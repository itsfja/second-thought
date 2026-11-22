// Named inputs (#442): inputValue on the page. The cases are in tests/parity/inputs.json, which the runtime's tests
// (tests/unit/test_inputs.py) read too.
"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const path = require("path");
const { load, read, ROOT } = require("./page.cjs");

const units = load().__editorUnits;
const parity = name => JSON.parse(read(path.join(ROOT, "tests", "parity", name)));

test("inputValue gives the runtime's answers", () => {
  for (const [name, type, raw, value, why] of parity("inputs.json").answers) {
    const got = units.inputValue({ name, type, def:"" }, raw);
    assert.deepEqual([got.value === undefined ? null : got.value, got.why || null], [value, why], JSON.stringify([type, raw]));
  }
});
