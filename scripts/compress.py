"""neverbor — text compressors for tool output. Stdlib only, Python 3.8+.

Ideas borrowed from headroom (github.com/headroomlabs-ai/headroom):
  * dense_line_elider  -> elide_dense_lines
  * log_compressor     -> dedupe_runs + keep_important (errors survive)
  * smart_crusher      -> crush_json (long arrays sampled, JSON minified)
  * CCR (reversible)   -> the caller saves the original and names it in a footer
"""

import json
import re

ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")

# Lines that must survive truncation: errors, failures, warnings, tracebacks.
IMPORTANT = re.compile(
    r"\b(error|errors|fail|failed|failure|fatal|panic|exception|traceback|"
    r"assert|assertion|denied|warning|warn|cannot|unable|not found|undefined|"
    r"segfault|killed|abort|aborted)\b|ERR!|FAIL|✗|✖|❌",
    re.IGNORECASE,
)

# Volatile tokens: numbers, hex ids, uuids, timestamps. Lines that differ only
# in these are "the same line" for run collapsing.
VOLATILE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    r"|\b[0-9a-f]{7,}\b|\d+(?:[.:]\d+)*",
    re.IGNORECASE,
)

DEFAULTS = {
    "min_chars": 2500,  # smaller outputs pass through untouched
    "max_lines": 150,  # above this, head/tail/important truncation kicks in
    "head": 50,
    "tail": 40,
    "max_important": 40,
    "min_saving": 0.15,  # don't bother if we save less than 15%
}


def strip_ansi(text):
    return ANSI.sub("", text)


def collapse_carriage_returns(text):
    """Progress bars redraw with \\r; only the final state matters."""
    out = []
    for line in text.split("\n"):
        if "\r" in line:
            parts = [p for p in line.split("\r") if p]
            line = parts[-1] if parts else ""
        out.append(line)
    return "\n".join(out)


def elide_dense_lines(text, min_len=600, head=160, tail=80):
    """Minified JS/CSS, base64, bundles: long lines with almost no spaces."""
    out = []
    for line in text.split("\n"):
        n = len(line)
        if (
            n >= min_len
            and line.count(" ") / n < 0.06
            and "\t" not in line
            and line.lstrip()[:1] not in ("{", "[")
        ):
            line = "%s…[%d chars elided]…%s" % (line[:head], n - head - tail, line[-tail:])
        out.append(line)
    return "\n".join(out)


def dedupe_runs(lines, min_run=3):
    """Collapse runs of identical / same-shaped consecutive lines."""
    out = []
    i = 0
    while i < len(lines):
        key = VOLATILE.sub("#", lines[i]).strip()
        j = i + 1
        while j < len(lines) and VOLATILE.sub("#", lines[j]).strip() == key:
            j += 1
        run = j - i
        if run >= min_run and key:
            exact = all(l == lines[i] for l in lines[i:j])
            if exact:
                out.append(lines[i])
                out.append("  … (same line repeated %d more times)" % (run - 1))
            else:
                out.extend(lines[i : i + 2])
                out.append("  … (%d similar lines)" % (run - 3))
                out.append(lines[j - 1])
        else:
            out.extend(lines[i:j])
        i = j
    return out


def keep_important(lines, cfg):
    """Head + tail + every important line (with one line of context) from the middle."""
    n = len(lines)
    keep = set(range(min(cfg["head"], n))) | set(range(max(0, n - cfg["tail"]), n))
    found = 0
    for idx in range(cfg["head"], n - cfg["tail"]):
        if found >= cfg["max_important"]:
            break
        if IMPORTANT.search(lines[idx]):
            keep.update((idx - 1, idx, idx + 1))
            found += 1
    out = []
    prev = -1
    for idx in sorted(k for k in keep if 0 <= k < n):
        if idx != prev + 1:
            out.append("… [%d lines omitted] …" % (idx - prev - 1))
        out.append(lines[idx])
        prev = idx
    return out


def _crush(value, max_items=12, max_str=400):
    if isinstance(value, list):
        if len(value) > max_items:
            picked = list(range(5)) + list(range(len(value) - 2, len(value)))
            # Keep items that look like errors even if they're in the middle.
            for i in range(5, len(value) - 2):
                if len(picked) >= 12:
                    break
                if IMPORTANT.search(json.dumps(value[i], ensure_ascii=False)):
                    picked.append(i)
            picked = sorted(set(picked))
            keys = sorted({k for v in value if isinstance(v, dict) for k in v})[:15]
            crushed = [_crush(value[i], max_items, max_str) for i in picked]
            note = "… %d of %d items omitted" % (len(value) - len(picked), len(value))
            if keys:
                note += " (item keys: %s)" % ", ".join(keys)
            crushed.insert(5, note)
            return crushed
        return [_crush(v, max_items, max_str) for v in value]
    if isinstance(value, dict):
        return {k: _crush(v, max_items, max_str) for k, v in value.items()}
    if isinstance(value, str) and len(value) > max_str:
        return value[:300] + "…[%d chars]…" % (len(value) - 380) + value[-80:]
    return value


def crush_json(text):
    """Returns minified, sampled JSON, or None if text isn't JSON."""
    s = text.strip()
    if not s or s[0] not in "[{":
        return None
    try:
        data = json.loads(s)
    except ValueError:
        return None
    return json.dumps(_crush(data), ensure_ascii=False, separators=(",", ":"))


def compress_text(text, cfg=None):
    """Return compressed text, or None when it isn't worth it."""
    cfg = dict(DEFAULTS, **(cfg or {}))
    if not isinstance(text, str) or len(text) < cfg["min_chars"]:
        return None

    out = crush_json(text)
    if out is None:
        out = collapse_carriage_returns(strip_ansi(text))
        out = elide_dense_lines(out)
        lines = dedupe_runs(out.split("\n"))
        if len(lines) > cfg["max_lines"]:
            lines = keep_important(lines, cfg)
        out = "\n".join(lines)

    if len(out) > len(text) * (1 - cfg["min_saving"]):
        return None
    return out
