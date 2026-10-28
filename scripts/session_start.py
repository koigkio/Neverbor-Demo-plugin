#!/usr/bin/env python3
"""neverbor — SessionStart hook: prune old cached outputs and add token-saving rules.

The rules cut OUTPUT tokens (what the model writes) and steer it toward
small, targeted reads — the same idea as ponytail's injected ruleset and
headroom's "verbosity steering".
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import state  # noqa: E402

FOOTER_NOTE = (
    "Some tool outputs in this session are condensed by the neverbor plugin and end with a "
    "`[neverbor: …]` footer naming a file with the full original. Read or Grep that file "
    "(with offset/limit) only when the omitted part matters; don't re-run the command to see it."
)

TERSE_RULES = """Token budget rules (neverbor plugin):
- Answer directly. No preambles ("Great, let me…"), no recaps of what you just did, no restating the request.
- Don't re-print code the user already has; show only changed lines or a short diff.
- Read narrowly: Grep first, then Read with offset/limit; avoid dumping whole large files.
- Keep shell output small: quiet flags (-q, --silent, --quiet), `| tail -n 40`, `| grep -E 'error|fail'`.
- Don't re-read files you already read in this session unless they changed."""


def main():
    state.prune_cache()
    if not state.enabled():
        return
    context = FOOTER_NOTE
    if state.terse_enabled():
        context = TERSE_RULES + "\n\n" + FOOTER_NOTE
    json.dump({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}, sys.stdout)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
