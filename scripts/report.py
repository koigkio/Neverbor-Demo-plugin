"""neverbor — savings report (an HTML page), advice from the ledger, and a status line script."""

import html
import json
import os
import time

import state

STATUSLINE = os.path.join(state.HOME, "statusline.py")
QUIET_CMDS = {"npm", "pip", "pip3", "cargo", "git"}


def _opens_by_cmd(rows):
    """{command: times Claude opened one of its cached originals}."""
    by_file = {r["file"]: r.get("cmd") or r.get("tool") for r in rows if r.get("file")}
    counts = {}
    for o in state.read_ledger(state.OPENS):
        cmd = by_file.get(o.get("file"))
        if cmd:
            counts[cmd] = counts.get(cmd, 0) + 1
    return counts


def _by(rows, key):
    groups = {}
    for r in rows:
        g = groups.setdefault(key(r) or "?", [0, 0])
        g[0] += 1
        g[1] += state.saved_tokens(r)
    return sorted(groups.items(), key=lambda kv: -kv[1][1])


def advise():
    """Plain-language suggestions, each with the command that applies it."""
    rows = state.read_ledger()
    if len(rows) < 10:
        return ["Not enough data yet (%d compressed outputs). Come back after a few sessions." % len(rows)]
    cfg = state.load_config()
    tips = []
    opens = _opens_by_cmd(rows)
    calls = dict((cmd, n) for cmd, (n, _) in _by(rows, lambda r: r.get("cmd")))
    for cmd, n in sorted(opens.items(), key=lambda kv: -kv[1]):
        if n >= 3 and n >= 0.3 * calls.get(cmd, n):
            value = "|".join(p for p in (cfg["passthrough"], cmd) if p)
            tips.append("Claude opened the full output of `%s` %d times out of %d: it needs it whole. "
                        "Leave it uncompressed: /neverbor config passthrough \"%s\"" % (cmd, n, calls.get(cmd, n), value))
    total = sum(state.saved_tokens(r) for r in rows) or 1
    noisy = sum(state.saved_tokens(r) for r in rows if r.get("cmd") in QUIET_CMDS)
    if not state.quiet_enabled() and noisy >= 0.2 * total:
        tips.append("Package and git commands give %d%% of all savings. Quiet flags stop that noise before it "
                    "is even printed: /neverbor quiet on" % (100 * noisy // total))
    share = sum(opens.values()) / len(rows)
    if share > 0.25 and cfg["mode"] != "light":
        tips.append("Claude opens %d%% of the originals, so compression is too strong for your work: "
                    "/neverbor mode light" % (100 * share))
    elif share < 0.03 and len(rows) >= 50 and cfg["mode"] == "normal":
        tips.append("Claude almost never needs the originals (%d%%). You can save more: /neverbor mode aggressive"
                    % (100 * share))
    if not cfg["reread"]:
        tips.append("Pointers instead of re-reading unchanged files are off. Try: /neverbor reread on")
    return tips or ["Everything looks well tuned."]


def _bars(days):
    """Inline SVG bar chart, tokens saved per day."""
    w, h, pad = 720, 220, 30
    peak = max([v for _, v in days] + [1])
    bw = (w - 2 * pad) / max(len(days), 1)
    out = ['<svg viewBox="0 0 %d %d" role="img" aria-label="Tokens saved per day">' % (w, h)]
    for i, (day, v) in enumerate(days):
        bh = (h - 2 * pad) * v / peak
        x, y = pad + i * bw, h - pad - bh
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="2"><title>%s: ≈%d tokens</title></rect>'
                   % (x + 1, y, max(bw - 2, 1), bh, day, v))
        if i % max(len(days) // 6, 1) == 0:
            out.append('<text x="%.1f" y="%d">%s</text>' % (x, h - 8, day[5:]))
    out.append("</svg>")
    return "".join(out)


def write_report(path=None):
    rows = state.read_ledger()
    path = path or os.path.join(state.HOME, "report.html")
    day_totals = {}
    for r in rows:
        day = time.strftime("%Y-%m-%d", time.localtime(r.get("ts", 0)))
        day_totals[day] = day_totals.get(day, 0) + state.saved_tokens(r)
    days = [(time.strftime("%Y-%m-%d", time.localtime(time.time() - d * 86400)), 0) for d in range(29, -1, -1)]
    days = [(d, day_totals.get(d, 0)) for d, _ in days]
    opens = _opens_by_cmd(rows)
    before = sum(r.get("before", 0) for r in rows)
    after = sum(r.get("after", 0) for r in rows)

    def table(items):
        return "".join("<tr><td>%s</td><td>%d</td><td>≈%d</td><td>%d</td></tr>"
                       % (html.escape(k), n, t, opens.get(k, 0)) for k, (n, t) in items[:10])

    page = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Neverbor report</title><style>
:root{--bg:#fbfaf7;--fg:#1f1e1c;--muted:#6b6862;--bar:#d97757;--line:#e6e2da}
@media (prefers-color-scheme:dark){:root{--bg:#1c1b19;--fg:#ece9e3;--muted:#a19d95;--bar:#e08a6c;--line:#34322e}}
body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;max-width:760px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 4px}.muted{color:var(--muted)}.kpis{display:flex;gap:24px;flex-wrap:wrap;margin:20px 0}
.kpi b{display:block;font-size:24px}svg{width:100%%;height:auto}rect{fill:var(--bar)}text{fill:var(--muted);font-size:11px}
table{width:100%%;border-collapse:collapse;margin:8px 0 24px}td,th{text-align:left;padding:6px 4px;border-bottom:1px solid var(--line)}
td:not(:first-child),th:not(:first-child){text-align:right}li{margin:6px 0}
</style></head><body>
<h1>🪶 Neverbor</h1><div class="muted">Report built %s</div>
<div class="kpis"><div class="kpi"><b>≈%s</b>tokens saved</div><div class="kpi"><b>%d</b>outputs compressed</div>
<div class="kpi"><b>%d%%</b>fewer characters</div><div class="kpi"><b>%d</b>originals opened</div></div>
<h2>Last 30 days</h2>%s
<h2>Top commands</h2><table><tr><th>Command</th><th>Calls</th><th>Tokens saved</th><th>Originals opened</th></tr>%s</table>
<h2>Advice</h2><ul>%s</ul></body></html>""" % (
        time.strftime("%Y-%m-%d %H:%M"), "{:,}".format(sum(state.saved_tokens(r) for r in rows)).replace(",", " "),
        len(rows), 100 * (before - after) // max(before, 1), sum(opens.values()), _bars(days),
        table(_by(rows, lambda r: r.get("cmd") or r.get("tool"))), "".join("<li>%s</li>" % html.escape(t) for t in advise()))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    return path


STATUSLINE_CODE = r'''#!/usr/bin/env python3
"""neverbor status line: tokens saved in this session. Installed by `/neverbor statusline`."""
import json, os, sys
ledger = %r
try:
    session = json.loads(sys.stdin.buffer.read().decode("utf-8-sig") or "{}").get("session_id", "")
    start = max(0, os.path.getsize(ledger) - 2000000)  # recent rows are enough for this session
    with open(ledger, "rb") as f:
        f.seek(start)
        lines = f.read().decode("utf-8", "replace").splitlines()[1 if start else 0:]
    rows = [json.loads(l) for l in lines if l.startswith("{")]
    saved = sum(r.get("tok", 0) for r in rows if r.get("session") == session)
    short = "%%.1fM" %% (saved / 1e6) if saved >= 1e6 else "%%.1fk" %% (saved / 1e3) if saved >= 1e3 else saved
    sys.stdout.write("neverbor ~%%s tokens saved" %% short)
except Exception:
    pass
'''


def install_statusline():
    os.makedirs(state.HOME, exist_ok=True)
    with open(STATUSLINE, "w", encoding="utf-8") as f:
        f.write(STATUSLINE_CODE % state.LEDGER)
    return STATUSLINE
