"""neverbor — project map: a short overview of a repository so Claude needn't explore it from scratch.

Top folders with file counts, languages, and how to build/run (package.json scripts, Makefile
targets, pyproject/Cargo/go.mod). Cached per folder; rebuilt when git HEAD or the top level changes.
"""

import hashlib
import json
import os
import re

import state

MAPS = os.path.join(state.HOME, "maps")
SKIP = {".git", "node_modules", "__pycache__", ".venv", "venv", "env", "dist", "build", "target", ".next",
        ".nuxt", "vendor", ".idea", ".vscode", ".mypy_cache", ".pytest_cache", ".tox", "coverage", ".cache"}
MAX_FILES = 20000
MAX_CHARS = 2500
LANGS = {".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
         ".go": "Go", ".rs": "Rust", ".java": "Java", ".kt": "Kotlin", ".swift": "Swift", ".rb": "Ruby",
         ".php": "PHP", ".cs": "C#", ".cpp": "C++", ".cc": "C++", ".c": "C", ".h": "C/C++", ".vue": "Vue",
         ".svelte": "Svelte", ".dart": "Dart", ".scala": "Scala", ".sh": "Shell", ".lua": "Lua"}


def _read(path, limit=200000):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read(limit)
    except OSError:
        return ""


def _git_head(root):
    head = _read(os.path.join(root, ".git", "HEAD")).strip()
    if head.startswith("ref: "):
        ref = head[5:]
        return ref.rsplit("/", 1)[-1], _read(os.path.join(root, ".git", ref)).strip()
    return "", head


def _walk(root):
    """{top-level folder: file count}, {language: file count}, total files (capped)."""
    folders, langs, total = {}, {}, 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP and not d.startswith("."))
        rel = os.path.relpath(dirpath, root)
        top = "." if rel == "." else rel.split(os.sep)[0]
        for name in filenames:
            total += 1
            folders[top] = folders.get(top, 0) + 1
            lang = LANGS.get(os.path.splitext(name)[1].lower())
            if lang:
                langs[lang] = langs.get(lang, 0) + 1
        if total >= MAX_FILES:
            break
    return folders, langs, total


def _how_to_run(root):
    out = []
    pkg = _read(os.path.join(root, "package.json"))
    if pkg:
        try:
            scripts = json.loads(pkg).get("scripts") or {}
        except ValueError:
            scripts = {}
        if scripts:
            out.append("npm scripts: " + ", ".join("%s (`%s`)" % (k, str(v)[:60]) for k, v in list(scripts.items())[:10]))
    make = _read(os.path.join(root, "Makefile"))
    targets = re.findall(r"^([A-Za-z][\w.-]*):(?!=)", make, re.MULTILINE)
    if targets:
        out.append("make targets: " + ", ".join(dict.fromkeys(targets[:15])))
    pyproject = _read(os.path.join(root, "pyproject.toml"))
    if pyproject:
        name = re.search(r'^name\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
        out.append("Python project%s (pyproject.toml)" % (" `%s`" % name.group(1) if name else ""))
    for marker, label in (("Cargo.toml", "Rust crate (cargo build / cargo run)"), ("go.mod", "Go module"),
                          ("requirements.txt", "pip requirements.txt"), ("Dockerfile", "Dockerfile"),
                          ("docker-compose.yml", "docker-compose.yml"), (".claude-plugin", "Claude Code plugin")):
        if os.path.exists(os.path.join(root, marker)):
            out.append(label)
    return out


def build(root):
    folders, langs, total = _walk(root)
    branch, _ = _git_head(root)
    title = os.path.basename(os.path.abspath(root)) or root
    lines = ["[neverbor: project map of %s%s — %s%d files, build/vendor folders skipped]" % (
        title, " (git branch %s)" % branch if branch else "", "≥" if total >= MAX_FILES else "", total)]
    if langs:
        lines.append("Languages: " + ", ".join("%s %d" % kv for kv in sorted(langs.items(), key=lambda kv: -kv[1])[:6]))
    root_files = sorted(n for n in os.listdir(root) if os.path.isfile(os.path.join(root, n)) and not n.startswith("."))
    if root_files:
        lines.append("Top-level files: " + ", ".join(root_files[:25]) + (" …" if len(root_files) > 25 else ""))
    tops = sorted((k for k in folders if k != "."), key=lambda k: -folders[k])
    if tops:
        lines.append("Folders: " + ", ".join("%s/ (%d)" % (k, folders[k]) for k in tops[:25]))
    lines.extend(_how_to_run(root))
    text = "\n".join(lines)
    return text if len(text) <= MAX_CHARS else text[: MAX_CHARS - 2] + " …"


def get(root):
    """Cached map for root; rebuilt when git HEAD or the top-level listing changed."""
    root = os.path.abspath(root)
    _, head = _git_head(root)
    try:
        stamp = "%s %s" % (head, os.path.getmtime(root))
    except OSError:
        return ""
    path = os.path.join(MAPS, hashlib.sha1(root.encode("utf-8", "replace")).hexdigest()[:12] + ".md")
    cached = _read(path)
    if cached.startswith(stamp + "\n"):
        return cached[len(stamp) + 1:]
    text = build(root)
    os.makedirs(MAPS, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(stamp + "\n" + text)
    return text
