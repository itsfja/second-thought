"""The memory blocks: notes kept while a program runs, notes saved to memory.json, and notes that expire."""
import json
import os
import time
import unittest

import support  # noqa: F401
from second_thought.core import MEMORY_FILE, Picture, RunError
from second_thought.runtime import Runtime


def fresh():
    r = Runtime()
    r.reset()
    r.log = lambda *a, **k: None
    return r


class Memory(unittest.TestCase):
    def setUp(self):
        if os.path.exists(MEMORY_FILE):
            os.remove(MEMORY_FILE)

    def saved(self):
        with open(MEMORY_FILE, encoding="utf-8") as f:
            return json.load(f)

    def test_uses_the_test_memory_file(self):
        self.assertTrue(MEMORY_FILE.startswith(str(support.TMP)))

    def test_saved_notes_outlive_the_program_and_ignore_case(self):
        fresh().remember("rye", " Favourite Flour ", "permanent")
        self.assertEqual(fresh().recall("favourite flour"), "rye")
        self.assertEqual(self.saved()["favourite flour"]["name"], "Favourite Flour")

    def test_while_running_notes_stay_out_of_the_file(self):
        r = fresh()
        r.remember("72%", "hydration")
        self.assertEqual(r.recall("Hydration"), "72%")
        self.assertFalse(os.path.exists(MEMORY_FILE))
        self.assertEqual(fresh().recall("hydration"), "")

    def test_a_while_running_note_replaces_a_saved_one(self):
        fresh().remember("old", "x", "permanent")
        r = fresh()
        r.remember("new", "x")
        self.assertEqual(r.recall("x"), "new")
        self.assertNotIn("x", self.saved())

    def test_adding_to_a_list(self):
        r = fresh()
        r.remember("a", "jobs", "permanent")
        r.remember_add("b", "jobs")
        r.remember_add("c", "jobs")
        self.assertEqual(fresh().recall("jobs"), ["a", "b", "c"])

    def test_expiring_notes(self):
        r = fresh()
        r.remember_for("soon", "starter fed", 1, "h")
        self.assertTrue(r.remembers("starter fed"))
        data = self.saved()
        data["starter fed"]["expires"] = int(time.time() * 1000) - 1
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
        self.assertFalse(fresh().remembers("starter fed"))
        with self.assertRaises(RunError):
            r.remember_for("x", "y", 0, "h")

    def test_forget_and_names(self):
        r = fresh()
        r.remember("1", "b", "permanent")
        r.remember("2", "A")
        self.assertEqual(r.memory_names(), ["A", "b"])
        r.forget("B")
        self.assertEqual(r.memory_names(), ["A"])

    def test_mistakes(self):
        with self.assertRaises(RunError):
            fresh().remember("x", "   ", "permanent")
        with self.assertRaises(RunError):
            fresh().remember(Picture(b"x", "image/png", "crumb"), "pic", "permanent")


NOTES = [
    {"name": "rye loaf", "value": "78% hydration, 20% wholemeal rye, proved overnight in the fridge", "updated": 3000},
    {"name": "starter feeding", "value": "Feed the starter 1:5:5 at 8pm; it peaks at 7am", "updated": 2000},
    {"name": "oven temperatures", "value": "Dutch oven at 250 °C for 20 min, lid off at 230 °C", "updated": 1000},
    {"name": "Crème pâtissière", "value": "Vanilla custard for the brioche", "updated": 4000},
    {"name": "shopping", "value": ["strong white flour", "rye flour", "sea salt"], "updated": 5000},
]


class Searching(unittest.TestCase):
    def test_terms(self):
        self.assertEqual(Runtime.memory_terms("The Loaves were PROVING, baked!"), ["loave", "prov", "bak"])
        self.assertEqual(Runtime.memory_terms("Crème  pâtissière 250°C"), ["crème", "pâtissière", "250", "c"])
        self.assertEqual(Runtime.memory_terms("glass_jar"), ["glass", "jar"])  # an underscore splits words
        decomposed = "Cre\u0300me"  # the same word with its accent as a separate mark
        self.assertEqual(Runtime.memory_terms(decomposed), ["crème"])
        self.assertEqual(Runtime.memory_terms("ﬁnal ２nd x²"), ["final", "2nd", "x2"])  # a ligature, a wide digit, a superscript

    def test_ranking(self):
        names = lambda q, **k: [f["name"] for f in Runtime.rank_notes(NOTES, q, **k)]  # noqa: E731
        self.assertEqual(names("rye"), ["rye loaf", "shopping"])  # in the name counts double
        self.assertEqual(names("when does the starter peak"), ["starter feeding"])
        self.assertEqual(names("hydrat"), ["rye loaf"])  # a word start finds the word
        self.assertEqual(names("creme"), [])  # accents matter: crème isn't creme
        self.assertEqual(names("crème"), ["Crème pâtissière"])
        self.assertEqual(names("the and of"), [])  # only common words
        self.assertEqual(names("flour", limit=1), ["shopping"])
        self.assertEqual(names("oven 250"), ["oven temperatures"])

    def test_ties_go_to_the_newest(self):
        same = [{"name": "b", "value": "salt", "updated": 1}, {"name": "a", "value": "salt", "updated": 2}, {"name": "c", "value": "salt", "updated": 2}]
        self.assertEqual([f["name"] for f in Runtime.rank_notes(same, "salt")], ["a", "c", "b"])

    def test_the_agents_tool(self):
        if os.path.exists(MEMORY_FILE):
            os.remove(MEMORY_FILE)
        r = fresh()
        for n in NOTES[:3]:
            r.remember(n["value"], n["name"], "permanent")
        r.remember("check the proof at 9", "today")
        text = r.memory_search_text("starter proof")
        self.assertTrue(text.startswith("Notes matching “starter proof”, best first (2 of 4):\n- "), text)
        self.assertIn("- starter feeding (saved ", text)
        self.assertIn("- today (saved ", text)
        self.assertIn("No saved note matches “croissant”. list_memory gives the names of all 4.", r.memory_search_text("croissant"))
        with self.assertRaises(RunError):
            r.memory_search_text("  ")


if __name__ == "__main__":
    unittest.main()
