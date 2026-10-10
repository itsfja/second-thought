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


if __name__ == "__main__":
    unittest.main()
