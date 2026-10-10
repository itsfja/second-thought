"""The runtime's version: a proper version number, the same one CHANGELOG.md lists, and shown by --version."""
import os
import re
import subprocess
import sys
import tempfile
import unittest

import support
from second_thought.settings import RUNTIME_VERSION


class Version(unittest.TestCase):
    def test_is_semantic(self):
        self.assertRegex(RUNTIME_VERSION, r"^\d+\.\d+\.\d+$")

    def test_changelog_lists_it_first(self):
        text = (support.ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("## Unreleased", text)
        released = re.findall(r"^## (\d+\.\d+\.\d+) - \d{4}-\d{2}-\d{2}$", text, re.M)
        self.assertTrue(released, "CHANGELOG.md has no '## 1.2.3 - YYYY-MM-DD' headings")
        self.assertEqual(released[0], RUNTIME_VERSION, "the newest version in CHANGELOG.md isn't RUNTIME_VERSION in settings.py")

    def test_readme_badge_shows_it(self):
        text = (support.ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(f"img.shields.io/badge/runtime-{RUNTIME_VERSION}-", text, "the runtime badge at the top of README.md is out of date")

    def test_bundle_has_it(self):
        text = (support.ROOT / "python" / "runtime.py").read_text(encoding="utf-8")
        self.assertIn(f'RUNTIME_VERSION = "{RUNTIME_VERSION}"', text, "python/runtime.py is out of date: run python tools/sync.py")

    def test_exported_program_prints_it(self):
        runtime = (support.ROOT / "python" / "runtime.py").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            prog = os.path.join(tmp, "prog.py")
            with open(prog, "w", encoding="utf-8") as f:
                f.write(runtime + "\nR = Runtime()\nR.main([], {}, [])\n")
            r = subprocess.run([sys.executable, "-I", prog, "--version"], capture_output=True, text=True, timeout=60,
                               cwd=tmp, env=dict(os.environ))
        self.assertEqual((r.returncode, r.stdout.strip()), (0, f"Second Thought runtime {RUNTIME_VERSION}"), r.stderr[-300:])


if __name__ == "__main__":
    unittest.main()
