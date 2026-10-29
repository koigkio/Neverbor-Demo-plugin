"""Draws assets/demo.gif from tests/fixtures/pytest.txt. Needs Pillow and macOS Menlo: python3 assets/make_demo.py"""
import os, sys
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT + "/scripts")
import compress, state
raw = open(ROOT + "/tests/fixtures/pytest.txt").read()
small = compress.compress_text(raw)
W, H = 820, 680
F = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 13)
FB = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 14, index=1)
LH = 17
BG, FG, DIM = (24, 24, 32), (214, 218, 230), (120, 124, 140)
GREEN, RED, ORANGE, YEL = (120, 200, 120), (235, 100, 100), (217, 119, 87), (230, 190, 90)
TOP = 70
ROWS = (H - TOP - 60) // LH

def color(line):
    if "FAILED" in line or line.startswith("E ") or "Error" in line: return RED
    if "PASSED" in line: return GREEN
    if line.strip().startswith("…"): return YEL
    return FG

def frame(title, sub, lines, footer, fcolor):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    for i, c in enumerate([(237, 106, 94), (245, 191, 79), (98, 197, 84)]):
        d.ellipse((16 + i * 20, 14, 28 + i * 20, 26), fill=c)
    d.text((90, 11), title, font=FB, fill=ORANGE if "With" in title and "out" not in title else DIM)
    d.text((16, 40), "●", font=F, fill=ORANGE)
    d.text((34, 40), "Bash(pytest -v)" + sub, font=F, fill=FG)
    for i, l in enumerate(lines[:ROWS]):
        d.text((34, TOP + i * LH), l[:92], font=F, fill=color(l))
    d.rectangle((0, H - 46, W, H), fill=(34, 34, 46))
    d.text((16, H - 34), footer, font=FB, fill=fcolor)
    return im

frames, durs = [], []
rl = raw.splitlines()
toks = state.estimate_tokens(raw)
steps = 28
for s in range(steps + 1):
    end = min(len(rl), ROWS + (len(rl) - ROWS) * s // steps)
    shown = sum(len(l) + 1 for l in rl[:end])
    frames.append(frame("Without Neverbor", "", rl[max(0, end - ROWS):end],
                        "Claude reads %s chars  ≈ %s tokens" % (format(shown, ","), format(shown // 4, ",")), RED))
    durs.append(90)
durs[-1] = 2200
sl = small.splitlines()
tsmall = state.estimate_tokens(small)
saved = 100 * (len(raw) - len(small)) // len(raw)
for k in range(1, len(sl) + 1, 4):
    frames.append(frame("With Neverbor", "", sl[:k], "compressing…", DIM)); durs.append(60)
frames.append(frame("With Neverbor", "", sl, "Claude reads %s chars  ≈ %s tokens   −%d%%   (original saved to disk)"
                    % (format(len(small), ","), format(len(small) // 4, ","), saved), GREEN))
durs.append(4500)
out = ROOT + "/assets/demo.gif"
frames[0].save(out, save_all=True, append_images=frames[1:], duration=durs, loop=0, optimize=True)
frames[-1].save(os.path.dirname(os.path.abspath(__file__)) + "/last.png")
frames[10].save(os.path.dirname(os.path.abspath(__file__)) + "/mid.png")
print(os.path.getsize(out), len(frames), ROWS, len(sl), saved)
