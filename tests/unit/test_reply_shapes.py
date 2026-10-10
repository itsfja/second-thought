"""Reading a model's JSON reply and checking it has the shape a block asked for."""
import unittest

import support  # noqa: F401
from second_thought.core import SCHEMAS, BadJSON, _fit, _parse_json, _shape_problem, record_schema


class ParseJSON(unittest.TestCase):
    def test_finds_the_json(self):
        self.assertEqual(_parse_json(' {"a": 1} '), {"a": 1})
        self.assertEqual(_parse_json('Here you go:\n```json\n{"a": 2}\n```'), {"a": 2})
        self.assertEqual(_parse_json('Sure! {"answer": true} Hope that helps.'), {"answer": True})
        self.assertEqual(_parse_json("The list: [1, 2]"), [1, 2])

    def test_unreadable(self):
        with self.assertRaises(BadJSON):
            _parse_json("no json here")


class Shapes(unittest.TestCase):
    def test_good_replies(self):
        self.assertIsNone(_shape_problem({"answer": False}, SCHEMAS["yesno"]))
        self.assertIsNone(_shape_problem({"number": "4.5"}, SCHEMAS["number"]))  # a number written as text is fine
        self.assertIsNone(_shape_problem({"pick": 2, "reason": "shorter"}, SCHEMAS["pick"]))
        self.assertIsNone(_shape_problem({"approved": False, "problems": ["too long"]}, SCHEMAS["review"]))
        self.assertIsNone(_shape_problem({"tool": "search_web", "input": {"query": "x"}}, SCHEMAS["agent"]))

    def test_problems_name_the_part(self):
        cases = [({}, "yesno", 'missing "answer"'), ({"answer": "yes"}, "yesno", '"answer" should be true or false'),
                 ([1], "yesno", "should be a JSON object"), ({"number": True}, "number", '"number" should be a number'),
                 ({"items": "a"}, "list", '"items" should be a list'), ({"items": ["a", 2]}, "list", 'item 2 of "items" should be text'),
                 ({"pick": 3}, "pick", '"pick" should be one of 1, 2')]
        for v, schema, want in cases:
            with self.subTest(v=v, schema=schema):
                self.assertIn(want, _shape_problem(v, SCHEMAS[schema]) or "")

    def test_records(self):
        one = record_schema(["name", "weight"])
        self.assertIsNone(_shape_problem({"name": "Loaf", "weight": 900}, one))
        self.assertIn("wrong kind of value", _shape_problem({"name": ["a"]}, one))
        many = record_schema(["name"], many=True)
        self.assertIsNone(_shape_problem({"items": [{"name": "a"}, {"name": "b"}]}, many))

    def test_fit_makes_small_safe_fixes(self):
        self.assertEqual(_fit(["a", "b"], SCHEMAS["list"]), {"items": ["a", "b"]})
        self.assertEqual(_fit([{"answer": True}], SCHEMAS["yesno"]), {"answer": True})
        self.assertEqual(_fit({"answer": True}, SCHEMAS["yesno"]), {"answer": True})
        self.assertEqual(_fit([{"a": 1}, {"a": 2}], SCHEMAS["yesno"]), [{"a": 1}, {"a": 2}])


if __name__ == "__main__":
    unittest.main()
