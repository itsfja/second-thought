"""tools/i18n.py: writing Linear B, cuneiform and hieroglyphs from romanised words, and adding translations."""
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

    def test_egyptian_transliteration_becomes_hieroglyphs(self):
        # #136: each sound in its one-consonant sign, in a linear run; markers (. = -) aren't written
        self.assertEqual(tool.to_script("egy", "rꜣ n kmt"), "\U0001308B\U0001313F \U00013216 \U000133A1\U00013153\U000133CF")
        self.assertEqual(tool.to_script("egy", "sḏm.n=f"), tool.to_script("egy", "sḏmnf"))
        self.assertEqual(tool.to_script("egy", "nḏ Claude {x} abc second-thought.ini"), "\U00013216\U00013193 Claude {x} abc second-thought.ini")

    def test_coptic_transliteration_becomes_coptic_letters(self):
        # #131: one letter each; th, ph, kh, ps, ks join only in Greek loanwords; ^ keeps a word in Latin letters
        self.assertEqual(tool.to_script("cop", "ari tpraksis"), "ⲁⲣⲓ ⲧⲡⲣⲁⲝⲓⲥ")
        self.assertEqual(tool.to_script("cop", "pshai"), "ⲡⲥϩⲁⲓ")
        self.assertEqual(tool.to_script("cop", "ari ^Run {x} second-thought.ini"), "ⲁⲣⲓ Run {x} second-thought.ini")
        self.assertEqual(tool.unmark("ari ^Run"), "ari Run")

    def test_syriac_transliteration_becomes_estrangela(self):
        # #130: unpointed, as Syriac is written: short vowels and a medial ā left out, a final ā or ē as ܐ, an initial
        # vowel with ܐ, a doubled consonant once; a proclitic joined to a name keeps its hyphen
        self.assertEqual(tool.to_script("syc", "malkā ktābā šabbtā"), "ܡܠܟܐ ܟܬܒܐ ܫܒܬܐ")
        self.assertEqual(tool.to_script("syc", "īdā ʾīdā malkē"), "ܐܝܕܐ ܐܝܕܐ ܡܠܟܐ")
        self.assertEqual(tool.to_script("syc", "ṭuksā d-Claude {x} second-thought.ini ^Run"), "ܛܘܟܣܐ ܕ-Claude {x} second-thought.ini Run")
        self.assertEqual(tool.to_script("syc", "dClaude bPython l3 d'sīm ʿbādā' w^text"), "ܕ-Claude ܒ-Python ܠ-3 ܕ'ܣܝܡ ܥܒܕܐ' ܘ-text")
        self.assertEqual(tool.printed("syc", "ʾīn ʿbādā w^text"), "ꜣīn ꜥbādā w-text", "exported Python prints Latin letters only")

    def test_sumerian_is_written_from_the_sign_list(self):
        self.assertEqual(tool.to_script("sux", "e2-dub-ba"), "𒂍𒁾𒁀")
        self.assertEqual(tool.to_script("sux", "%1-da Claude-e <b>ak</b> {name}"), "%1-𒁕 Claude-𒂊 <b>𒀝</b> {name}")
        self.assertEqual(tool.to_script("sux", "ĝeš-ḫur ^n-ta second-thought.ini"), "𒄑𒄯 n-𒋫 second-thought.ini")
        gaps = set()
        self.assertEqual(tool.to_script("sux", "dub zzz", gaps), "𒁾 zzz")
        self.assertEqual(gaps, {"zzz"})
        self.assertEqual(tool.printed("sux", "^Claude-e ĝeš-ḫur ak"), "Claude-e ĝeš-ḫur ak", "exported Python prints the transliteration")

    def test_hittite_mixes_syllables_sumerograms_and_akkadograms(self):
        self.assertEqual(tool.to_script("hit", "ne-e-ši-li"), "𒉈𒂊𒅆𒇷")
        self.assertEqual(tool.to_script("hit", "DUB.SAR-aš A-NA É LÚ.MEŠ"), "𒁾𒊬𒀸 𒀀𒈾 𒂍 𒇽𒎌")
        self.assertEqual(tool.to_script("hit", "ú-ul ták-ša-an."), "𒌑𒌌 𒁖𒊭𒀭.", "an accent is the sign's index")
        gaps = set()
        self.assertEqual(tool.to_script("hit", "%1-za Claude-aš GitHub ^MQTT <b>DUB</b> {name}", gaps), "%1-𒍝 Claude-𒀸 GitHub MQTT <b>𒁾</b> {name}")
        self.assertEqual(gaps, set(), "names in mixed case are kept, not reported")
        self.assertEqual(tool.printed("hit", "ḫa-at-re-eš-šar ^MQTT"), "ḫa-at-re-eš-šar MQTT")

    def test_gothic_is_written_letter_for_letter(self):
        self.assertEqual(tool.to_script("got", "gutisk þiudans ƕas"), "𐌲𐌿𐍄𐌹𐍃𐌺 𐌸𐌹𐌿𐌳𐌰𐌽𐍃 𐍈𐌰𐍃")
        self.assertEqual(tool.to_script("got", "<b>tawei</b> %1 Claude ^the {name} second-thought.ini"),
                         "<b>𐍄𐌰𐍅𐌴𐌹</b> %1 Claude the {name} second-thought.ini")
        gaps = set()
        self.assertEqual(tool.to_script("got", "cave", gaps), "cave", "c and v aren't Gothic letters")
        self.assertEqual(gaps, {"c", "v"})
        self.assertEqual(tool.printed("got", "^the gutisk"), "the gutisk")

    def test_sumerian_signs_are_the_signs_themselves(self):
        # A sign's readings, not those of a variant form listed after it (#374): u3 is U, not ŠA17's old form, and aš and
        # dili are AŠ, not the numeral 1(AŠ@c).
        self.assertEqual([tool.sumerian(r) for r in ("u3", "aš", "dili")], ["𒅇", "𒀸", "𒀸"])
        signs = json.loads((support.ROOT / "tools" / "sux_signs.json").read_text(encoding="utf-8"))["signs"]
        outside = {r: s for r, s in signs.items() if not all(0x12000 <= ord(c) <= 0x1254F for c in s)}
        self.assertEqual(outside, {}, "every sign is in Unicode's cuneiform blocks, which the font has")

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


class Runes(unittest.TestCase):
    """#465: Old Norse in the Younger Futhark, written from its Latin spelling as the inscriptions spell."""

    def test_words_are_spelled_as_the_inscriptions_spell(self):
        for norse, runes in [("konungr", "ᚴᚢᚾᚢᚴᛦ"),      # kunukʀ: o as ᚢ, g as ᚴ, no n before it, the ending's r as ᛦ
                             ("steinn", "ᛋᛏᛅᛁᚾ"),         # stain: ei as ᛅᛁ, the doubled n once
                             ("danmǫrk", "ᛏᛅᚾᛘᛅᚢᚱᚴ"),     # tanmaurk, as on the Jelling stone
                             ("eptir", "ᛁᛒᛏᛁᛦ"), ("þeir", "ᚦᛅᛁᛦ"), ("faðir", "ᚠᛅᚦᛁᛦ"),
                             ("haraldr", "ᚼᛅᚱᛅᛚᛏᚱ"),      # haraltr: ᚱ, not ᛦ, after a dental
                             ("var", "ᚢᛅᚱ"), ("hverr", "ᚼᚢᛁᚱ"), ("á", "ᚬ"), ("án", "ᚬᚾ"), ("dróttinn", "ᛏᚱᚢᛏᛁᚾ")]:
            with self.subTest(norse):
                self.assertEqual(tool.younger_futhark(norse), runes)
        self.assertIsNone(tool.younger_futhark("señor"))
        self.assertTrue(all(0x16A0 <= ord(c) <= 0x16FF for c in "".join(tool.RUNES.values())))

    def test_names_fields_code_and_placeholders_stay_in_latin_letters(self):
        self.assertEqual(tool.to_runes("Claude ræðr hvat næst skal gera"), "Claude ᚱᛅᚦᚱ ᚼᚢᛅᛏ ᚾᛅᛋᛏ ᛋᚴᛅᛚ ᚴᛁᚱᛅ")
        self.assertEqual(tool.to_runes("Set lyklana í second-thought.ini ok keyr --doctor."), "ᛋᛁᛏ ᛚᚢᚴᛚᛅᚾᛅ ᛁ second-thought.ini ᚢᚴ ᚴᛅᚢᚱ --doctor.")
        self.assertEqual(tool.to_runes("sem skrár: name, path, modified, size (<b>{n}</b> MB), %1"), "ᛋᛁᛘ ᛋᚴᚱᛅᚱ: name, path, modified, size (<b>{n}</b> MB), %1")
        self.assertEqual(tool.to_runes("Homey-tæki, {service}-boð ok claude.ai-reikningi"), "Homey-ᛏᛅᚴᛁ, {service}-ᛒᚢᚦ ᚢᚴ claude.ai-ᚱᛅᛁᚴᚾᛁᚴᛁ")
        self.assertEqual(tool.to_runes("GitHub pull requests ok email (not a tool)"), "GitHub pull requests ᚢᚴ email (not a tool)")
        self.assertEqual(tool.to_runes("Send boð, set gildi"), "ᛋᛁᚾᛏ ᛒᚢᚦ, ᛋᛁᛏ ᚴᛁᛚᛏᛁ", "send and set are Old Norse here, not English")

    def test_the_runic_file_is_made_from_the_old_norse_one(self):
        for code, (source, _, about) in tool.DERIVED.items():
            with self.subTest(code):
                have = json.loads((support.ROOT / "i18n" / f"{code}.json").read_text(encoding="utf-8"))
                self.assertEqual(have, tool.derived(code), f"i18n/{code}.json is out of date: python tools/i18n.py derive, then python tools/sync.py")
                norse = json.loads((support.ROOT / "i18n" / f"{source}.json").read_text(encoding="utf-8"))
                self.assertEqual(have["python"], norse["python"], "exported programs print the Latin spelling")
                self.assertEqual((have["name"], have["font"]), (about["name"], about["font"]))
                self.assertEqual(have["page"]["Second Thought"], "Second Thought")
                letters = [c for c in have["categories"]["Events"] + have["page"]["Save"] if c.isalpha()]
                self.assertTrue(letters and all(0x16A0 <= ord(c) <= 0x16FF for c in letters), letters)

    def test_add_writes_the_derived_language_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            for code in ("non", "qnr"):
                (tmp / f"{code}.json").write_text(json.dumps({"name": code, "blockly": "en", "page": {}, "python": {}}), encoding="utf-8")
            (tmp / "new").mkdir()
            words = tmp / "new" / "words.json"
            words.write_text(json.dumps({"page": {"Save {n}": {"non": "Geym {n}"}}, "python": {"Saved": {"non": "Geymt"}}}), encoding="utf-8")
            with mock.patch.object(tool, "I18N", tmp):
                self.assertEqual(tool.cmd_add(str(words)), 0, "words.json needs no qnr")
            runes = json.loads((tmp / "qnr.json").read_text(encoding="utf-8"))
            self.assertEqual((runes["page"], runes["python"]), ({"Save {n}": "ᚴᛅᚢᛘ {n}"}, {"Saved": "Geymt"}))


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
