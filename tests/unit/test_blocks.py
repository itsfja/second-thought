"""The block list tools/sync.py writes from the editor's definitions — tools/blocks.json (#421): every block's type,
words, slots, tooltip, palette category and capability (or none).

Checked here, in seconds: the list is fresh, the capability table and every language cover all of it, and the
conversion guide and the built-in examples use only blocks on it (the gallery's check is in test_gallery.py).
Each check fails when one block is left out."""
import json
import re
import sys
import unittest

import support

sys.path.insert(0, str(support.ROOT / "tools"))
import sync  # noqa: E402

ROOT = support.ROOT
BLOCKS = json.loads((ROOT / "tools" / "blocks.json").read_text(encoding="utf-8"))
TYPES = {b["type"] for b in BLOCKS}


def used_rb_types(path):
    """The rb_ block types a JS source uses, as blk("...") or type:"..." literals."""
    src = path.read_text(encoding="utf-8")
    used = set(re.findall(r'\bblk\("([^"]+)"', src)) | set(re.findall(r'type:"(rb_[^"]+)"', src))
    return {t for t in used if t.startswith("rb_")}


class List(unittest.TestCase):
    def test_is_fresh(self):
        self.assertEqual((ROOT / "tools" / "blocks.json").read_text(encoding="utf-8"), sync.blocks_json(),
                         "tools/blocks.json is out of date (a block definition changed): run python tools/sync.py")

    def test_shape(self):
        self.assertGreater(len(BLOCKS), 100, "the list should hold every block the editor defines")
        self.assertEqual(len(TYPES), len(BLOCKS), "every type appears once")
        for b in BLOCKS:
            with self.subTest(block=b.get("type")):
                self.assertRegex(b["type"], r"^rb_[a-z0-9_]+$")
                self.assertIsInstance(b["words"], str)
                self.assertIsInstance(b["slots"], list)
                self.assertTrue(all(isinstance(s, str) for s in b["slots"]))
                self.assertIsInstance(b["tooltip"], str)
                self.assertTrue(b["category"], "every block is in the palette")
                self.assertIn("capability", b)

    def test_capability_table_covers_every_block(self):
        caps, none = sync.block_capabilities()
        listed = set(caps) | none
        self.assertEqual(TYPES, listed,
                         f"the capability table and the list disagree: only on the list {sorted(TYPES - listed)}, "
                         f"only in the table {sorted(listed - TYPES)}")

    def test_every_language_covers_every_block(self):
        for path in sorted((ROOT / "i18n").glob("*.json")):
            with self.subTest(language=path.stem):
                keys = {k for k in json.loads(path.read_text(encoding="utf-8")).get("blocks", {}) if k.startswith("rb_")}
                self.assertEqual(keys, TYPES,
                                 f"i18n/{path.name} doesn't translate exactly the listed blocks: "
                                 f"missing {sorted(TYPES - keys)[:5]}, extra {sorted(keys - TYPES)[:5]}")

    def test_guide_names_only_listed_blocks(self):
        text = (ROOT / "prompts" / "convert-guide.txt").read_text(encoding="utf-8")
        named = set(re.findall(r"\brb_[a-z0-9_]+", text))
        self.assertEqual(named - TYPES, set(),
                         f"the conversion guide names blocks not on the list: {sorted(named - TYPES)}")

    def test_examples_use_only_listed_blocks(self):
        for name in ("04-examples.js", "06-example-library.js"):
            with self.subTest(file=name):
                used = used_rb_types(ROOT / "web" / "editor" / name)
                self.assertEqual(used - TYPES, set(),
                                 f"{name} uses blocks not on the list: {sorted(used - TYPES)}")


if __name__ == "__main__":
    unittest.main()
