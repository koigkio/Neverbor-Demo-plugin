"""Quality check: for real outputs, the facts a developer would ask about must survive compression.

Each case is (output, [strings the compressed text must still contain]).
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import compress  # noqa: E402
from test_neverbor import fixture  # noqa: E402

PS_AUX = "\n".join(
    ["USER   PID  %CPU %MEM    VSZ   RSS TTY STAT START TIME COMMAND"]
    + ["app   %d   0.%d  1.2 %d  %d ?   Ss   10:00 0:0%d node server.js --port %d"
       % (1000 + i, i % 10, 400000 + i, 50000 + i, i % 10, 3000 + i) for i in range(120)]
)

FIND = "\n".join(
    ["./src/components/Button%d.tsx" % i for i in range(300)]
    + ["./src/api/payments/stripe.ts", "./src/api/payments/refund.ts"]
    + ["./node_modules/react/cjs/react.%d.js" % i for i in range(400)]
    + ["./docs/README.md"]
)

CASES = {
    "pytest": (fixture("pytest.txt"), [
        "test_case_097", "test_case_203", "AssertionError: assert '12' == 12",
        "KeyError: 'orders'", "tests/test_views.py:88"]),
    "jest": (fixture("jest.txt"), ["Widget07.test.tsx", "1 failed, 167 passed"]),
    "traceback": (fixture("traceback.txt"), ['relation "orders" does not exist']),
    "find": (FIND, ["src/components/", "src/api/payments/stripe.ts", "src/api/payments/refund.ts",
                    "node_modules/react/cjs/", "docs/README.md", "300 entries"]),
}


class QualityTest(unittest.TestCase):
    def test_facts_survive(self):
        for name, (text, facts) in CASES.items():
            out = compress.compress_text(text) or text
            for fact in facts:
                with self.subTest(case=name, fact=fact):
                    self.assertIn(fact, out)

    def test_numeric_rows_not_collapsed(self):
        """Every port in a process list is data; none may disappear into "similar lines"."""
        out = compress.compress_text(PS_AUX) or PS_AUX
        lines = compress.dedupe_runs(PS_AUX.split("\n"))
        self.assertEqual(len(lines), len(PS_AUX.split("\n")))
        self.assertNotIn("similar lines", "\n".join(lines))
        self.assertIn("--port 3000", out)

    def test_similar_run_names_skipped_range(self):
        lines = ["[info] compiling module_%d of the frontend bundle" % i for i in range(20)]
        out = compress.dedupe_runs(lines)
        self.assertIn("(17 similar lines (2…18))", "\n".join(out))

    def test_short_similar_run_kept(self):
        lines = ["worker %d started on the default queue" % i for i in range(5)]
        self.assertEqual(compress.dedupe_runs(lines), lines)


if __name__ == "__main__":
    unittest.main()
