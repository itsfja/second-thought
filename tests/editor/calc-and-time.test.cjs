// calculate and time_plus in the page. The cases are in tests/parity/, which the runtime's tests read too.
"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const fs = require("fs"), path = require("path");
const { load, ROOT } = require("./page.cjs");

const units = load().__editorUnits;
const parity = name => JSON.parse(fs.readFileSync(path.join(ROOT, "tests", "parity", name), "utf8"));
const message = f => { try { f(); } catch (e) { return e.message; } assert.fail("expected an error"); };

test("calculate gives the runtime's answers", () => {
  for (const [expr, want] of parity("calc.json").answers) assert.equal(units.calcText(expr), expr + " = " + want, expr);
});

test("calculate's mistakes are the runtime's", () => {
  for (const [expr, why] of parity("calc.json").mistakes) assert.match(message(() => units.calcText(expr)), new RegExp(why), JSON.stringify(expr));
});

test("time_plus gives the runtime's answers", () => {
  for (const [when, add, want] of parity("time_plus.json").answers) assert.equal(units.timePlusText(when, add), want, when + " + " + add);
});

test("time_plus refuses what the runtime refuses", () => {
  for (const when of parity("time_plus.json").mistakes) assert.throws(() => units.timePlusText(when, 10), when);
});
