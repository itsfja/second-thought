"""The agent step's reply shape is one Claude's structured replies accept: every object closed (#250)."""
import unittest

import support  # noqa: F401
from second_thought.core import _shape_problem
from second_thought.runtime import Runtime


def open_objects(schema, where="step"):
    """Where an object in this schema doesn't set additionalProperties to false."""
    bad = []
    if isinstance(schema, dict):
        if schema.get("type") == "object" and schema.get("additionalProperties") is not False:
            bad.append(where)
        for k, v in schema.items():
            if isinstance(v, dict):
                bad += open_objects(v, f"{where}.{k}")
            elif isinstance(v, list):
                bad += [b for i, x in enumerate(v) for b in open_objects(x, f"{where}.{k}[{i}]")]
    return bad


class StepShape(unittest.TestCase):
    def catalogue(self):
        rt = Runtime()
        tools = [{"kind": k} for k in rt.AGENT_BUILTINS]
        tools.append({"kind": "block", "name": "add", "desc": "Adds.", "inputs": "a: number; b: number", "params": ["a", "b"], "fn": None})
        return rt._agent_tools(tools, [])

    def test_every_object_is_closed(self):
        step = Runtime.agent_step_schema(self.catalogue())
        self.assertEqual(open_objects(step), [])

    def test_input_offers_every_tools_inputs(self):
        cat = self.catalogue()
        names = set(Runtime.agent_step_schema(cat)["properties"]["input"]["properties"])
        for tool, entry in cat.items():
            self.assertLessEqual(set((entry[4] or {}).get("properties", {})), names, tool)

    def test_ordinary_steps_still_fit(self):
        step = Runtime.agent_step_schema(self.catalogue())
        self.assertIsNone(_shape_problem({"tool": "add", "input": {"a": 2, "b": "3"}, "why": "sum"}, step))
        self.assertIsNone(_shape_problem({"done": True, "answer": "5"}, step))


if __name__ == "__main__":
    unittest.main()
