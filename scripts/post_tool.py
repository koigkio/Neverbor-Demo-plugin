#!/usr/bin/env python3
"""neverbor — PostToolUse hook. Compresses Bash and MCP tool output before Claude reads it.

Claude Code replaces the tool result with hookSpecificOutput.updatedToolOutput.
For built-in tools a value that doesn't match the tool's schema is ignored, so
the worst case of a bug here is "no compression", never a broken result.
Any exception -> exit 0 with no output (fail open).
"""

import hashlib
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compress  # noqa: E402
import journal  # noqa: E402
import state  # noqa: E402

# If the last stage of a command already shows a precise slice of something
# (file contents, a diff), the model asked for exact text: leave it alone.
PASSTHROUGH = re.compile(
    r"^(cat|bat|head|tail|sed|awk|less|more|nl|wc|jq|yq|diff|git\s+(diff|show|blame)|"
    r"gh\s+pr\s+diff|base64|xxd|od)\b"
)
DIFF_COMMAND = re.compile(r"^(diff|git\s+(diff|show)|gh\s+pr\s+diff)\b")

# Outputs shorter than this aren't worth replacing with a "same as before" pointer.
REPEAT_MIN_CHARS = 300


def last_stage(command):
    return re.split(r"&&|\|\||;|\|", command)[-1].strip()


def should_skip(command, cfg):
    if "neverbor:off" in command:
        return True
    stage = last_stage(command)
    if cfg["passthrough"] and re.match(r"^(%s)\b" % cfg["passthrough"], stage):
        return True
    if cfg["compress_diff"] and DIFF_COMMAND.match(stage):
        return False
    return bool(PASSTHROUGH.match(stage))


def footer(before, after, path):
    return (
        "\n[neverbor: output condensed %d→%d chars, parts omitted — don't conclude something is "
        "missing from this view; full original: %s (Grep/Read it when the omitted part matters)]"
        % (before, after, path)
    )


def joined(stdout, stderr):
    return stdout + ("\n--- stderr ---\n" + stderr if stderr else "")


def neverbor_bash(resp, cfg, ctx):
    """Returns (new response or None, path of the saved original or None)."""
    stdout = resp.get("stdout") or ""
    stderr = resp.get("stderr") or ""
    new_out = compress.compress_text(stdout, cfg)
    new_err = compress.compress_text(stderr, cfg)
    if new_out is None and new_err is None:
        return None, None
    original = joined(stdout, stderr)
    path = state.save_original(original)
    stdout = new_out if new_out is not None else stdout
    stderr = new_err if new_err is not None else stderr
    after = len(stdout) + len(stderr)
    if new_out is not None:
        stdout += footer(len(original), after, path)
    else:
        stderr += footer(len(original), after, path)
    state.record("Bash", original, joined(stdout, stderr), **ctx)
    return dict(resp, stdout=stdout, stderr=stderr), path


def repeat_of(resp, command, session):
    """If this session already saw this exact command + output, point back to it instead."""
    key = hashlib.sha1(
        "\0".join((command, resp.get("stdout") or "", resp.get("stderr") or "")).encode("utf-8", "replace")
    ).hexdigest()
    return key, session["seen"].get(key)


def neverbor_mcp(tool, resp, cfg, ctx):
    """MCP results: a string, a list of content blocks, or {"content": [...]}."""
    if isinstance(resp, str):
        new = compress.compress_text(resp, cfg)
        if new is None:
            return None
        path = state.save_original(resp)
        new += footer(len(resp), len(new), path)
        state.record(tool, resp, new, **ctx)
        return new

    blocks = resp.get("content") if isinstance(resp, dict) else resp
    if not isinstance(blocks, list):
        return None
    changed = False
    out_blocks = []
    for block in blocks:
        text = block.get("text") if isinstance(block, dict) and block.get("type") == "text" else None
        new = compress.compress_text(text, cfg) if text else None
        if new is None:
            out_blocks.append(block)
            continue
        path = state.save_original(text)
        new += footer(len(text), len(new), path)
        state.record(tool, text, new, **ctx)
        out_blocks.append(dict(block, text=new))
        changed = True
    if not changed:
        return None
    return dict(resp, content=out_blocks) if isinstance(resp, dict) else out_blocks


def handle_bash(resp, command, cfg, ctx):
    session_id = ctx["session_id"]
    size = len(resp.get("stdout") or "") + len(resp.get("stderr") or "")
    if not session_id or size < REPEAT_MIN_CHARS:
        return neverbor_bash(resp, cfg, ctx)[0]

    session = state.load_session(session_id)
    key, seen = repeat_of(resp, command, session)
    if seen:
        path, when = seen
        note = (
            "[neverbor: output identical to the same command run at %s (%d chars); full output: %s — "
            "Read it only if it is no longer in your context]" % (when, size, path)
        )
        state.record("Bash", joined(resp.get("stdout") or "", resp.get("stderr") or ""), note, **ctx)
        return dict(resp, stdout=note, stderr="")

    new, path = neverbor_bash(resp, cfg, ctx)
    session["seen"][key] = [path or state.save_original(joined(resp.get("stdout") or "", resp.get("stderr") or "")),
                            time.strftime("%H:%M:%S")]
    state.save_session(session_id, session)
    return new


def handle_read(resp, tool_input, session_id):
    """Opt-in (`reread`): a full re-read of a file unchanged since the last full read gets a pointer."""
    file = resp.get("file") if isinstance(resp, dict) and resp.get("type") == "text" else None
    path = tool_input.get("file_path")
    if not isinstance(file, dict) or not isinstance(file.get("content"), str) or not isinstance(path, str):
        return None
    partial = tool_input.get("offset") is not None or tool_input.get("limit") is not None
    at = journal.reread_note(session_id, path, partial)
    if not at:
        return None
    note = ("[neverbor: unchanged since you read it in full at %s, see that copy. If it is no longer in "
            "your context, Read it again and it will be shown in full.]" % at)
    state.record("Read", file["content"], note, session_id, "Read")
    return dict(resp, file=dict(file, content=note))


def main():
    data = state.read_hook_input()
    tool = data.get("tool_name", "")
    tool_input = data.get("tool_input") or {}
    resp = data.get("tool_response")
    session_id = data.get("session_id") or ""
    cfg = state.load_config()
    command = tool_input.get("command", "") if tool == "Bash" else ""

    # The journal works even with compression off: it only records, never changes output.
    if tool in journal.EDIT_TOOLS:
        journal.note_edit(session_id, tool_input.get(journal.EDIT_TOOLS[tool]) or "?")
        return
    if tool == "Bash" and command:
        journal.note_command(session_id, command)
    if not state.enabled():
        return
    words = last_stage(command).split()
    ctx = {"session_id": session_id, "cmd": words[0] if words else ""}

    if tool == "Read":
        new = handle_read(resp, tool_input, session_id) if cfg["reread"] else None
    elif tool == "Bash" and isinstance(resp, dict):
        if should_skip(command, cfg):
            return
        new = handle_bash(resp, command, cfg, ctx)
    elif tool.startswith("mcp__"):
        new = neverbor_mcp(tool, resp, cfg, ctx)
    else:
        return

    if new is not None:
        state.write_hook_output({"hookSpecificOutput": {"hookEventName": "PostToolUse", "updatedToolOutput": new}})


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # fail open: never break the tool call
        if os.environ.get("NEVERBOR_DEBUG"):
            sys.stderr.write("neverbor: %s\n" % ascii(e))
    sys.exit(0)
