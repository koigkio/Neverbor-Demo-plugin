"""neverbor — where state lives: flags, config, original-output cache, savings ledger, per-session index."""

import hashlib
import json
import os
import re
import sys
import time

import compress

HOME = os.environ.get("NEVERBOR_HOME") or os.path.join(
    os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"), "neverbor"
)
CACHE = os.path.join(HOME, "cache")
SESSIONS = os.path.join(HOME, "sessions")
LEDGER = os.path.join(HOME, "stats.jsonl")
CONFIG = os.path.join(HOME, "config.json")
OFF_FLAG = os.path.join(HOME, "off")
TERSE_OFF_FLAG = os.path.join(HOME, "terse-off")
QUIET_ON_FLAG = os.path.join(HOME, "quiet-on")

# Everything a user can put in config.json; compress.DEFAULTS covers the compressor knobs.
DEFAULTS = dict(
    compress.DEFAULTS,
    mode="normal",
    cache_days=3,
    passthrough="",  # extra regex of commands to leave untouched
    rules_extra="",  # appended to the terse rules
    compress_diff=False,
    lang="en",  # language of the end-of-reply savings message: en | ru
)

# Presets sit between the defaults and the user's own keys.
MODES = {
    "light": {"light": True, "min_chars": 5000},
    "normal": {},
    "aggressive": {"max_lines": 80, "head": 25, "tail": 20, "min_saving": 0.1},
}


def read_hook_input():
    """Hook JSON arrives as UTF-8 whatever the console code page is (cp1252 on many Windows setups)."""
    raw = sys.stdin.buffer.read().decode("utf-8-sig", "replace")
    return json.loads(raw) if raw.strip() else {}


def write_hook_output(data):
    """ASCII-only JSON (non-ASCII as \\u escapes) can't fail on any console encoding."""
    sys.stdout.write(json.dumps(data))


def enabled():
    return os.environ.get("NEVERBOR", "1") != "0" and not os.path.exists(OFF_FLAG)


def terse_enabled():
    return os.environ.get("NEVERBOR_TERSE", "1") != "0" and not os.path.exists(TERSE_OFF_FLAG)


def quiet_enabled():
    return os.environ.get("NEVERBOR_QUIET", "0") == "1" or os.path.exists(QUIET_ON_FLAG)


def read_user_config():
    try:
        with open(CONFIG, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_user_config(data):
    os.makedirs(HOME, exist_ok=True)
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_config():
    """defaults < mode preset < config.json < env vars. A broken file means defaults."""
    user = read_user_config()
    cfg = dict(DEFAULTS)
    cfg.update(MODES.get(user.get("mode", "normal"), {}))
    cfg.update({k: v for k, v in user.items() if k in DEFAULTS})
    if os.environ.get("NEVERBOR_PASSTHROUGH"):
        cfg["passthrough"] = os.environ["NEVERBOR_PASSTHROUGH"]
    return cfg


WIDE = re.compile(r"[Ѐ-ӿ぀-ヿ㐀-鿿가-힯]")


def estimate_tokens(text):
    """Latin text runs ~4 chars per token; Cyrillic and CJK closer to 2.5."""
    wide = len(WIDE.findall(text))
    return int((len(text) - wide) / 4 + wide / 2.5)


def save_original(text):
    """Keep the full output so the model can Read it back (headroom's CCR idea)."""
    os.makedirs(CACHE, exist_ok=True)
    digest = hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()[:10]
    path = os.path.join(CACHE, "%s-%s.txt" % (time.strftime("%Y%m%d-%H%M%S"), digest))
    with open(path, "w", encoding="utf-8", errors="replace") as f:
        f.write(text)
    return path


def record(tool, original, new, session_id="", cmd=""):
    os.makedirs(HOME, exist_ok=True)
    row = {
        "ts": int(time.time()),
        "tool": tool,
        "before": len(original),
        "after": len(new),
        "tok": max(0, estimate_tokens(original) - estimate_tokens(new)),
        "session": session_id,
        "cmd": cmd,
    }
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def read_ledger():
    rows = []
    try:
        with open(LEDGER, encoding="utf-8") as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    pass
    except OSError:
        pass
    return rows


def saved_tokens(row):
    return row.get("tok", (row.get("before", 0) - row.get("after", 0)) // 4)


def _session_path(session_id):
    safe = re.sub(r"[^A-Za-z0-9_-]", "", session_id)[:80]
    return os.path.join(SESSIONS, safe + ".json") if safe else None


def load_session(session_id):
    path = _session_path(session_id)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data.setdefault("seen", {})
            return data
    except (OSError, ValueError, TypeError):
        pass
    return {"seen": {}, "reported": 0}


def save_session(session_id, data):
    path = _session_path(session_id)
    if not path:
        return
    os.makedirs(SESSIONS, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def forget_seen(session_id):
    """After a compaction the model no longer has earlier outputs, so repeats must show in full again."""
    data = load_session(session_id)
    data["seen"] = {}
    save_session(session_id, data)


def prune_cache(days=3):
    cutoff = time.time() - days * 86400
    for folder in (CACHE, SESSIONS):
        if not os.path.isdir(folder):
            continue
        for name in os.listdir(folder):
            path = os.path.join(folder, name)
            try:
                if os.path.getmtime(path) < cutoff:
                    os.remove(path)
            except OSError:
                pass
