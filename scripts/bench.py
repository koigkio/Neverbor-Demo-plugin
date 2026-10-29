#!/usr/bin/env python3
"""Reproduce the README numbers: `python3 scripts/bench.py` compresses every file in tests/fixtures."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import compress  # noqa: E402
import state  # noqa: E402

FIXTURES = os.path.join(ROOT, "tests", "fixtures")


def main():
    print("| Fixture | Before, chars | After, chars | Saved | ≈ tokens saved |")
    print("|---|---:|---:|---:|---:|")
    for name in sorted(os.listdir(FIXTURES)):
        with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
            text = f.read()
        cfg = {"compress_diff": True} if "diff" in name else None
        out = compress.compress_text(text, cfg) or text
        label = name + (" (compress_diff on)" if cfg else "")
        print("| %s | %d | %d | −%.0f%% | %d |" % (
            label, len(text), len(out), 100.0 * (len(text) - len(out)) / len(text),
            state.estimate_tokens(text) - state.estimate_tokens(out)))


if __name__ == "__main__":
    main()
