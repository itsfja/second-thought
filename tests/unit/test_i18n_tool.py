"""tools/i18n.py: writing Linear B and cuneiform from romanised words, and adding translations."""
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

import support

sys.path.insert(0, str(support.ROOT / "tools"))
import i18n as tool  # noqa: E402


class Scripts(unittest.TestCase):
    def test_linear_b_words_become_signs(self):
        self.assertEqual(tool.to_script("gmy", "ka-ra-pe"), "\U0001000F\U00010028\U0001001F")

    def test_placeholders_names_and_files_are_kept(self):
        for lang, word in [("gmy", "to"), ("akk", "ana")]:
            for keep in ["{to}", "{name}-actions.zip", "GitHub", "SETUP.md", "second-thought.ini", "python my-program.py --test"]:
                with self.subTest(lang=lang, keep=keep):
                    out = tool.to_script(lang, f"{word} {keep}")
                    self.assertTrue(out.endswith(" " + keep), out)
                    self.assertNotIn(word, out.split(" ")[0])

    def test_cuneiform_syllables(self):
        self.assertEqual(tool.syllables("šumātim"), ["šu", "ma", "ti", "im"])
        self.assertEqual(tool.syllables("ibašši"), ["i", "ba", "aš", "ši"])
        self.assertIsNone(tool.syllables("v2"))

    def test_cuneiform_matches_the_existing_translations(self):
        # The akk words already translated both ways: written again from their romanised form, most come out the same.
        d = json.loads((support.ROOT / "i18n" / "akk.json").read_text(encoding="utf-8"))
        pairs = [(d["python"][k], d["page"][k]) for k in d["python"] if k in d["page"] and isinstance(d["page"][k], str)][:200]
        same = sum(tool.to_script("akk", roman) == signs for roman, signs in pairs)
        self.assertGreater(same / len(pairs), 0.6, f"{same} of {len(pairs)}")

    def test_unknown_syllables_are_reported_not_guessed(self):
        gaps = set()
        out = tool.to_script("gmy", "ka-zz-pe", gaps)
        self.assertEqual((out, gaps), ("ka-zz-pe", {"zz"}))


class Add(unittest.TestCase):
    def test_add_writes_every_language_and_checks_placeholders(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            for code in ("de", "gmy"):
                (tmp / f"{code}.json").write_text(json.dumps({"name": code, "page": {}, "python": {}}), encoding="utf-8")
            words = tmp / "words.json"
            words.write_text(json.dumps({"page": {"Save {n}": {"de": "Speichere {n}", "gmy": "o-ri-ze {n}"},
                                                  "Bad": {"de": "Schlecht {x}", "gmy": "ka"}}}), encoding="utf-8")
            with mock.patch.object(tool, "I18N", tmp):
                code = tool.cmd_add(str(words))
            de = json.loads((tmp / "de.json").read_text(encoding="utf-8"))
            gmy = json.loads((tmp / "gmy.json").read_text(encoding="utf-8"))
            self.assertEqual(code, 1)  # "Bad" has a placeholder English doesn't
            self.assertEqual(de["page"], {"Save {n}": "Speichere {n}"})
            self.assertEqual(gmy["page"]["Save {n}"], "\U00010003\U0001002A\U0001003D {n}")
            self.assertTrue((tmp / "de.json").read_text(encoding="utf-8").startswith('{\n "name"'))


if __name__ == "__main__":
    unittest.main()
