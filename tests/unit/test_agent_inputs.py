"""The agent's tool inputs: declaring their types, the schema sent to the model, and checking what comes back."""
import unittest

import support  # noqa: F401
from second_thought.agent import AgentTools
from second_thought.core import RunError


class InputTypes(unittest.TestCase):
    def test_parse(self):
        got = AgentTools.parse_input_types("flour grams: number - grams of flour; Salty: yes or no\nnames: list",
                                           ["flour grams", "salty", "names", "note"], "Recipe")
        self.assertEqual(got, {"flour grams": ("number", "grams of flour"), "salty": ("yes/no", ""), "names": ("list", ""),
                               "note": ("text", "")})

    def test_mistakes_name_the_block(self):
        with self.assertRaises(RunError) as e:
            AgentTools.parse_input_types("weight: number", ["flour"], "Recipe")
        self.assertIn("Recipe", str(e.exception))
        with self.assertRaises(RunError):
            AgentTools.parse_input_types("flour: decimal", ["flour"], "Recipe")

    def test_schema(self):
        s = AgentTools.tool_schema({"q": ("text", "what to look up"), "n": ("number", ""), "x": ("any", "")}, optional={"n"})
        self.assertEqual(s, {"type": "object", "additionalProperties": False, "required": ["q", "x"],
                             "properties": {"q": {"type": "string", "description": "what to look up"}, "n": {"type": "number"}, "x": {}}})


class CheckInput(unittest.TestCase):
    SCHEMA = AgentTools.tool_schema({"n": ("number", ""), "ok": ("yes/no", ""), "t": ("text", ""), "l": ("list", "")})

    def test_safe_conversions(self):
        problem, got = AgentTools.check_tool_input({"n": "4", "ok": "Yes", "t": 12, "l": [1, "a"]}, self.SCHEMA)
        self.assertIsNone(problem)
        self.assertEqual(got, {"n": 4, "ok": True, "t": "12", "l": ["1", "a"]})

    def test_problems(self):
        good = {"n": 1, "ok": True, "t": "x", "l": []}
        cases = [({**good, "extra": 1}, "no input called “extra”"), ({k: v for k, v in good.items() if k != "t"}, "“t” is missing"),
                 ({**good, "t": None}, "“t” is missing"), ({**good, "n": "four"}, "“n” should be a number"),
                 ({**good, "n": True}, "“n” should be a number"), ({**good, "ok": "maybe"}, "“ok” should be true or false"),
                 ({**good, "t": ["a"]}, "“t” should be text, not a list"), ({**good, "l": "a"}, "“l” should be a list")]
        for inp, want in cases:
            with self.subTest(inp=inp):
                problem, got = AgentTools.check_tool_input(inp, self.SCHEMA)
                self.assertIn(want, problem or "")
                self.assertIsNone(got)

    def test_tool_names_are_unique(self):
        taken = set()
        self.assertEqual([AgentTools._agent_name(n, taken) for n in ("Look up!", "look up", "", "")],
                         ["look_up", "look_up_2", "tool", "tool_2"])


if __name__ == "__main__":
    unittest.main()
