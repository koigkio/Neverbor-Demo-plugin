#!/usr/bin/env python3
"""neverbor — PreToolUse hook (opt-in: /neverbor quiet on): add quiet flags to noisy commands.

Only a single, simple command from a short allowlist is rewritten. The rewrite is
always returned with permissionDecision "ask", so the user sees and approves the
new command: the hook never widens what runs without their consent.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import state  # noqa: E402

# (pattern for the whole command, flag that means "already quiet", text to append)
REWRITES = [
    (re.compile(r"^npm (install|i|ci)\b"), re.compile(r"--loglevel|--silent|-s\b|-q\b"),
     " --no-fund --no-audit --loglevel=warn"),
    (re.compile(r"^(pip3?|python3? -m pip) install\b"), re.compile(r"\s(-q|--quiet)\b"), " -q"),
    (re.compile(r"^git clone\b"), re.compile(r"\s(-q|--quiet)\b"), " -q"),
    (re.compile(r"^cargo (build|check)\b"), re.compile(r"\s(-q|--quiet|-v)\b"), " -q"),
]
COMPOUND = re.compile(r"&&|\|\||[;|<>`$()]|\n")


def quiet(command):
    command = command.strip()
    if not command or COMPOUND.search(command):
        return None
    for pattern, already, extra in REWRITES:
        if pattern.match(command) and not already.search(command):
            return command + extra
    return None


def main():
    if not (state.enabled() and state.quiet_enabled()):
        return
    data = state.read_hook_input()
    tool_input = data.get("tool_input") or {}
    if data.get("tool_name") != "Bash" or not isinstance(tool_input.get("command"), str):
        return
    new = quiet(tool_input["command"])
    if new is None:
        return
    state.write_hook_output({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "ask",
        "permissionDecisionReason": "neverbor quiet mode: %s" % new,
        "updatedInput": dict(tool_input, command=new),
    }})


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
