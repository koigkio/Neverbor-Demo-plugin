#!/usr/bin/env python3
"""neverbor — PostToolUse hook. Compresses Bash and MCP tool output before Claude reads it.

Claude Code replaces the tool result with hookSpecificOutput.updatedToolOutput.
For built-in tools a value that doesn't match the tool's schema is ignored, so
the worst case of a bug here is "no compression", never a broken result.
Any exception -> exit 0 with no output (fail open).
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compress  # noqa: E402
import state  # noqa: E402

# If the last stage of a command already shows a precise slice of something
# (file contents, a diff), the model asked for exact text: leave it alone.
PASSTHROUGH = re.compile(
    r"^(cat|bat|head|tail|sed|awk|less|more|nl|wc|jq|yq|diff|git\s+(diff|show|blame)|"
    r"gh\s+pr\s+diff|base64|xxd|od)\b"
)


def last_stage(command):
    return re.split(r"&&|\|\||;|\|", command)[-1].strip()


def should_skip(command):
    if "neverbor:off" in command:
        return True
    extra = os.environ.get("NEVERBOR_PASSTHROUGH", "")
    stage = last_stage(command)
    if extra and re.match(r"^(%s)\b" % extra, stage):
        return True
    return bool(PASSTHROUGH.match(stage))


def footer(before, after, path):
    return (
        "\n[neverbor: output condensed %d→%d chars; full original: %s — "
        "Read/Grep it only if the omitted part matters]" % (before, after, path)
    )


def neverbor_bash(resp):
    stdout = resp.get("stdout") or ""
    stderr = resp.get("stderr") or ""
    new_out = compress.compress_text(stdout)
    new_err = compress.compress_text(stderr)
    if new_out is None and new_err is None:
        return None
    before = len(stdout) + len(stderr)
    path = state.save_original(stdout + ("\n--- stderr ---\n" + stderr if stderr else ""))
    stdout = new_out if new_out is not None else stdout
    stderr = new_err if new_err is not None else stderr
    after = len(stdout) + len(stderr)
    if new_out is not None:
        stdout += footer(before, after, path)
    else:
        stderr += footer(before, after, path)
    state.record("Bash", before, after)
    return dict(resp, stdout=stdout, stderr=stderr)


def neverbor_mcp(tool, resp):
    """MCP results: a string, a list of content blocks, or {"content": [...]}."""
    if isinstance(resp, str):
        new = compress.compress_text(resp)
        if new is None:
            return None
        path = state.save_original(resp)
        state.record(tool, len(resp), len(new))
        return new + footer(len(resp), len(new), path)

    blocks = resp.get("content") if isinstance(resp, dict) else resp
    if not isinstance(blocks, list):
        return None
    changed = False
    out_blocks = []
    for block in blocks:
        text = block.get("text") if isinstance(block, dict) and block.get("type") == "text" else None
        new = compress.compress_text(text) if text else None
        if new is None:
            out_blocks.append(block)
            continue
        path = state.save_original(text)
        state.record(tool, len(text), len(new))
        out_blocks.append(dict(block, text=new + footer(len(text), len(new), path)))
        changed = True
    if not changed:
        return None
    return dict(resp, content=out_blocks) if isinstance(resp, dict) else out_blocks


def main():
    if not state.enabled():
        return
    data = json.loads(sys.stdin.read().lstrip("﻿"))
    tool = data.get("tool_name", "")
    resp = data.get("tool_response")

    if tool == "Bash" and isinstance(resp, dict):
        if should_skip((data.get("tool_input") or {}).get("command", "")):
            return
        new = neverbor_bash(resp)
    elif tool.startswith("mcp__"):
        new = neverbor_mcp(tool, resp)
    else:
        return

    if new is not None:
        json.dump(
            {"hookSpecificOutput": {"hookEventName": "PostToolUse", "updatedToolOutput": new}},
            sys.stdout,
            ensure_ascii=False,
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # fail open: never break the tool call
        if os.environ.get("NEVERBOR_DEBUG"):
            print("neverbor: %r" % e, file=sys.stderr)
    sys.exit(0)
