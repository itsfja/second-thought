"""What exported programs print, in another language: tr(), the yes/no answers, and every language's words for it."""
import ast
import json
import re
import unittest

import support
from second_thought import settings

PACKAGE = support.ROOT / "python" / "second_thought"
LANGS = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted((support.ROOT / "i18n").glob("*.json"))}


def runtime_texts():
    """Every text the runtime passes to tr(), as written: tr("…") and tr("…" if … else "…"), plus --doctor's area names
    (it translates them as it prints each line)."""
    out = set()
    for path in sorted(PACKAGE.glob("*.py")):
        for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "tr" and n.args:
                a = n.args[0]
                out |= {c.value for c in ([a.body, a.orelse] if isinstance(a, ast.IfExp) else [a])
                        if isinstance(c, ast.Constant) and isinstance(c.value, str)}
            if path.name == "doctor.py" and isinstance(n, ast.Call):
                if getattr(n.func, "id", "") == "row" and len(n.args) > 1 and isinstance(n.args[1], ast.Constant):
                    out.add(n.args[1].value)
                if getattr(n.func, "attr", "") == "append" and n.args and isinstance(n.args[0], ast.Tuple) and len(n.args[0].elts) == 2 \
                        and isinstance(n.args[0].elts[0], ast.Constant) and isinstance(n.args[0].elts[0].value, str):
                    out.add(n.args[0].elts[0].value)
    return out


class Tr(unittest.TestCase):
    def setUp(self):
        self.saved = settings._WORDS, settings.LANGUAGE

    def tearDown(self):
        settings._WORDS, settings.LANGUAGE = self.saved

    def test_english_fills_in_slots(self):
        settings._WORDS, settings.LANGUAGE = {}, "en"
        self.assertEqual(settings.tr("Saved {name}.", name="a.md"), "Saved a.md.")
        self.assertEqual(settings.tr("Use {\"temperature\": 20} or {missing}"), "Use {\"temperature\": 20} or {missing}")

    def test_another_language(self):
        settings._WORDS, settings.LANGUAGE = {"Saved {name}.": "Guardado {name}."}, "es"
        self.assertEqual(settings.tr("Saved {name}.", name="a.md"), "Guardado a.md.")
        self.assertEqual(settings.tr("Not translated"), "Not translated")

    def test_language_en_wins_over_the_words(self):
        settings._WORDS, settings.LANGUAGE = {"Saved {name}.": "Guardado {name}."}, "en"
        self.assertEqual(settings.tr("Saved {name}.", name="x"), "Saved x.")

    def test_yes_and_no(self):
        settings._WORDS, settings.LANGUAGE = {"(yes)": "s, si, sí", "(no)": "n, no"}, "en"
        self.assertTrue(settings.said_yes(" Y ") and settings.said_yes("yes") and not settings.said_yes("s"))
        settings.LANGUAGE = "es"
        self.assertTrue(settings.said_yes("s") and settings.said_yes("Sí") and settings.said_yes("y"))
        self.assertTrue(settings.said_no("n") and settings.said_no("No") and not settings.said_no("s"))
        settings._WORDS, settings.LANGUAGE = {"(yes)": "j, ja", "(no)": "n, nein"}, "de"
        self.assertTrue(settings.said_yes("Ja") and settings.said_no("nein") and not settings.said_yes("s"))


class Words(unittest.TestCase):
    def test_every_text_is_translated_and_nothing_else(self):
        texts = runtime_texts()
        self.assertGreater(len(texts), 400)
        for code, lang in LANGS.items():
            if "python" not in lang:
                continue
            with self.subTest(language=code):
                words = lang["python"]
                self.assertEqual(sorted(texts - set(words))[:8], [], "texts the runtime prints with no translation")
                self.assertEqual(sorted(set(words) - texts)[:8], [], "translations of texts the runtime doesn't print")
                for english, said in words.items():
                    self.assertTrue(isinstance(said, str) and said.strip(), english)
                    self.assertEqual(sorted(re.findall(r"\{\w+\}", english)), sorted(re.findall(r"\{\w+\}", said)), english)

    def test_no_shown_text_left_in_english(self):
        # A message, log line, question or error written with words in it, but not through tr(), would print in English.
        shown = {"log", "RunError", "Retryable", "BadJSON", "print", "input", "_input"}
        left = []
        for path in sorted(PACKAGE.glob("*.py")):
            if path.name in ("settings.py", "__init__.py"):
                continue
            src = path.read_text(encoding="utf-8").split("# ---- package only", 1)[1]
            for n in ast.walk(ast.parse(src.split("\n", 1)[1])):
                if not isinstance(n, ast.Call):
                    continue
                name = getattr(n.func, "id", None) or getattr(n.func, "attr", None)
                if name not in shown or getattr(getattr(n.func, "value", None), "id", "") == "math":
                    continue
                for arg in n.args[:3]:
                    inside_tr = {id(c) for t in ast.walk(arg) if isinstance(t, ast.Call) and getattr(t.func, "id", "") == "tr" for c in ast.walk(t)}
                    for c in ast.walk(arg):
                        if isinstance(c, ast.Constant) and isinstance(c.value, str) and re.search(r"[A-Za-z]{3}", c.value) and id(c) not in inside_tr \
                                and not isinstance(getattr(c, "_parent", None), ast.Subscript):
                            left.append(f"{path.name}: {c.value[:60]!r}")
        # Dictionary keys and field names in formatted values (r['title'], d["name"]) aren't shown text.
        left = [x for x in left if not re.search(r": '(date|title|name|day|start|caps|reason|transient|approved|role|text)'$", x)]
        self.assertEqual(left, [])


if __name__ == "__main__":
    unittest.main()
