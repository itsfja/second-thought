"""Named inputs (#442): Runtime.input_value. The cases are in tests/parity/inputs.json, which the page's own tests
(tests/editor/inputs.test.cjs) read too, so a value means the same on the page, on the command line and over MCP."""
import json
import pathlib
import unittest

import support  # noqa: F401
from second_thought.runtime import Runtime

PARITY = pathlib.Path(__file__).resolve().parent.parent / "parity"
CASES = json.loads((PARITY / "inputs.json").read_text(encoding="utf-8"))


class InputValue(unittest.TestCase):
    def test_answers(self):
        for name, kind, raw, value, why in CASES["answers"]:
            with self.subTest(kind=kind, raw=raw):
                got, problem = Runtime.input_value(name, kind, raw)
                self.assertEqual((got, problem), (value, why))
                if value is not None:
                    self.assertIs(type(got), type(value))


if __name__ == "__main__":
    unittest.main()
