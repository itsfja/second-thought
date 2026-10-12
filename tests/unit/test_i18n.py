"""The block palette's translation files: well formed. (The page tests check each covers every block.)"""
import json
import re
import unittest

import support

FILES = sorted((support.ROOT / "i18n").glob("*.json"))


class Files(unittest.TestCase):
    def test_there_is_at_least_one(self):
        self.assertTrue(FILES)

    def test_shape(self):
        for path in FILES:
            with self.subTest(file=path.name):
                d = json.loads(path.read_text(encoding="utf-8"))
                self.assertRegex(path.stem, r"^[a-z]{2,3}$")
                self.assertTrue(d["name"] and d["blockly"])
                self.assertTrue(set(d) >= {"blocks", "options", "categories", "labels"})
                for block, parts in d["blocks"].items():
                    self.assertTrue(block.startswith("rb_"), block)
                    for k, v in parts.items():
                        self.assertTrue(re.fullmatch(r"message\d+|tooltip", k), f"{block}.{k}")
                        self.assertTrue(isinstance(v, str) and v.strip(), f"{block}.{k}")
                for field, labels in d["options"].items():
                    self.assertRegex(field, r"^rb_[a-z_]+\.[A-Z_]+$")
                    self.assertTrue(all(isinstance(v, str) and v.strip() for v in labels.values()), field)
                if "font" in d:
                    # A font the page loads from Google Fonts for this language only (Linear B): a plain family name.
                    self.assertRegex(d["font"], r"^[A-Za-z0-9 ]+$")
                if "dir" in d:
                    # Right-to-left languages (Hebrew, Aramaic) mirror the page; left to right is the default.
                    self.assertIn(d["dir"], ("ltr", "rtl"))
                for key, words in d.get("blocklyMsg", {}).items():
                    # Blockly's own words, for a language Blockly has no msg file for (the page tests check it has them all).
                    self.assertRegex(key, r"^[A-Z][A-Z0-9_]*$")
                    self.assertTrue(isinstance(words, str) and words.strip(), key)
                for english, words in d.get("starters", {}).items():
                    self.assertTrue(isinstance(words, str) and words.strip(), english)
                for key, words in d.get("examples", {}).items():
                    # Each example: a short title, a description and a tip (the page tests check every example has one).
                    self.assertRegex(key, r"^[a-z][a-z0-9_]*$")
                    self.assertEqual(set(words), {"title", "desc", "tip"}, key)
                    self.assertTrue(all(isinstance(v, str) and v.strip() for v in words.values()), key)
                    self.assertLessEqual(len(words["title"]), 60, key)
                for english, words in d.get("page", {}).items():
                    # The page's own words: the same {name} slots and the same bold words, so nothing goes missing.
                    self.assertTrue(isinstance(words, str) and words.strip(), english)
                    self.assertEqual(sorted(re.findall(r"\{\w+\}", english)), sorted(re.findall(r"\{\w+\}", words)), english)
                    self.assertEqual(re.findall(r"</?\w+>", english), re.findall(r"</?\w+>", words), english)


if __name__ == "__main__":
    unittest.main()
