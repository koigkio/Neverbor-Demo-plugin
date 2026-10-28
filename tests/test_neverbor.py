"""Run: python3 -m unittest discover -s tests"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import compress  # noqa: E402

BUILD_LOG = "\n".join(
    ["\x1b[32m[%04d] compiling module_%d.ts ... ok\x1b[0m" % (i, i) for i in range(400)]
    + ["src/api/user.ts:42:7 - error TS2322: Type 'string' is not assignable to type 'number'."]
    + ["[%04d] compiling module_%d.ts ... ok" % (i, i) for i in range(400, 800)]
    + ["Build finished with 1 error."]
)


def run_hook(payload, home):
    env = dict(os.environ, NEVERBOR_HOME=home)
    p = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "post_tool.py")],
        input=json.dumps(payload), capture_output=True, text=True, env=env,
    )
    return json.loads(p.stdout) if p.stdout.strip() else None


class CompressTest(unittest.TestCase):
    def test_small_output_untouched(self):
        self.assertIsNone(compress.compress_text("hello\n" * 10))

    def test_build_log_keeps_error_and_tail(self):
        out = compress.compress_text(BUILD_LOG)
        self.assertLess(len(out), len(BUILD_LOG) * 0.1)
        self.assertIn("error TS2322", out)
        self.assertIn("Build finished with 1 error.", out)
        self.assertNotIn("\x1b[", out)

    def test_json_array_sampled_and_minified(self):
        items = [{"id": i, "title": "Issue %d" % i, "state": "open"} for i in range(200)]
        items[120]["state"] = "error: build failed"
        text = json.dumps(items, indent=2)
        out = compress.compress_text(text)
        self.assertIn("error: build failed", out)
        self.assertIn("items omitted", out)
        json.loads(out)  # still valid JSON

    def test_progress_bars_collapse(self):
        text = "\r".join("Downloading %d%%" % i for i in range(101)) + "\ndone\n" + "x " * 2000
        out = compress.compress_text(text) or text
        self.assertNotIn("Downloading 50%", out)


class HookTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()

    def test_bash_output_replaced_and_original_saved(self):
        resp = {"stdout": BUILD_LOG, "stderr": "", "interrupted": False, "isImage": False}
        out = run_hook({"tool_name": "Bash", "tool_input": {"command": "npm run build"}, "tool_response": resp}, self.home)
        new = out["hookSpecificOutput"]["updatedToolOutput"]
        self.assertEqual(set(new), set(resp))
        self.assertIn("[neverbor:", new["stdout"])
        cached = os.listdir(os.path.join(self.home, "cache"))
        self.assertEqual(len(cached), 1)
        with open(os.path.join(self.home, "cache", cached[0])) as f:
            self.assertEqual(f.read(), BUILD_LOG)

    def test_cat_passthrough(self):
        resp = {"stdout": BUILD_LOG, "stderr": "", "interrupted": False, "isImage": False}
        self.assertIsNone(run_hook({"tool_name": "Bash", "tool_input": {"command": "cd x && cat build.log"}, "tool_response": resp}, self.home))

    def test_mcp_blocks(self):
        resp = [{"type": "text", "text": BUILD_LOG}, {"type": "image", "data": "..."}]
        out = run_hook({"tool_name": "mcp__ci__logs", "tool_input": {}, "tool_response": resp}, self.home)
        blocks = out["hookSpecificOutput"]["updatedToolOutput"]
        self.assertIn("error TS2322", blocks[0]["text"])
        self.assertEqual(blocks[1], resp[1])

    def test_off_flag(self):
        open(os.path.join(self.home, "off"), "w").close()
        resp = {"stdout": BUILD_LOG, "stderr": "", "interrupted": False, "isImage": False}
        self.assertIsNone(run_hook({"tool_name": "Bash", "tool_input": {"command": "make"}, "tool_response": resp}, self.home))

    def test_garbage_input_fails_open(self):
        p = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "post_tool.py")],
                           input="not json", capture_output=True, text=True)
        self.assertEqual((p.returncode, p.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
