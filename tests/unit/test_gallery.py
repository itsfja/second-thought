"""The community gallery's entries (gallery/*.json): well formed, nothing secret, nothing they can't back up.

The page tests load, run and export every entry, and work out what each one can do from its blocks.
"""
import json
import re
import unittest

import support
from second_thought.settings import RUNTIME_VERSION

FILES = sorted((support.ROOT / "gallery").glob("*.json"))
LIMITS = {"title": 40, "author": 40, "description": 300, "tip": 200}
# Things that look like keys, tokens or passwords. A shared program must never carry one.
SECRETS = [r"sk-[A-Za-z0-9_-]{16,}", r"gh[pousr]_[A-Za-z0-9]{20,}", r"github_pat_\w{20,}", r"xox[abprs]-[A-Za-z0-9-]{10,}",
           r"AKIA[0-9A-Z]{16}", r"AIza[0-9A-Za-z_-]{30,}", r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b", r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}",
           r"(?i)(password|passwd|api[_ ]?key|secret|token)\s*[=:]\s*\S{6,}"]
EMAIL = re.compile(r"[\w.+-]+@([\w-]+\.)+[a-z]{2,}", re.I)


def version(v):
    return tuple(int(x) for x in v.split("."))


def walk(o):
    """Every dict in a saved program, depth first."""
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)


class Entries(unittest.TestCase):
    def test_there_is_at_least_one(self):
        self.assertTrue(FILES)

    def test_files_made_by_gallery_build_match_it(self):
        import subprocess
        import sys
        r = subprocess.run([sys.executable, str(support.ROOT / "tools" / "gallery_build.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_readme_explains_how_to_add_one(self):
        self.assertIn('"gallery"', (support.ROOT / "gallery" / "README.md").read_text(encoding="utf-8"))

    def test_shape(self):
        titles = set()
        for path in FILES:
            with self.subTest(file=path.name):
                self.assertRegex(path.name, r"^[a-z0-9]+(-[a-z0-9]+)*\.json$", "name files in lowercase words joined by -")
                self.assertLess(path.stat().st_size, 100_000, "a gallery program should be well under 100 KB")
                d = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual((d.get("format"), d.get("version")), ("reflection-blocks", 1), "save it from Import / export on the page")
                info, program = d.get("gallery"), d.get("program")
                self.assertIsInstance(info, dict)
                self.assertIsInstance(program, dict)
                self.assertIsInstance(program.get("blocks", {}).get("blocks"), list)
                for field, most in LIMITS.items():
                    value = info.get(field)
                    self.assertTrue(isinstance(value, str) and value.strip(), f"gallery.{field} is missing")
                    self.assertLessEqual(len(value), most, f"gallery.{field} is over {most} characters")
                self.assertIn(info.get("category", "odds"), ("github", "coding", "news", "money", "calendar", "home", "odds"),
                              "gallery.category is one of the groups in gallery/README.md")
                self.assertRegex(info.get("runtime", ""), r"^\d+\.\d+\.\d+$")
                self.assertLessEqual(version(info["runtime"]), version(RUNTIME_VERSION), "made with a runtime newer than this one")
                self.assertNotIn(info["title"].lower(), titles, "two entries have the same title")
                titles.add(info["title"].lower())

    def test_capabilities_are_never_declared(self):
        # The page works them out from the blocks. A list in the entry could only disagree with that.
        for path in FILES:
            with self.subTest(file=path.name):
                d = json.loads(path.read_text(encoding="utf-8"))
                for part in (d, d["gallery"]):
                    self.assertFalse({"can", "capabilities", "CAN"} & set(part), "don't list what it can do; the page works that out")

    def test_stands_alone(self):
        # Running another saved program needs that program, which the person loading this one won't have.
        for path in FILES:
            with self.subTest(file=path.name):
                types = {o["type"] for o in walk(json.loads(path.read_text(encoding="utf-8"))["program"]) if isinstance(o.get("type"), str)}
                self.assertNotIn("rb_run_program", types)

    def test_nothing_secret(self):
        for path in FILES:
            with self.subTest(file=path.name):
                text = path.read_text(encoding="utf-8")
                for pattern in SECRETS:
                    self.assertIsNone(re.search(pattern, text), f"looks like a key or password ({pattern}); take it out")
                for m in EMAIL.finditer(text):
                    self.assertRegex(m.group(0).lower(), r"@example\.(com|org|net)$", "use an @example.com address, not a real one")

    def test_checks_catch_a_key(self):
        text = '{"TEXT": "my key is sk-ant-api03-abcdefghijklmnopqrstuv"}'
        self.assertTrue(any(re.search(p, text) for p in SECRETS))


if __name__ == "__main__":
    unittest.main()
