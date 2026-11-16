// review's rules in the page (#424): parseRules, reviewVerdicts and stuckRule. The cases are in tests/parity/review.json,
// which the runtime's tests (tests/unit/test_review.py) read too.
"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const path = require("path");
const { load, read, ROOT } = require("./page.cjs");

const units = load().__editorUnits;
const parity = name => JSON.parse(read(path.join(ROOT, "tests", "parity", name)));

test("parseRules gives the runtime's answers", () => {
  for (const [criteria, want] of parity("review.json").parse_rules.answers)
    assert.equal(JSON.stringify(units.parseRules(criteria)), JSON.stringify(want), JSON.stringify(criteria));
});

test("reviewVerdicts gives the runtime's answers", () => {
  for (const [rules, reply, want] of parity("review.json").review_verdicts.answers) {
    const got = units.reviewVerdicts(rules, reply);
    assert.equal(JSON.stringify({ approved: got.approved, problems: got.problems, met: got.met, unmet: got.unmet, verdicts: got.verdicts }),
                 JSON.stringify(want), JSON.stringify([rules, reply]));
  }
});

test("stuckRule gives the runtime's answers", () => {
  for (const [prev, unmet, want] of parity("review.json").stuck_rule.answers)
    assert.equal(units.stuckRule(prev, unmet), want, JSON.stringify([prev, unmet]));
});
