"""A newer runtime (#244): --doctor says when one is out, and --update-runtime puts it into the program file in place.

A stand-in for GitHub's releases API runs on this computer; RB_RELEASES_URL points the runtime at it.
"""
import hashlib
import http.server
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import unittest

import support
from second_thought import update
from second_thought.runtime import Runtime
from second_thought.settings import RUNTIME_VERSION

RUNTIME = (support.ROOT / "python" / "runtime.py").read_text(encoding="utf-8")
MAJOR, MINOR, PATCH = (int(x) for x in RUNTIME_VERSION.split("."))
NEXT = f"{MAJOR}.{MINOR}.{PATCH + 1}"
PROGRAM_MARK = update.PROGRAM_MARKS[0]


def as_version(runtime, version):
    return re.sub(r'^RUNTIME_VERSION = "[^"]+"', f'RUNTIME_VERSION = "{version}"', runtime, count=1, flags=re.M)


class Releases:
    """Serves a releases list and its files: files maps a path to bytes; releases is the list served at /releases."""

    def __init__(self):
        self.files, self.releases = {}, []
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                path = self.path.split("?")[0]
                body = json.dumps(outer.releases).encode() if path == "/releases" else outer.files.get(path)
                self.send_response(200 if body is not None else 404)
                self.end_headers()
                self.wfile.write(body or b"")

            def log_message(self, *a):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def release(self, version, runtime=None, body="", sha=None, draft=False):
        rel = {"tag_name": "v" + version, "draft": draft, "prerelease": False, "body": body,
               "html_url": f"https://github.com/itsfja/second-thought/releases/tag/v{version}", "assets": []}
        if runtime is not None:
            data = runtime.encode("utf-8")
            self.files[f"/{version}/runtime.py"] = data
            self.files[f"/{version}/runtime.py.sha256"] = f"{sha or hashlib.sha256(data).hexdigest()}  runtime.py\n".encode()
            rel["assets"] = [{"name": "runtime.py", "browser_download_url": f"{self.url}/{version}/runtime.py"},
                             {"name": "runtime.py.sha256", "browser_download_url": f"{self.url}/{version}/runtime.py.sha256"}]
        self.releases.append(rel)
        return rel

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def exported(runtime, crlf=False):
    """A program file shaped like the page's export: notes, the runtime, the program, then its blocks and code hash."""
    code = ('"""My program.\n\nExported from Second Thought."""\n\n' + runtime.lstrip("\n") + "\n"
            + "# Your program\nR = Runtime()\nSTART_SCRIPTS = []\nCAN = {\"services\": [], \"can\": []}\n\n"
            + "if __name__ == \"__main__\":\n    R.main(START_SCRIPTS, {}, [], can=CAN)\n")
    text = code.rstrip("\n") + "\n\n\n" + PROGRAM_MARK + "\n# CODE-HASH: " + update.code_hash(code) + "\n# BLOCKS:\n# eyJmb3JtYXQiOiJ4In0=\n"
    return text.replace("\n", "\r\n") if crlf else text


class Pieces(unittest.TestCase):
    def test_code_hash_matches_the_page(self):
        # The same answers as the page's codeHash(): tests/editor/update-runtime.test.cjs checks them there.
        cases = json.loads((support.ROOT / "tests" / "parity" / "code_hash.json").read_text(encoding="utf-8"))["answers"]
        for text, want in cases:
            self.assertEqual(update.code_hash(text), want, repr(text))
        self.assertEqual(update.code_hash("print('hi')  \r\n\n\n"), update.code_hash("print('hi')"))

    def test_the_page_finds_its_mark_after_the_runtime(self):
        # The page looks for this line anywhere in the file (readExported), so the runtime must never contain it.
        for mark in update.PROGRAM_MARKS:
            self.assertNotIn(mark, RUNTIME)

    def test_the_runtime_is_marked_first_and_last(self):
        self.assertEqual(update.runtime_span(RUNTIME), (0, len(RUNTIME.rstrip("\n"))))
        self.assertTrue(RUNTIME.startswith(update.RUNTIME_START + "\n"))

    def test_security_fix_is_a_heading(self):
        self.assertTrue(update.security_fix("## 3.0.2\n\n### Security\n- Closed a gap."))
        self.assertFalse(update.security_fix("### Fixed\n- Better security wording."))

    def test_swap_keeps_the_program_and_its_hash_right(self):
        old = exported(as_version(RUNTIME, "0.0.1"))
        new = update.with_runtime(old, RUNTIME)
        self.assertIn(f'RUNTIME_VERSION = "{RUNTIME_VERSION}"', new)
        self.assertNotIn('RUNTIME_VERSION = "0.0.1"', new)
        self.assertEqual(new.split(update.RUNTIME_END)[1], old.split(update.RUNTIME_END)[1].replace(
            re.search(r"CODE-HASH: (\w+)", old).group(1), re.search(r"CODE-HASH: (\w+)", new).group(1)))
        at = new.index(PROGRAM_MARK)
        self.assertEqual(re.search(r"CODE-HASH: (\w+)", new).group(1), update.code_hash(new[:at]))

    def test_an_edited_file_stays_marked_as_edited(self):
        old = exported(as_version(RUNTIME, "0.0.1")).replace("START_SCRIPTS = []", "START_SCRIPTS = []  # mine")
        new = update.with_runtime(old, RUNTIME)
        self.assertEqual(re.search(r"CODE-HASH: (\w+)", new).group(1), re.search(r"CODE-HASH: (\w+)", old).group(1))

    def test_unmarked_files_are_left_alone(self):
        self.assertIsNone(update.with_runtime("print('no runtime here')\n", RUNTIME))


class Doctor(unittest.TestCase):
    def setUp(self):
        self.gh = Releases()
        os.environ["RB_RELEASES_URL"] = self.gh.url + "/releases"
        self.rt = Runtime()

    def tearDown(self):
        self.gh.close()
        for k in ("RB_RELEASES_URL", "RB_UPDATE_CHECK"):
            os.environ.pop(k, None)

    def test_latest(self):
        self.gh.release(RUNTIME_VERSION)
        self.gh.release(f"{MAJOR}.{MINOR}.{PATCH + 5}", draft=True)
        self.assertEqual(self.rt.update_status()[0], "ok")

    def test_newer_patch_is_a_note(self):
        self.gh.release(NEXT, body="### Fixed\n- A thing.")
        status, text = self.rt.update_status()
        self.assertEqual(status, "NOTE")
        self.assertIn(NEXT, text)
        self.assertIn("--update-runtime", text)

    def test_security_fix_fails(self):
        self.gh.release(f"{MAJOR}.{MINOR}.{PATCH + 2}")
        self.gh.release(NEXT, body="### Security\n- Closed a gap.")
        status, text = self.rt.update_status()
        self.assertEqual(status, "FAIL")
        self.assertIn(f"{MAJOR}.{MINOR}.{PATCH + 2}", text)

    def test_new_major_says_to_export_again(self):
        self.gh.release(f"{MAJOR + 1}.0.0")
        status, text = self.rt.update_status()
        self.assertEqual(status, "NOTE")
        self.assertIn("export it again", text)

    def test_offline_is_a_note(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        os.environ["RB_RELEASES_URL"] = f"http://127.0.0.1:{port}/releases"
        self.assertEqual(self.rt.update_status()[0], "NOTE")

    def test_can_be_turned_off(self):
        os.environ["RB_UPDATE_CHECK"] = "no"
        self.assertIsNone(self.rt.update_status())


class UpdateInPlace(unittest.TestCase):
    """Runs a real program file with --update-runtime, as someone would."""

    def setUp(self):
        self.gh = Releases()
        self.tmp = tempfile.TemporaryDirectory()
        self.prog = os.path.join(self.tmp.name, "prog.py")

    def tearDown(self):
        self.gh.close()
        self.tmp.cleanup()

    def write(self, text):
        with open(self.prog, "w", encoding="utf-8", newline="") as f:
            f.write(text)

    def read(self):
        with open(self.prog, encoding="utf-8", newline="") as f:
            return f.read()

    def run_it(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith("RB_")}
        env.update(RB_RELEASES_URL=self.gh.url + "/releases", SECOND_THOUGHT_INI=os.path.join(self.tmp.name, "none.ini"))
        return subprocess.run([sys.executable, "-I", self.prog, *args], capture_output=True, text=True, timeout=60,
                              cwd=self.tmp.name, env=env)

    def test_updates_and_still_runs(self):
        self.write(exported(RUNTIME, crlf=True))
        self.gh.release(NEXT, as_version(RUNTIME, NEXT), body="### Fixed\n- A thing.")
        r = self.run_it("--update-runtime")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(f"from {RUNTIME_VERSION} to {NEXT}", r.stdout)
        self.assertTrue(os.path.exists(self.prog + ".bak"))
        text = self.read()
        self.assertIn("\r\n", text)
        self.assertIn("# eyJmb3JtYXQiOiJ4In0=", text)
        self.assertEqual(self.run_it("--version").stdout.strip(), f"Second Thought runtime {NEXT}")

    def test_tampered_download_is_refused(self):
        before = exported(RUNTIME)
        self.write(before)
        self.gh.release(NEXT, as_version(RUNTIME, NEXT), sha="0" * 64)
        r = self.run_it("--update-runtime")
        self.assertEqual(r.returncode, 1)
        self.assertIn("SHA-256", r.stdout)
        self.assertEqual(self.read(), before)
        self.assertFalse(os.path.exists(self.prog + ".bak"))

    def test_wrong_version_inside_is_refused(self):
        before = exported(RUNTIME)
        self.write(before)
        self.gh.release(NEXT, RUNTIME)  # says it's NEXT, holds this version
        self.assertEqual(self.run_it("--update-runtime").returncode, 1)
        self.assertEqual(self.read(), before)

    def test_new_major_is_not_applied(self):
        before = exported(RUNTIME)
        self.write(before)
        self.gh.release(f"{MAJOR + 1}.0.0", as_version(RUNTIME, f"{MAJOR + 1}.0.0"))
        r = self.run_it("--update-runtime")
        self.assertEqual(r.returncode, 1)
        self.assertIn("major", r.stdout)
        self.assertEqual(self.read(), before)

    def test_release_without_runtime(self):
        self.write(exported(RUNTIME))
        self.gh.release(NEXT)
        r = self.run_it("--update-runtime")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no runtime to download", r.stdout)

    def test_nothing_newer(self):
        self.write(exported(RUNTIME))
        self.gh.release(RUNTIME_VERSION)
        r = self.run_it("--update-runtime")
        self.assertEqual((r.returncode, "nothing to update" in r.stdout), (0, True), r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
