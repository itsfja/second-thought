"""The value helpers. The page has the same rules in JavaScript, so a block gives the same answer in both places."""
import unittest

import support  # noqa: F401
from second_thought.core import (RunError, arith, change_case, compare, contains, count, field_list, is_empty, join,
                                 length, modulo, num, rec_get, rec_has, rec_keys, rec_set, round_op, sort_by, times,
                                 to_bool, to_list, to_record, to_str, word_count, _short)


class Numbers(unittest.TestCase):
    def test_num(self):
        cases = [(True, 1), (False, 0), (7, 7), (2.5, 2.5), ("3.0", 3), (" 2.5 ", 2.5), ("", 0), ("abc", 0), (None, 0), ("1e3", 1000)]
        for v, want in cases:
            with self.subTest(v=v):
                self.assertEqual(num(v), want)
        self.assertIsInstance(num("3.0"), int)

    def test_arith(self):
        self.assertEqual(arith("2", "ADD", 3), 5)
        self.assertEqual(arith(10, "MINUS", "4"), 6)
        self.assertEqual(arith(1.5, "MULTIPLY", 2), 3)
        self.assertIsInstance(arith(1.5, "MULTIPLY", 2), int)
        self.assertEqual(arith(7, "DIVIDE", 2), 3.5)
        self.assertEqual(arith(2, "POWER", 10), 1024)
        with self.assertRaises(RunError):
            arith(1, "DIVIDE", 0)

    def test_modulo_follows_the_sign_of_the_first_number(self):
        self.assertEqual(modulo(7, 3), 1)
        self.assertEqual(modulo(-7, 3), -1)  # like JavaScript's %, not Python's
        with self.assertRaises(RunError):
            modulo(1, 0)

    def test_round_halves_go_up_like_javascript(self):
        self.assertEqual(round_op(2.5, "ROUND"), 3)
        self.assertEqual(round_op(-2.5, "ROUND"), -2)
        self.assertEqual(round_op(2.1, "ROUNDUP"), 3)
        self.assertEqual(round_op(2.9, "ROUNDDOWN"), 2)

    def test_count_goes_either_way_and_ignores_the_sign_of_by(self):
        self.assertEqual(list(count(1, 5, 2)), [1, 3, 5])
        self.assertEqual(list(count(5, 1, 2)), [5, 3, 1])
        self.assertEqual(list(count(1, 3, -1)), [1, 2, 3])
        self.assertEqual(list(count(1, 2, 0)), [1, 2])  # a step of 0 counts in ones
        self.assertEqual(list(count(0, 1, 0.5)), [0, 0.5, 1])

    def test_times(self):
        self.assertEqual(len(times("3.9")), 3)
        self.assertEqual(len(times(-2)), 0)


class Text(unittest.TestCase):
    def test_to_str(self):
        cases = [(None, ""), (True, "true"), (False, "false"), (2.0, "2"), (0.5, "0.5"), ([1, "a"], "1\na"),
                 ({"a": 1, "b": [1, 2]}, "a: 1\nb: 1, 2"), (3, "3")]
        for v, want in cases:
            with self.subTest(v=v):
                self.assertEqual(to_str(v), want)

    def test_to_bool(self):
        for v in ("", "false", "FALSE", "0", 0, None):
            with self.subTest(v=v):
                self.assertFalse(to_bool(v))
        for v in ("no", "yes", "x", [], [0], 1):  # any other text is true, and so is any list
            with self.subTest(v=v):
                self.assertTrue(to_bool(v))

    def test_to_list_drops_bullets_numbers_and_blank_lines(self):
        self.assertEqual(to_list("- a\n* b\n\n3. c\n• d\n4) e"), ["a", "b", "c", "d", "e"])
        self.assertEqual(to_list("(5) f\n12. g\n•h\n1.Item"), ["f", "g", "h", "Item"])

    def test_to_list_keeps_numbers_that_arent_markers(self):
        lines = ["10 green bottles", "2024 plan", "1.5 kg flour", "-5 °C overnight", "**Rye** loaf", "3 eggs"]
        self.assertEqual(to_list("\n".join(lines)), lines)
        self.assertEqual(to_list(""), [])
        self.assertEqual(to_list(None), [])
        items = [1, 2]
        self.assertIs(to_list(items), items)

    def test_join_length_empty(self):
        self.assertEqual(join("a", 1, None, True), "a1true")
        self.assertEqual(length([1, 2, 3]), 3)
        self.assertEqual(length("héllo"), 5)
        self.assertTrue(is_empty(""))
        self.assertTrue(is_empty([]))
        self.assertFalse(is_empty(0))

    def test_change_case(self):
        self.assertEqual(change_case("hello wORLD", "UPPERCASE"), "HELLO WORLD")
        self.assertEqual(change_case("Hello", "LOWERCASE"), "hello")
        self.assertEqual(change_case("hello wORLD  again", "TITLECASE"), "Hello World  Again")

    def test_contains_ignores_case(self):
        self.assertTrue(contains("Sourdough Starter", "starter"))
        self.assertFalse(contains("rye", "wheat"))

    def test_word_count(self):
        self.assertEqual(word_count("  one two\nthree  "), 3)
        self.assertEqual(word_count("   "), 0)

    def test_short(self):
        self.assertEqual(_short("a   b\n c", 10), "a b c")
        self.assertEqual(_short("abcdefghij", 5), "abcd…")


class Comparing(unittest.TestCase):
    def test_numbers_compare_as_numbers(self):
        self.assertTrue(compare("10", "GT", "9"))
        self.assertTrue(compare(2, "EQ", "2.0"))

    def test_text_compares_without_case(self):
        self.assertTrue(compare("Apple", "EQ", "apple"))
        self.assertTrue(compare("b", "GT", "A"))
        self.assertTrue(compare("10", "LT", "9a"))  # one side isn't a number, so both are text

    def test_true_isnt_a_number(self):
        self.assertTrue(compare(True, "EQ", "TRUE"))


class Records(unittest.TestCase):
    def test_get_set_has_keys(self):
        r = to_record({"name": "Loaf", "extra": {"x": 1}}, ["name", "weight"])
        self.assertEqual(r, {"name": "Loaf", "extra": '{"x": 1}', "weight": ""})
        rec_set(r, " weight ", 900)
        self.assertEqual(rec_get(r, "weight"), 900)
        self.assertEqual(rec_get(r, "missing"), "")
        self.assertTrue(rec_has(r, "name"))
        self.assertFalse(rec_has("not a record", "name"))
        self.assertEqual(rec_keys(r), ["name", "extra", "weight"])
        self.assertEqual(rec_keys([]), [])

    def test_mistakes_say_what_went_wrong(self):
        with self.assertRaises(RunError):
            rec_get("text", "name")
        with self.assertRaises(RunError):
            rec_set({}, " ", 1)
        with self.assertRaises(RunError):
            rec_set("text", "name", 1)

    def test_field_list(self):
        self.assertEqual(field_list("name, weight\n hydration ,,"), ["name", "weight", "hydration"])

    def test_sort_by(self):
        loaves = [{"n": "b", "w": "900"}, {"n": "a", "w": 1000}, {"n": "c", "w": 80}]
        self.assertEqual([x["n"] for x in sort_by(loaves, "w", "asc")], ["c", "b", "a"])  # all numbers: by number
        self.assertEqual([x["n"] for x in sort_by(loaves, "n", "desc")], ["c", "b", "a"])
        self.assertEqual(sort_by("pear\nApple\nfig", "", "asc"), ["Apple", "fig", "pear"])
        self.assertEqual(len(loaves), 3)  # the list given isn't changed


if __name__ == "__main__":
    unittest.main()
