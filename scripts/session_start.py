#!/usr/bin/env python3
"""neverbor — SessionStart hook: prune old cached outputs and add token-saving rules.

The rules cut OUTPUT tokens (what the model writes) and steer it toward
small, targeted reads — the same idea as ponytail's injected ruleset and
headroom's "verbosity steering".
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import state  # noqa: E402

FOOTER_NOTE = (
    "Some tool outputs in this session are condensed by the neverbor plugin and end with a "
    "`[neverbor: …]` footer naming a file with the full original; a repeated command with identical output is replaced by a pointer to the earlier run. Read or Grep that file "
    "(with offset/limit) only when the omitted part matters; don't re-run the command to see it."
)

TERSE_RULES = """Token budget rules (neverbor plugin):
- Answer directly. No preambles ("Great, let me…"), no recaps of what you just did, no restating the request.
- Don't re-print code the user already has; show only changed lines or a short diff.
- Read narrowly: Grep first, then Read with offset/limit; avoid dumping whole large files.
- Keep shell output small: quiet flags (-q, --silent, --quiet), `| tail -n 40`, `| grep -E 'error|fail'`.
- Don't re-read files you already read in this session unless they changed."""


def main():
    try:
        data = state.read_hook_input()
    except ValueError:
        data = {}
    cfg = state.load_config()
    state.prune_cache(cfg["cache_days"])
    if data.get("source") in ("compact", "clear") and data.get("session_id"):
        state.forget_seen(data["session_id"])
    if not state.enabled():
        return
    context = FOOTER_NOTE
    if state.terse_enabled():
        rules = TERSE_RULES
        if cfg["rules_extra"]:
            rules += "\n- " + cfg["rules_extra"].strip()
        context = rules + "\n\n" + FOOTER_NOTE
    state.write_hook_output({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}})


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
