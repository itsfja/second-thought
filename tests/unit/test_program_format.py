"""The block file format (docs/program-format.md): the grammar, and --doctor's check of the file inside a program."""
import base64
import json
import pathlib
import sys
import tempfile
import unittest

import support  # noqa: F401  (the settings above, before second_thought is imported)

from second_thought.doctor import PROGRAM_MARKS, Doctor, _grammar_problems

GALLERY = sorted((support.ROOT / "gallery").glob("*.json"))
MARK = PROGRAM_MARKS[0]


def block_file(blocks):
    return {"format": "reflection-blocks", "version": 1, "name": "tested",
            "program": {"blocks": {"languageVersion": 0, "blocks": blocks}}}


def exported(path, data, broken=False):
    payload = base64.b64encode(json.dumps(data).encode()).decode()
    lines = ["print('hello')", "", MARK, "# CODE-HASH: " + "0" * 64, "# BLOCKS:"]
    if broken:
        payload = base64.b64encode(b"not json").decode()
    lines += ["# " + payload[i:i + 76] for i in range(0, len(payload), 76)]
    pathlib.Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


class Grammar(unittest.TestCase):
    def test_every_gallery_program_matches(self):
        self.assertTrue(GALLERY)
        for path in GALLERY:
            with self.subTest(file=path.name):
                self.assertEqual(_grammar_problems(json.loads(path.read_text(encoding="utf-8"))), [])

    def test_the_shapes_the_format_promises(self):
        ok = block_file([{"type": "rb_start", "next": {"block": {"type": "rb_result"}}}])
        self.assertEqual(_grammar_problems(ok), [])
        self.assertEqual(_grammar_problems({**ok, "tests": [{"name": "Says done", "value": "", "inputs": {}, "criteria": "It says done."}],
                                            "exported": "2026-11-08T09:00:00.000Z", "gallery": {"title": "T"}}), [])
        for broken, problem in [
            ([], "the top level"),                                                 # not an object with the format
            ({**block_file([]), "format": "other"}, "format"),
            ({**block_file([]), "version": 2}, "version"),
            ({**block_file([]), "name": ""}, "name"),
            ({**block_file([]), "program": {}}, "the program part"),
            (block_file([{"type": ""}]), "isn't a block with a type"),
            (block_file([{"type": "rb_start", "fields": {"A": {}}}]), "fields"),
            (block_file([{"type": "rb_start", "inputs": {"GOAL": {}}}]), "isn't a block connection"),
            (block_file([{"type": "rb_start", "inputs": {"GOAL": {"block": {}}}}]), "isn't a block with a type"),
            (block_file([{"type": "rb_start", "x": "left"}]), "x"),
            ({**block_file([]), "tests": [{"value": ""}]}, "tests"),
        ]:
            with self.subTest(problem=problem):
                self.assertTrue(any(problem in p for p in _grammar_problems(broken)), _grammar_problems(broken))

    def test_a_field_can_be_null_or_a_variable_reference(self):
        self.assertEqual(_grammar_problems(block_file([{"type": "rb_start", "inputs": {"VALUE": {"shadow": {"type": "text", "fields": {"TEXT": None}}}}}])), [])
        self.assertEqual(_grammar_problems(block_file([{"type": "variables_get", "fields": {"VAR": {"id": "g_warning"}}}])), [])
        self.assertTrue(_grammar_problems(block_file([{"type": "variables_get", "fields": {"VAR": {"name": "warning"}}}])))

    def test_unknown_keys_are_ignored(self):
        newer = {**block_file([{"type": "rb_start", "extraState": {"a": 1}}]), "future": {"x": 1}, "futureVersion": 2}
        self.assertEqual(_grammar_problems(newer), [])


class DoctorProgram(unittest.TestCase):
    def run_doctor(self, data=None, broken=False, none=False):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "my-program.py"
            if none:
                path.write_text("print('an older program')\n", encoding="utf-8")
            else:
                exported(path, data if data is not None else block_file([{"type": "rb_start"}]), broken=broken)
            old, sys.argv[0] = sys.argv[0], str(path)
            try:
                return Doctor._doctor_program()
            finally:
                sys.argv[0] = old

    def test_ok(self):
        status, text = self.run_doctor()
        self.assertEqual(status, "ok")
        self.assertIn("matches the format", text)

    def test_broken_payload(self):
        status, text = self.run_doctor(broken=True)
        self.assertEqual(status, "FAIL")
        self.assertIn("isn't readable", text)

    def test_breaks_the_grammar(self):
        status, text = self.run_doctor({"format": "reflection-blocks", "version": 1, "name": "tested",
                                        "program": {"blocks": {"blocks": [{"type": "rb_start", "fields": {"A": {}}}]}}})
        self.assertEqual(status, "FAIL")
        self.assertIn("breaks the format", text)

    def test_older_program_without_a_block_file(self):
        status, text = self.run_doctor(none=True)
        self.assertEqual(status, "NOTE")
        self.assertIn("no block file embedded", text)


if __name__ == "__main__":
    unittest.main()
