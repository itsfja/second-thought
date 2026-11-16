// The review's exact checks (#425): exactChecks on the page. The cases are in tests/parity/checks.json,
// which the runtime's tests (tests/unit/test_checks.py) read too.
"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const path = require("path");
const { load, read, ROOT } = require("./page.cjs");

const units = load().__editorUnits;
const parity = name => JSON.parse(read(path.join(ROOT, "tests", "parity", name)));

test("exactChecks gives the runtime's answers", () => {
  for (const [text, checks, want] of parity("checks.json").exact_checks.answers) {
    const got = units.exactChecks(text, checks);
    assert.equal(JSON.stringify(got.map(g => ({ rule: g.rule, met: g.met, problem: g.problem, shows: g.shows }))),
                 JSON.stringify(want), JSON.stringify([text, checks]));
  }
});
