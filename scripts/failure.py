#!/usr/bin/env python3
"""neverbor — PostToolUseFailure hook: journal failed Bash commands and flag repeat failures.

When the same command fails with the same error several times in a row, Claude gets a
short hint to change approach instead of retrying. Output of a failed command is never changed.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import journal  # noqa: E402
import state  # noqa: E402


def main():
    data = state.read_hook_input()
    command = (data.get("tool_input") or {}).get("command")
    if data.get("tool_name") != "Bash" or not isinstance(command, str) or data.get("is_interrupt"):
        return
    error = data.get("error")
    count = journal.note_failure(data.get("session_id") or "", command, error if isinstance(error, str) else "")
    hint = journal.loop_hint(count, command) if state.enabled() else None
    if hint:
        state.write_hook_output({"hookSpecificOutput": {"hookEventName": "PostToolUseFailure", "additionalContext": hint}})


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
