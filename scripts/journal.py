"""neverbor — session journal: which files changed, which commands ran and how they ended.

It feeds three things:
  * the work brief put back into context after /compact (brief)
  * the "same failure again" hint (note_failure)
  * the "file unchanged since you read it" pointer (opt-in, reread_note)
Everything lives in the per-session file from state.load_session().
"""

import hashlib
import os
import time

import compress
import state

MAX_COMMANDS = 30
MAX_BRIEF = 1500
LOOP_AFTER = 3  # the same failure this many times in a row gets a hint
EDIT_TOOLS = {"Edit": "file_path", "Write": "file_path", "MultiEdit": "file_path", "NotebookEdit": "notebook_path"}


def _update(session_id, change):
    if not session_id:
        return None
    data = state.load_session(session_id)
    for key, empty in (("files", {}), ("cmds", []), ("reads", {}), ("fails", {})):
        data.setdefault(key, empty)
    result = change(data)
    state.save_session(session_id, data)
    return result


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def note_edit(session_id, path):
    def change(data):
        f = data["files"].setdefault(path, {"n": 0})
        f["n"] += 1
        f["t"] = time.time()
        data["reads"].pop(path, None)  # an edited file must be shown in full next time
    _update(session_id, change)


def _push_command(data, command, ok, error=""):
    data["cmds"].append({"cmd": command[:200], "ok": ok, "err": error[:200], "t": time.time()})
    del data["cmds"][:-MAX_COMMANDS]


def note_command(session_id, command):
    def change(data):
        _push_command(data, command, True)
        data["fails"].pop(command, None)
    _update(session_id, change)


def _first_error_line(error):
    lines = [l.strip() for l in (error or "").splitlines() if l.strip()]
    for line in reversed(lines):
        if compress.IMPORTANT.search(line):
            return line
    return lines[-1] if lines else ""


def note_failure(session_id, command, error):
    """Returns how many times in a row this command failed with this same error."""
    line = _first_error_line(error)
    digest = hashlib.sha1(line.encode("utf-8", "replace")).hexdigest()[:12]

    def change(data):
        _push_command(data, command, False, line)
        prev = data["fails"].get(command)
        count = prev[1] + 1 if prev and prev[0] == digest else 1
        data["fails"][command] = [digest, count]
        return count
    return _update(session_id, change) or 0


def loop_hint(count, command):
    if count < LOOP_AFTER:
        return None
    return ("[neverbor: `%s` has now failed %d times in a row with the same error. Repeating it won't "
            "help: re-read the error, check your assumption, or try a different approach.]"
            % (command[:120], count))


def reread_note(session_id, path, partial):
    """Note for a full re-read of an unchanged file, or None to show it.

    Never twice in a row for one file: if Claude asks again right after a note, it has lost the
    earlier copy (cleared tool results), so the second request goes through.
    """
    mtime = _mtime(path)

    def change(data):
        seen = data["reads"].get(path)
        if partial or mtime is None:
            return None
        if seen and seen.get("m") == mtime and not seen.get("noted"):
            seen["noted"] = True
            return seen["at"]
        data["reads"][path] = {"m": mtime, "at": time.strftime("%H:%M:%S")}
        return None
    return _update(session_id, change)


def forget_reads(session_id):
    _update(session_id, lambda data: data["reads"].clear())


def _rel(path, cwd):
    if cwd and path.startswith(cwd.rstrip("/\\") + os.sep):
        return path[len(cwd.rstrip("/\\")) + 1:]
    return path


def brief(session, cwd=""):
    """Short work log for after a compaction, or "" when nothing happened yet."""
    files = sorted((session.get("files") or {}).items(), key=lambda kv: -kv[1].get("t", 0))
    cmds = session.get("cmds") or []
    if not files and not cmds:
        return ""
    out = ["[neverbor: work log of this session, kept across the compaction]"]
    if files:
        shown = ", ".join("%s%s" % (_rel(p, cwd), " (×%d)" % f["n"] if f["n"] > 1 else "") for p, f in files[:15])
        more = " … and %d more" % (len(files) - 15) if len(files) > 15 else ""
        out.append("Files changed (%d, newest first): %s%s" % (len(files), shown, more))
    latest = {}
    for c in cmds:
        latest.pop(c["cmd"], None)
        latest[c["cmd"]] = c
    if latest:
        out.append("Last commands (newest last):")
        for c in list(latest.values())[-8:]:
            out.append("  `%s` → %s" % (c["cmd"][:100], "ok" if c["ok"] else "FAILED: " + c["err"][:120]))
    out.append("Full outputs of earlier commands are cached in %s." % state.CACHE)
    text = "\n".join(out)
    return text if len(text) <= MAX_BRIEF else text[: MAX_BRIEF - 2] + " …"
