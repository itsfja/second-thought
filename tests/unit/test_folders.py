"""Folders: what a new file gives a 'when a file appears' script (pictures included), and listing a folder's files."""
import asyncio
import os
import shutil
import tempfile
import time
import unittest

import support
from second_thought.connectors import Connections as Connectors
from second_thought.core import Picture, RunError

PNG = support.ROOT / "tests" / "fixtures" / "crumb.png"


class Folders(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="folders-")
        shutil.copy(PNG, os.path.join(self.dir, "crumb.png"))
        with open(os.path.join(self.dir, "notes.txt"), "w", encoding="utf-8") as f:
            f.write("Rye loaf: 500 g rye, 400 g water.")
        with open(os.path.join(self.dir, ".hidden"), "w", encoding="utf-8") as f:
            f.write("x")
        os.utime(os.path.join(self.dir, "crumb.png"), (time.time() - 3600, time.time() - 3600))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_a_new_picture_comes_with_the_picture(self):
        path = os.path.join(self.dir, "crumb.png")
        rec = Connectors._folder_file(path, os.path.getsize(path))
        self.assertIsInstance(rec["picture"], Picture)
        self.assertEqual((rec["picture"].media_type, rec["picture"].name, rec["name"]), ("image/png", "crumb", "crumb.png"))
        self.assertEqual(rec["picture"].data, PNG.read_bytes())

    def test_a_new_text_file_comes_with_its_words_and_no_picture(self):
        path = os.path.join(self.dir, "notes.txt")
        rec = Connectors._folder_file(path, os.path.getsize(path))
        self.assertIn("500 g rye", rec["text"])
        self.assertNotIn("picture", rec)

    def test_listing_a_folder(self):
        c = Connectors()
        rows = asyncio.run(c.folder_files(self.dir))
        self.assertEqual([r["name"] for r in rows], ["notes.txt", "crumb.png"], "newest first, hidden files left out")
        self.assertEqual(set(rows[0]), {"name", "path", "modified", "size"})
        self.assertRegex(rows[0]["modified"], r"^\d{4}-\d\d-\d\d \d\d:\d\d$")
        self.assertEqual([r["name"] for r in asyncio.run(c.folder_files(self.dir, "*.PNG"))], ["crumb.png"], "patterns ignore case")

    def test_a_missing_folder_says_so(self):
        with self.assertRaises(RunError):
            asyncio.run(Connectors().folder_files(os.path.join(self.dir, "nope")))


if __name__ == "__main__":
    unittest.main()
