"""tools/gallery_from_issue.py: an accepted "Share a program" issue becomes gallery/<name>.json (#437)."""
import base64
import json
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

import support
from second_thought.settings import RUNTIME_VERSION

ROOT = support.ROOT
sys.path.insert(0, str(ROOT / "tools"))
import gallery_from_issue as gfi  # noqa: E402

PROGRAM = {"blocks": {"languageVersion": 0, "blocks": [
    {"type": "rb_start", "next": {"block": {"type": "rb_say", "inputs": {"TEXT": {"shadow": {"type": "text", "fields": {"TEXT": "hi"}}}}}}}]}}


def pack(program, version=1, name="x", envelope=False):
    """Pack a program the way the page's Copy link does (#436): deflate-raw of the compact JSON, in base64url."""
    payload = {"version": version, "name": name, "program": program}
    if envelope:
        payload = {"format": "reflection-blocks", **payload}
    raw = zlib.compress(json.dumps(payload, separators=(",", ":")).encode(), 9, -15)
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def body(link, **over):
    fields = {"Title": "Bake-day timeline", "Category": "Community: home and baking",
              "Description": "Works backwards from the oven time.", "Tip": "Change the recipe first.",
              "Author": "Francis", "File name": "zz-test-share", "Runtime": RUNTIME_VERSION, "Program link": link}
    fields.update(over)
    return "Intro text\n\n" + "".join(f"### {k}\n\n{v}\n\n" for k, v in fields.items())


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_gallery = gfi.GALLERY
        gfi.GALLERY = Path(self._tmp.name)
        (gfi.GALLERY / "airport-leave-time.json").write_text("{}", encoding="utf-8")  # for the "already exists" case

    def tearDown(self):
        gfi.GALLERY = self._old_gallery
        self._tmp.cleanup()


class Parse(Base):
    def test_fields_from_an_issue_body(self):
        f = gfi.parse_fields(body("https://x.test/#p=" + pack(PROGRAM)))
        self.assertEqual(f["title"], "Bake-day timeline")
        self.assertEqual(f["category"], "Community: home and baking")
        self.assertEqual(f["name"], "zz-test-share")
        self.assertEqual(f["runtime"], RUNTIME_VERSION)
        self.assertTrue(f["link"].startswith("https://x.test/#p="))

    def test_unpack_link(self):
        version, name, program = gfi.unpack_link("https://itsfja.github.io/second-thought/#p=" + pack(PROGRAM, 2, "pie"))
        self.assertEqual((version, name), (2, "pie"))
        self.assertEqual(program, PROGRAM)

    def test_unpack_link_accepts_a_whole_block_file(self):
        version, name, program = gfi.unpack_link("#p=" + pack(PROGRAM, envelope=True))
        self.assertEqual(program, PROGRAM)

    def test_bad_links_are_refused(self):
        for bad in ("", "https://x.test/", "https://x.test/#p=!!!", "https://x.test/#p=" + pack(PROGRAM)[:-4]):
            with self.assertRaises(SystemExit, msg=bad[:40]):
                gfi.unpack_link(bad)


class Build(Base):
    def entry(self, link=None, **over):
        link = link or ("https://x.test/#p=" + pack(PROGRAM))
        fields = gfi.parse_fields(body(link, **over))
        version, _, program = gfi.unpack_link(fields["link"])
        return gfi.build_entry(fields, version, "", program)

    def test_a_good_issue_makes_a_gallery_entry(self):
        e = self.entry()
        self.assertEqual((e["format"], e["name"]), ("reflection-blocks", "zz-test-share"))
        self.assertEqual(e["gallery"], {"title": "Bake-day timeline", "category": "home",
                                        "description": "Works backwards from the oven time.", "tip": "Change the recipe first.",
                                        "author": "Francis", "runtime": RUNTIME_VERSION})
        self.assertEqual(e["program"], PROGRAM)

    def test_category_accepts_the_key_too(self):
        self.assertEqual(self.entry(**{"Category": "news"})["gallery"]["category"], "news")

    def test_problems_are_refused(self):
        cases = [
            ({"Title": ""}, "empty"),
            ({"Title": "x" * 41}, "over 40"),
            ({"File name": "Bake-Day"}, "lowercase words"),
            ({"File name": "airport-leave-time"}, "already exists"),
            ({"Category": "Community: space"}, "one of"),
            ({"Runtime": "tomorrow"}, "3.13.0"),
            ({"Runtime": "99.0.0"}, "newer than"),
        ]
        for over, why in cases:
            with self.assertRaises(SystemExit, msg=str(over)) as cm:
                self.entry(**over)
            self.assertIn(why, str(cm.exception), over)

    def test_a_secret_or_a_real_email_or_a_subprogram_is_refused(self):
        secret = json.loads(json.dumps(PROGRAM))
        secret["blocks"]["blocks"][0]["next"]["block"]["inputs"]["TEXT"]["shadow"]["fields"]["TEXT"] = "key sk-abcdefghijklmnop123456"
        with self.assertRaises(SystemExit) as cm:
            self.entry(link="https://x.test/#p=" + pack(secret))
        self.assertIn("key or password", str(cm.exception))
        email = json.loads(json.dumps(PROGRAM))
        email["blocks"]["blocks"][0]["next"]["block"]["inputs"]["TEXT"]["shadow"]["fields"]["TEXT"] = "mail me at francis@anthropic.com"
        with self.assertRaises(SystemExit) as cm:
            self.entry(link="https://x.test/#p=" + pack(email))
        self.assertIn("email", str(cm.exception))
        sub = json.loads(json.dumps(PROGRAM))
        sub["blocks"]["blocks"][0]["next"]["block"] = {"type": "rb_run_program", "fields": {"NAME": "other"}}
        with self.assertRaises(SystemExit) as cm:
            self.entry(link="https://x.test/#p=" + pack(sub))
        self.assertIn("stand alone", str(cm.exception))


class Cli(Base):
    def test_dry_run_prints_the_summary(self):
        import subprocess
        out = subprocess.run([sys.executable, str(ROOT / "tools" / "gallery_from_issue.py"), "--body", body("https://x.test/#p=" + pack(PROGRAM))],
                             capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(out.returncode, 0, out.stderr)
        summary = json.loads(out.stdout.strip().splitlines()[-1])
        self.assertEqual((summary["name"], summary["title"], summary["written"]), ("zz-test-share", "Bake-day timeline", False))

    def test_write_makes_the_file(self):
        import contextlib, io
        argv = sys.argv
        sys.argv = ["gallery_from_issue.py", "--body", body("https://x.test/#p=" + pack(PROGRAM)), "--write"]
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                gfi.main()
        finally:
            sys.argv = argv
        written = json.loads((gfi.GALLERY / "zz-test-share.json").read_text(encoding="utf-8"))
        self.assertEqual(written["gallery"]["category"], "home")
        self.assertEqual(written["program"], PROGRAM)


if __name__ == "__main__":
    unittest.main()
