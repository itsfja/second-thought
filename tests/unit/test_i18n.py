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


if __name__ == "__main__":
    unittest.main()
