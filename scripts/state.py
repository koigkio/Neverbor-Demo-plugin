"""neverbor — where state lives: on/off flag, original-output cache, savings ledger."""

import hashlib
import json
import os
import time

HOME = os.environ.get("NEVERBOR_HOME") or os.path.join(
    os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"), "neverbor"
)
CACHE = os.path.join(HOME, "cache")
LEDGER = os.path.join(HOME, "stats.jsonl")
OFF_FLAG = os.path.join(HOME, "off")
TERSE_OFF_FLAG = os.path.join(HOME, "terse-off")
CACHE_DAYS = 3


def enabled():
    return os.environ.get("NEVERBOR", "1") != "0" and not os.path.exists(OFF_FLAG)


def terse_enabled():
    return os.environ.get("NEVERBOR_TERSE", "1") != "0" and not os.path.exists(TERSE_OFF_FLAG)


def save_original(text):
    """Keep the full output so the model can Read it back (headroom's CCR idea)."""
    os.makedirs(CACHE, exist_ok=True)
    digest = hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()[:10]
    path = os.path.join(CACHE, "%s-%s.txt" % (time.strftime("%Y%m%d-%H%M%S"), digest))
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def record(tool, before, after):
    os.makedirs(HOME, exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": int(time.time()), "tool": tool, "before": before, "after": after}) + "\n")


def prune_cache():
    if not os.path.isdir(CACHE):
        return
    cutoff = time.time() - CACHE_DAYS * 86400
    for name in os.listdir(CACHE):
        path = os.path.join(CACHE, name)
        try:
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
        except OSError:
            pass
