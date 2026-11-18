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

// The reviewer's choice on the review blocks (#426): who checks the draft.
test("reviewerTier picks the same model, another maker's, or a named one", () => {
  assert.equal(JSON.stringify(units.reviewerTier("same", "default")), JSON.stringify({ tier: "default", note: null }));
  assert.equal(JSON.stringify(units.reviewerTier("", "default")), JSON.stringify({ tier: "default", note: null }));
  assert.equal(JSON.stringify(units.reviewerTier("gemini-default", "default")), JSON.stringify({ tier: "gemini-default", note: null }));
  const hasGemini = s => s.name === "Gemini";
  assert.equal(units.otherMakerTiers("default", hasGemini)[0], "gemini-default");
  assert.equal(JSON.stringify(units.reviewerTier("another", "default", hasGemini)), JSON.stringify({ tier: "gemini-default", note: null }));
  const r = units.reviewerTier("another", "default", () => false);
  assert.equal(r.tier, "default");
  assert.match(r.note, /No other maker's model has a key on this page/);
  // the same maker is not "another maker"
  assert.equal(JSON.stringify(units.otherMakerTiers("gemini-default", s => s.name === "Gemini")), "[]");
  assert.equal(units.makerOfTier("default"), "Anthropic");
  assert.equal(units.makerOfTier("gemini-default"), "Google");
});

// A rule offered when someone sends a result back (#428) is merged into the review block's rules, not twice.
test("mergeRule adds the offered rule once", () => {
  assert.equal(units.mergeRule("", "prices in pounds, not dollars"), "prices in pounds, not dollars");
  assert.equal(units.mergeRule("clear", "prices in pounds, not dollars"), "clear; prices in pounds, not dollars");
  assert.equal(units.mergeRule("clear; titled", "prices in pounds, not dollars"), "clear; titled; prices in pounds, not dollars");
  assert.equal(units.mergeRule("clear\ntitled", "titled"), "clear\ntitled");
  assert.equal(units.mergeRule("clear; titled", "titled"), "clear; titled");
});
