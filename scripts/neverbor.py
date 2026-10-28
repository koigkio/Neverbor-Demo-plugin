#!/usr/bin/env python3
"""neverbor CLI: `neverbor.py [stats|on|off|terse on|terse off]`."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import state  # noqa: E402


def set_flag(path, on):
    os.makedirs(state.HOME, exist_ok=True)
    if on and os.path.exists(path):
        os.remove(path)
    elif not on:
        open(path, "w").close()


def stats():
    rows = []
    if os.path.exists(state.LEDGER):
        with open(state.LEDGER, encoding="utf-8") as f:
            rows = [json.loads(l) for l in f if l.strip()]
    print("neverbor: compression %s, terse rules %s" % (
        "ON" if state.enabled() else "OFF", "ON" if state.terse_enabled() else "OFF"))
    if not rows:
        print("No outputs compressed yet.")
        return
    before = sum(r["before"] for r in rows)
    after = sum(r["after"] for r in rows)
    print("Compressed outputs: %d" % len(rows))
    print("Chars: %d → %d (saved %.0f%%)" % (before, after, 100.0 * (before - after) / before))
    print("≈ tokens saved: %d (chars/4 estimate)" % ((before - after) // 4))
    by_tool = {}
    for r in rows:
        t = by_tool.setdefault(r["tool"], [0, 0])
        t[0] += 1
        t[1] += r["before"] - r["after"]
    print("By tool:")
    for tool, (n, saved) in sorted(by_tool.items(), key=lambda kv: -kv[1][1]):
        print("  %-40s %5d calls  ≈%d tokens" % (tool, n, saved // 4))


def main(args):
    cmd = " ".join(args).strip().lower() or "stats"
    if cmd == "on":
        set_flag(state.OFF_FLAG, True)
        print("neverbor: compression ON")
    elif cmd == "off":
        set_flag(state.OFF_FLAG, False)
        print("neverbor: compression OFF (tool output passes through untouched)")
    elif cmd == "terse on":
        set_flag(state.TERSE_OFF_FLAG, True)
        print("neverbor: terse rules ON from the next session")
    elif cmd == "terse off":
        set_flag(state.TERSE_OFF_FLAG, False)
        print("neverbor: terse rules OFF from the next session")
    elif cmd == "stats":
        stats()
    else:
        print("usage: /neverbor [stats|on|off|terse on|terse off]")


if __name__ == "__main__":
    main(sys.argv[1:])
