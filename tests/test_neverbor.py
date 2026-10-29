"""Run: python3 -m unittest discover -s tests"""

import json
import os
import shutil
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


FIXTURES = os.path.join(ROOT, "tests", "fixtures")


def fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return f.read()


def run_script(script, payload, home, **env):
    env = dict(os.environ, NEVERBOR_HOME=home, **env)
    env.pop("NEVERBOR_PASSTHROUGH", None)
    p = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", script)],
        input=json.dumps(payload), capture_output=True, text=True, env=env,
    )
    return json.loads(p.stdout) if p.stdout.strip() else None


def run_hook(payload, home):
    return run_script("post_tool.py", payload, home)


def bash(command, stdout, session="s1"):
    resp = {"stdout": stdout, "stderr": "", "interrupted": False, "isImage": False}
    return {"session_id": session, "tool_name": "Bash", "tool_input": {"command": command}, "tool_response": resp}


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


class FormatTest(unittest.TestCase):
    def test_pytest_keeps_failures_and_summary(self):
        text = fixture("pytest.txt")
        out = compress.compress_text(text)
        self.assertLess(len(out), len(text) * 0.15)
        self.assertIn("test_case_097 FAILED", out)
        self.assertIn("AssertionError: assert '12' == 12", out)
        self.assertIn("2 failed, 312 passed", out)
        self.assertNotIn("test_case_001 PASSED", out)

    def test_jest_keeps_failure(self):
        out = compress.compress_text(fixture("jest.txt"))
        self.assertIn("✕ renders the empty state", out)
        self.assertIn("Tests:       1 failed, 167 passed, 168 total", out)
        self.assertIn("passing test lines", out)

    def test_traceback_library_frames_collapsed(self):
        out = compress.compress_text(fixture("traceback.txt"))
        self.assertIn("library frames", out)
        self.assertIn('File "/work/app/db.py", line 44', out)
        self.assertIn("UndefinedTable", out)

    def test_install_noise_collapsed_warnings_kept(self):
        text = fixture("pip_install.txt")
        out = compress.compress_text(text)
        self.assertLess(len(out), len(text) * 0.2)
        self.assertIn("WARNING: package-17", out)
        self.assertIn("Successfully installed", out)

    def test_diff_only_when_enabled(self):
        text = fixture("git_diff.txt")
        out = compress.compress_text(text, {"compress_diff": True})
        for line in ("-    timeout = 30", "+    timeout = 60", "-    retries = 1", "+    retries = 3", "@@ -1,140 +1,140 @@"):
            self.assertIn(line, out)
        self.assertIn("unchanged lines", out)
        self.assertNotIn("line_060", out)

    def test_light_mode_skips_json_and_truncation(self):
        items = json.dumps([{"id": i} for i in range(500)], indent=2)
        self.assertIsNone(compress.compress_text(items, {"light": True}))
        self.assertNotIn("library frames", compress.compress_text(fixture("traceback.txt"), {"light": True}) or "")


class SessionTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()

    def test_repeat_replaced_with_pointer(self):
        text = "result line\n" + "x" * 400
        self.assertIsNone(run_hook(bash("npm test", text), self.home))
        out = run_hook(bash("npm test", text), self.home)
        new = out["hookSpecificOutput"]["updatedToolOutput"]
        self.assertIn("identical to the same command", new["stdout"])
        # Different session or different output: shown in full.
        self.assertIsNone(run_hook(bash("npm test", text, session="s2"), self.home))
        self.assertIsNone(run_hook(bash("npm test", text + "!"), self.home))

    def test_compaction_forgets_repeats(self):
        text = "y" * 500
        run_hook(bash("make", text), self.home)
        run_script("session_start.py", {"session_id": "s1", "source": "compact"}, self.home)
        self.assertIsNone(run_hook(bash("make", text), self.home))

    def test_stop_reports_only_new_savings(self):
        run_hook(bash("npm run build", BUILD_LOG), self.home)
        msg = run_script("stop.py", {"session_id": "s1"}, self.home)
        self.assertIn("neverbor:", msg["systemMessage"])
        self.assertIsNone(run_script("stop.py", {"session_id": "s1"}, self.home))

    def test_stop_language(self):
        with open(os.path.join(self.home, "config.json"), "w") as f:
            json.dump({"lang": "ru"}, f)
        run_hook(bash("npm run build", BUILD_LOG), self.home)
        self.assertIn("сэкономлено", run_script("stop.py", {"session_id": "s1"}, self.home)["systemMessage"])


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()

    def write(self, text):
        with open(os.path.join(self.home, "config.json"), "w") as f:
            f.write(text)

    def test_broken_config_uses_defaults(self):
        self.write("{not json")
        out = run_hook(bash("npm run build", BUILD_LOG), self.home)
        self.assertIn("[neverbor:", out["hookSpecificOutput"]["updatedToolOutput"]["stdout"])

    def test_min_chars_from_config(self):
        self.write(json.dumps({"min_chars": 10 ** 6}))
        self.assertIsNone(run_hook(bash("npm run build", BUILD_LOG), self.home))

    def test_passthrough_from_config(self):
        self.write(json.dumps({"passthrough": "kubectl"}))
        self.assertIsNone(run_hook(bash("kubectl logs api", BUILD_LOG), self.home))

    def test_git_diff_compressed_only_with_flag(self):
        diff = fixture("git_diff.txt")
        self.assertIsNone(run_hook(bash("git diff", diff), self.home))
        self.write(json.dumps({"compress_diff": True}))
        out = run_hook(bash("git diff", diff, session="s9"), self.home)
        self.assertIn("unchanged lines", out["hookSpecificOutput"]["updatedToolOutput"]["stdout"])


class QuietTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()

    def pre(self, command, **env):
        payload = {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": command, "description": "d"}}
        return run_script("pre_tool.py", payload, self.home, **env)

    def test_off_by_default(self):
        self.assertIsNone(self.pre("npm install"))

    def test_rewrite_asks_for_approval(self):
        open(os.path.join(self.home, "quiet-on"), "w").close()
        out = self.pre("pip install requests")["hookSpecificOutput"]
        self.assertEqual(out["permissionDecision"], "ask")
        self.assertEqual(out["updatedInput"], {"command": "pip install requests -q", "description": "d"})

    def test_compound_and_already_quiet_untouched(self):
        open(os.path.join(self.home, "quiet-on"), "w").close()
        for command in ("npm install && rm -rf x", "pip install -q x", "npm install $(cat list)", "git clone a | tee"):
            self.assertIsNone(self.pre(command), command)


class PlatformTest(unittest.TestCase):
    """Windows consoles often use cp1252; hooks must still read and write UTF-8 data."""

    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.env = dict(os.environ, NEVERBOR_HOME=self.home, PYTHONIOENCODING="cp1252")

    def run_bytes(self, args, payload):
        p = subprocess.run(args, input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                           capture_output=True, env=self.env)
        return p.returncode, p.stdout

    def test_hook_with_cyrillic_under_cp1252(self):
        log = BUILD_LOG + "\nОшибка сборки → смотри лог"
        payload = bash("npm run build", log)
        code, out = self.run_bytes([sys.executable, os.path.join(ROOT, "scripts", "post_tool.py")], payload)
        self.assertEqual(code, 0)
        stdout = json.loads(out.decode("ascii"))["hookSpecificOutput"]["updatedToolOutput"]["stdout"]
        self.assertIn("Ошибка сборки → смотри лог", stdout)

    def test_cli_under_cp1252(self):
        run_hook(bash("npm run build", BUILD_LOG), self.home)
        p = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "neverbor.py"), "stats"],
                           capture_output=True, env=self.env)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("→", p.stdout.decode("utf-8"))

    @unittest.skipIf(shutil.which("sh") is None, "no sh")
    def test_launcher_runs_hook(self):
        code, out = self.run_bytes(["sh", os.path.join(ROOT, "scripts", "run.sh"), "post_tool.py"],
                                   bash("npm run build", BUILD_LOG))
        self.assertEqual(code, 0)
        self.assertIn(b"updatedToolOutput", out)


class JournalTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.cwd = tempfile.mkdtemp()
        self.file = os.path.join(self.cwd, "app.py")
        with open(self.file, "w") as f:
            f.write("print(1)\n")

    def tool(self, name, tool_input, resp=None):
        return run_script("post_tool.py", {"session_id": "s1", "tool_name": name, "tool_input": tool_input,
                                           "tool_response": resp or {}}, self.home)

    def fail(self, command, error="npm ERR! missing script: tset"):
        return run_script("failure.py", {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": command},
                                         "error": "Exit code 1\n" + error}, self.home)

    def compact(self):
        out = run_script("session_start.py", {"session_id": "s1", "source": "compact", "cwd": self.cwd}, self.home)
        return out["hookSpecificOutput"]["additionalContext"]

    def test_brief_after_compact(self):
        self.tool("Edit", {"file_path": self.file})
        self.tool("Edit", {"file_path": self.file})
        self.tool("Bash", {"command": "npm run build"}, {"stdout": "ok", "stderr": ""})
        self.fail("npm run tset")
        ctx = self.compact()
        self.assertIn("app.py (×2)", ctx)
        self.assertIn("`npm run build` → ok", ctx)
        self.assertIn("`npm run tset` → FAILED: npm ERR! missing script: tset", ctx)

    def test_no_brief_on_fresh_start(self):
        out = run_script("session_start.py", {"session_id": "s1", "source": "startup"}, self.home)
        self.assertNotIn("work log", out["hookSpecificOutput"]["additionalContext"])

    def test_loop_hint_after_three_same_failures(self):
        self.assertIsNone(self.fail("npm run tset"))
        self.assertIsNone(self.fail("npm run tset"))
        out = self.fail("npm run tset")
        self.assertIn("failed 3 times in a row", out["hookSpecificOutput"]["additionalContext"])

    def test_loop_counter_resets_on_new_error_or_success(self):
        self.fail("make")
        self.fail("make")
        self.assertIsNone(self.fail("make", "error: other thing"))
        self.tool("Bash", {"command": "make"}, {"stdout": "ok", "stderr": ""})
        self.assertIsNone(self.fail("make", "error: other thing"))

    def read(self, **extra):
        resp = {"type": "text", "file": {"filePath": self.file, "content": "print(1)\n", "numLines": 1,
                                         "startLine": 1, "totalLines": 1}}
        out = self.tool("Read", dict(file_path=self.file, **extra), resp)
        return out and out["hookSpecificOutput"]["updatedToolOutput"]["file"]["content"]

    def test_reread_off_by_default(self):
        self.read()
        self.assertIsNone(self.read())

    def test_reread_pointer_once_then_full(self):
        subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "neverbor.py"), "reread", "on"],
                       capture_output=True, env=dict(os.environ, NEVERBOR_HOME=self.home))
        self.assertIsNone(self.read())
        self.assertIn("unchanged since", self.read())
        self.assertIsNone(self.read())  # asked again right away: show it
        self.assertIsNone(self.read(offset=1, limit=5))
        self.tool("Edit", {"file_path": self.file})
        self.assertIsNone(self.read())  # edited: full again


class MapTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.root = tempfile.mkdtemp()
        for rel in ("src/a.ts", "src/b.ts", "node_modules/x/index.js", "Makefile", "package.json"):
            os.makedirs(os.path.join(self.root, os.path.dirname(rel)), exist_ok=True)
            with open(os.path.join(self.root, rel), "w") as f:
                f.write({"Makefile": "build:\n\tcc\ntest:\n\tcc\n",
                         "package.json": '{"scripts": {"dev": "vite"}}'}.get(rel, ""))

    def start(self, source="startup"):
        out = run_script("session_start.py", {"session_id": "s1", "source": source, "cwd": self.root}, self.home)
        return out["hookSpecificOutput"]["additionalContext"]

    def test_map_off_by_default(self):
        self.assertNotIn("project map", self.start())

    def test_map_on_start(self):
        with open(os.path.join(self.home, "config.json"), "w") as f:
            json.dump({"map_on_start": True}, f)
        ctx = self.start()
        self.assertIn("project map", ctx)
        self.assertIn("src/ (2)", ctx)
        self.assertNotIn("node_modules", ctx)
        self.assertIn("make targets: build, test", ctx)
        self.assertIn("dev (`vite`)", ctx)
        self.assertNotIn("project map", self.start("resume"))


if __name__ == "__main__":
    unittest.main()
