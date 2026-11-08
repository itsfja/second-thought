"""Private files only for you, and settings that can't set LD_PRELOAD and friends (#307)."""
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest

import support
from second_thought.core import _private_open, _write_json
from second_thought.runtime import Runtime
from second_thought import settings

SHOW = ("\nimport os\nprint('ENV', [os.environ.get(k) for k in ('LD_PRELOAD', 'PYTHONSTARTUP', 'DYLD_INSERT_LIBRARIES', 'HTTPS_PROXY', 'RB_CURRENCY')])\n"
        "print('NOTES', Runtime().settings_notes())\n")


@unittest.skipUnless(os.name == "posix", "file modes are a Linux and Mac thing")
class Modes(unittest.TestCase):
    def test_new_and_old_files_become_yours_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "memory.json")
            _write_json(path, {"a": 1})
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
            old = os.path.join(tmp, "journal")
            with open(old, "w") as f:
                f.write("x")
            os.chmod(old, 0o644)
            with _private_open(old, "a") as f:
                f.write("y")
            self.assertEqual(stat.S_IMODE(os.stat(old).st_mode), 0o600)
            with open(old) as f:
                self.assertEqual(f.read(), "xy", "appending keeps what was there")


class Names(unittest.TestCase):
    def run_prog(self, ini, env=None, mode=None):
        runtime = (support.ROOT / "python" / "runtime.py").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            prog = os.path.join(tmp, "prog.py")
            with open(prog, "w", encoding="utf-8") as f:
                f.write(runtime + SHOW)
            ini_path = os.path.join(tmp, "second-thought.ini")
            with open(ini_path, "w", encoding="utf-8") as f:
                f.write(ini)
            if mode is not None:
                os.chmod(ini_path, mode)
            full = {k: v for k, v in os.environ.items() if not k.startswith(("RB_", "ST_", "LD_", "DYLD_", "PYTHON")) and k not in ("HTTPS_PROXY", "SECOND_THOUGHT_INI")}
            full.update(SECOND_THOUGHT_HOME_INI=os.path.join(tmp, "none.ini"), RB_RATES_URL="http://127.0.0.1:9/none", **(env or {}))
            r = subprocess.run([sys.executable, "-I", prog], capture_output=True, text=True, timeout=60, cwd=tmp, env=full)
        out = {line.split(" ", 1)[0]: line.split(" ", 1)[1] for line in r.stdout.splitlines() if line[:5] in ("ENV [", "NOTES")}
        self.assertIn("ENV", out, r.stderr[-600:])
        return out

    def test_start_up_names_are_never_set_and_doctor_says_so(self):
        out = self.run_prog("[keys]\nLD_PRELOAD = /tmp/evil.so\npythonstartup = /tmp/evil.py\nDYLD_INSERT_LIBRARIES = x\n"
                            "HTTPS_PROXY = http://proxy.example:3128\ncurrency = gbp\n", env={"ST_LD_LIBRARY_PATH": "/tmp"})
        self.assertEqual(out["ENV"], "[None, None, None, 'http://proxy.example:3128', 'gbp']")
        for name in ("LD_PRELOAD", "pythonstartup", "DYLD_INSERT_LIBRARIES", "ST_LD_LIBRARY_PATH"):
            self.assertIn(name, out["NOTES"])
        self.assertNotIn("HTTPS_PROXY", out["NOTES"].split("skipped")[1] if "skipped" in out["NOTES"] else "")

    def test_a_misspelt_setting_is_noted(self):
        out = self.run_prog("[run]\ncurrency = gbp\nsave_logg = yes\n[keys]\nANTHROPIC_API_KEY = x\nANTHROPC_API_KEY = y\n"
                            "MODEL_DEFAULT = claude-x\nMCP_GITHUB = github-mcp\nLLAMA_BASE_URL = http://x\n")
        notes = out["NOTES"]
        self.assertIn("save_logg", notes)
        self.assertIn("ANTHROPC_API_KEY", notes)
        for fine in ("currency", "'ANTHROPIC_API_KEY", "MODEL_DEFAULT", "MCP_GITHUB", "LLAMA_BASE_URL"):
            self.assertNotIn(fine + " (", notes)

    @unittest.skipUnless(os.name == "posix", "file modes are a Linux and Mac thing")
    def test_an_ini_others_can_read_is_noted(self):
        self.assertIn("chmod 600", self.run_prog("[run]\ncurrency = gbp\n", mode=0o644)["NOTES"])
        self.assertNotIn("chmod 600", self.run_prog("[run]\ncurrency = gbp\n", mode=0o600)["NOTES"])

    def test_every_name_the_runtime_reads_is_known(self):
        """So --doctor never calls a real setting a spelling mistake."""
        internal = {"GITHUB_ACTIONS", "GITHUB_STEP_SUMMARY", "SECOND_THOUGHT_INI", "SECOND_THOUGHT_HOME_INI"}
        read = set()
        for path in (support.ROOT / "python" / "second_thought").glob("*.py"):
            read |= set(re.findall(r'environ(?:\.get\(|\[)"([A-Z][A-Z0-9_]+)"', path.read_text(encoding="utf-8")))
        unknown = sorted(n for n in read - internal if not Runtime.known_setting(n))
        self.assertEqual(unknown, [])
        self.assertTrue(set(settings.NEVER_SET))


if __name__ == "__main__":
    unittest.main()
