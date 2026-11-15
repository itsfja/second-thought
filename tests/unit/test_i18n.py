"""The block palette's translation files: well formed. (The page tests check each covers every block.)"""
import json
import re
import unittest

import support

FILES = sorted((support.ROOT / "i18n").glob("*.json"))


def has_own_words(english):
    """Whether a text has a word of English to translate: a word of three or more letters starting lowercase, outside
    the {name} slots and <b>bold</b> marks. Names (Coinbase, Pi-hole, Docker {version}) and placeholder skeletons
    ({window} {x}) have none, so they may stay as they are in any language."""
    stripped = re.sub(r"\{[^{}]*\}|</?\w+>", "", english)
    return any(w[0].islower() and len(w) >= 3 for w in re.findall(r"[^\W\d_]+(?:['’-][^\W\d_]+)*", stripped))


# Texts a language shares with English rather than leaves untranslated: currencies (yen, euros), terms that are the
# same word (premium, standard, error, tokens), and names with a word of English in them (Second Thought runtime…).
# Middle English (enm) is exempt: its own words are English words, so its translations often are the English text.
SHARED_WITH_ENGLISH = {
    "US dollars", "Second Thought runtime {runtime_version}", "Second Thought on claude.ai",
    "Home Assistant: homelab", "Email (sending)", "array {state}", "budget {n}", "container", "emails", "error",
    "euros", "note", "pounds", "premium", "sent", "standard", "tokens", "versions", "yen", "yuan",
    "{action} the Unraid {who} {name}", "{code}, {note} (1 US dollar = {rate})", "{got} topics", "{items} items",
    "{list} and {last}", "{n} clients", "{n} containers", "{n} items", "{n} ports", "{n} records", "{n} sessions",
    "{n} shares", "{n} topics", "{recs} items", "{recs} records", "~{n} tokens",
}

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

    def test_no_text_left_in_english(self):
        # #462: the tests only checked that each language has a text, not that it was translated. A translation the
        # same as its English is a text left untranslated, unless it's a name, a skeleton, or a shared word.
        for path in FILES:
            if path.stem == "enm":
                continue
            with self.subTest(file=path.name):
                d = json.loads(path.read_text(encoding="utf-8"))
                left = [english for section in ("page", "python") for english, words in (d.get(section) or {}).items()
                        if english == words and english not in SHARED_WITH_ENGLISH and has_own_words(english)]
                self.assertEqual(left, [], "texts left the same as the English")


if __name__ == "__main__":
    unittest.main()
