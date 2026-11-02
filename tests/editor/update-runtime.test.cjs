// The page's side of --update-runtime (#244): its code hash agrees with the runtime's, and it still finds a program's
// blocks in a file that carries the runtime, which mentions the line the page looks for.
"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const path = require("path");
const { load, read, ROOT } = require("./page.cjs");

const units = load().__editorUnits;
const MARK = "# ---- Second Thought program: lets the block editor import this file again ----";

test("the code hash gives the runtime's answers", () => {
  for (const [text, want] of JSON.parse(read(path.join(ROOT, "tests", "parity", "code_hash.json"))).answers)
    assert.equal(units.codeHash(text), want, JSON.stringify(text));
});

test("a file with the runtime inside imports, unedited, with its runtime's version", () => {
  const runtime = read(path.join(ROOT, "python", "runtime.py"));
  const version = runtime.match(/^RUNTIME_VERSION = "([^"]+)"/m)[1];
  const code = '"""My program."""\n\n' + runtime + "\nR = Runtime()\n";
  const blocks = Buffer.from(JSON.stringify({ format:"second-thought", version:1, name:"t", program:{ blocks:{} } })).toString("base64");
  const file = code + "\n\n" + MARK + "\n# CODE-HASH: " + units.codeHash(code) + "\n# BLOCKS:\n# " + blocks + "\n";
  const got = units.readExported(file);
  assert.ok(got, "the page didn't find the program's blocks");
  assert.equal(got.data.name, "t");
  assert.equal(got.edited, false);
  assert.equal(got.runtime, version);
});
