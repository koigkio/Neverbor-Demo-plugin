#!/usr/bin/env python3
"""neverbor CLI: `neverbor.py [stats [today|week|all]|on|off|terse on|off|quiet on|off|reread on|off|brief|
mode <name>|config [key value]]`."""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import journal  # noqa: E402
import state  # noqa: E402

USAGE = ("usage: /neverbor [stats [today|week|all] | on | off | terse on|off | quiet on|off | "
         "reread on|off | brief | mode light|normal|aggressive | config [key value]]")
PERIODS = {"today": None, "week": 7 * 86400, "all": None}


def set_flag(path, present):
    os.makedirs(state.HOME, exist_ok=True)
    if present:
        open(path, "w").close()
    elif os.path.exists(path):
        os.remove(path)


def onoff(value):
    return "ON" if value else "OFF"


def stats(period="all"):
    cfg = state.load_config()
    print("neverbor: compression %s, terse rules %s, quiet flags %s, mode %s" % (
        onoff(state.enabled()), onoff(state.terse_enabled()), onoff(state.quiet_enabled()), cfg["mode"]))
    rows = state.read_ledger()
    if period == "today":
        start = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))
        rows = [r for r in rows if r.get("ts", 0) >= start]
    elif period == "week":
        rows = [r for r in rows if r.get("ts", 0) >= time.time() - PERIODS["week"]]
    if not rows:
        print("No outputs compressed (%s)." % period)
        return
    before = sum(r["before"] for r in rows)
    after = sum(r["after"] for r in rows)
    print("Period: %s" % period)
    print("Compressed outputs: %d" % len(rows))
    print("Chars: %d → %d (saved %.0f%%)" % (before, after, 100.0 * (before - after) / max(before, 1)))
    print("≈ tokens saved: %d" % sum(state.saved_tokens(r) for r in rows))

    def table(title, key):
        groups = {}
        for r in rows:
            g = groups.setdefault(key(r) or "?", [0, 0])
            g[0] += 1
            g[1] += state.saved_tokens(r)
        print(title)
        for name, (n, saved) in sorted(groups.items(), key=lambda kv: -kv[1][1])[:5]:
            print("  %-40s %5d calls  ≈%d tokens" % (name, n, saved))

    table("By tool:", lambda r: r.get("tool"))
    if any(r.get("cmd") for r in rows):
        table("Top commands:", lambda r: r.get("cmd"))


def parse_value(raw):
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def config(args):
    if not args:
        user = state.read_user_config()
        print("neverbor config (%s):" % state.CONFIG)
        for key, value in sorted(state.load_config().items()):
            print("  %-14s %s%s" % (key, json.dumps(value, ensure_ascii=False), "  (set)" if key in user else ""))
        return
    key = args[0]
    if key not in state.DEFAULTS:
        print("neverbor: unknown key %r. Known: %s" % (key, ", ".join(sorted(state.DEFAULTS))))
        return
    user = state.read_user_config()
    if len(args) == 1 or args[1] == "reset":
        user.pop(key, None)
        print("neverbor: %s reset to default" % key)
    else:
        value = parse_value(" ".join(args[1:]))
        expected = type(state.DEFAULTS[key])
        if expected is float and isinstance(value, int) and not isinstance(value, bool):
            value = float(value)
        if not isinstance(value, expected) or (expected is int and isinstance(value, bool)):
            print("neverbor: %s expects %s" % (key, expected.__name__))
            return
        user[key] = value
        print("neverbor: %s = %s" % (key, json.dumps(value, ensure_ascii=False)))
    state.write_user_config(user)


def set_config(key, value):
    user = state.read_user_config()
    user[key] = value
    state.write_user_config(user)


def brief():
    """Work log of the most recent session: what Claude gets back after /compact."""
    try:
        names = [n for n in os.listdir(state.SESSIONS) if n.endswith(".json")]
    except OSError:
        names = []
    if not names:
        print("neverbor: no session log yet.")
        return
    latest = max(names, key=lambda n: os.path.getmtime(os.path.join(state.SESSIONS, n)))
    text = journal.brief(state.load_session(latest[:-5]), os.getcwd())
    print(text or "neverbor: nothing logged in the latest session yet.")


def main(args):
    words = [a for a in " ".join(args).split() if a]
    cmd = words[0].lower() if words else "stats"
    rest = words[1:]
    sub = rest[0].lower() if rest else ""
    if cmd == "on":
        set_flag(state.OFF_FLAG, False)
        print("neverbor: compression ON")
    elif cmd == "off":
        set_flag(state.OFF_FLAG, True)
        print("neverbor: compression OFF (tool output passes through untouched)")
    elif cmd == "terse" and sub in ("on", "off"):
        set_flag(state.TERSE_OFF_FLAG, sub == "off")
        print("neverbor: terse rules %s from the next session" % sub.upper())
    elif cmd == "quiet" and sub in ("on", "off"):
        set_flag(state.QUIET_ON_FLAG, sub == "on")
        print("neverbor: quiet flags %s (each rewritten command asks for your approval)" % sub.upper()
              if sub == "on" else "neverbor: quiet flags OFF")
    elif cmd == "reread" and sub in ("on", "off"):
        set_config("reread", sub == "on")
        print("neverbor: re-read pointers %s" % sub.upper())
    elif cmd == "brief":
        brief()
    elif cmd == "mode" and sub in state.MODES:
        set_config("mode", sub)
        print("neverbor: mode %s" % sub)
    elif cmd == "config":
        config(rest)
    elif cmd == "stats" and sub in ("", "today", "week", "all"):
        stats(sub or "all")
    else:
        print(USAGE)


if __name__ == "__main__":
    # Windows consoles default to a legacy code page; the output has →, ≈ and Cyrillic.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    main(sys.argv[1:])
