// Loading old programs (migrations), spotting blocks the page doesn't have, what each block declares it can do, and
// the page's words in another language.
"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const { load, plain } = require("./page.cjs");

test("a program from an older block format is brought up to date, one version at a time, without changing the original", () => {
  const page = load(), units = page.__editorUnits;
  page.__setFormat(3, {
    1:s => { s.blocks.languageVersion = 2; return s; },
    2:s => { s.blocks.blocks.forEach(b => { if (b.type === "rb_old") b.type = "rb_say"; }); },  // changing it in place is fine
  });
  const old = { blocks:{ languageVersion:0, blocks:[{ type:"rb_old" }] } };
  const { state, from } = units.migrateProgram(old, 1);
  assert.equal(from, 1);
  assert.deepEqual(plain(state), { blocks:{ languageVersion:2, blocks:[{ type:"rb_say" }] } });
  assert.equal(old.blocks.blocks[0].type, "rb_old", "the program passed in is left as it was");
  assert.equal(units.migrateProgram(state, 3).state, state, "an up-to-date program is passed straight through");
  assert.equal(units.migrateProgram(old, "nonsense").from, 1, "no version means version 1");
  assert.throws(() => units.migrateProgram(old, 4), /newer Second Thought/);
});

test("the blocks a program uses that the page doesn't have", () => {
  const units = load().__editorUnits;
  const program = { blocks:{ blocks:[
    { type:"rb_add_result", id:"a", inputs:{ TEXT:{ block:{ type:"made_up_block", fields:{} } } },
      next:{ block:{ type:"another_unknown", id:"b" } } },
    { type:"rb_add_result", fields:{ TEXT:"known" } },
  ] } };
  assert.deepEqual(plain(units.unknownTypes(program)).sort(), ["another_unknown", "made_up_block"]);
  assert.deepEqual(plain(units.unknownTypes({ blocks:{ blocks:[{ type:"rb_add_result", fields:{ type:"not_a_block" } }] } })), [],
    "a field that happens to be called 'type' isn't a block");
});

test("every block says what it lets a program do, from the runtime's list", () => {
  const page = load(), c = plain(page.__capabilityCheck());
  const types = plain(page.__blockDefs().map(d => d.type));
  const listed = new Set(c.blocks.concat(["rb_agent_builtin"]));  // the agent's built-in tool: by its kind, checked next
  assert.deepEqual(types.filter(t => !listed.has(t) && !c.none.includes(t)), [], "blocks in neither CAP_BLOCKS nor NO_CAPABILITY");
  assert.deepEqual(c.blocks.filter(t => c.none.includes(t)), [], "blocks in both");
  assert.deepEqual(c.kinds.slice().sort(), c.agentKinds.slice().sort(), "every agent tool kind says what it lets a program do");
  assert.deepEqual(c.used.slice().sort(), c.ids.slice().sort(), "each capability comes from some block or tool");
  const runtime = plain(JSON.parse(page.document.getElementById("capabilities").textContent).map(x => x[0]));
  assert.deepEqual(c.ids, runtime, "the page has the runtime's list, in its order");
});

test("page words: placeholders are filled, and a word with no translation stays in English", () => {
  const en = load().__editorUnits, de = load({ lang:"de" }).__editorUnits;
  assert.equal(en.tr("Backups ({n})", { n:3 }), "Backups (3)");
  assert.equal(en.tr("{a} and {b}", { a:1 }), "1 and {b}", "a placeholder with no value is left showing");
  assert.equal(en.tr("Backups ({n})"), "Backups ({n})");
  assert.equal(de.tr("Schedules: on"), "Zeitpläne: an");
  assert.match(de.tr("Backups ({n})", { n:3 }), /3/);
  assert.equal(de.tr("A sentence nobody has translated"), "A sentence nobody has translated");
});

test("blocks in another language: the labels change, the values saved in programs don't", () => {
  const de = load({ lang:"de" }).__editorUnits;
  const def = { type:"rb_when_time", message0:"when it's %1", tooltip:"English tooltip",
    args0:[{ type:"field_dropdown", name:"DAYS", options:[["every day", "every"], ["on weekdays", "weekdays"], ["at weekends", "weekends"]] }] };
  const out = plain(de.localizeBlock(def));
  assert.deepEqual(out.args0[0].options.map(o => o[1]), ["every", "weekdays", "weekends"]);
  assert.deepEqual(out.args0[0].options.map(o => o[0]), ["jeden Tag", "an Wochentagen", "am Wochenende"]);
  assert.notEqual(out.message0, "when it's %1");
  assert.equal(def.args0[0].options[0][0], "every day", "the English definition is left as it was");
  assert.equal(load().__editorUnits.localizeBlock(def), def, "in English the block is used as it is");
});

test("helpers: short, pad2, num and str", () => {
  const u = load().__editorUnits;
  assert.equal(u.short("  lots   of\nspace  ", 40), "lots of space");
  assert.equal(u.short("abcdefghij", 5), "abcd…");
  assert.equal(u.pad2(7), "07");
  assert.equal(u.num("2.5"), 2.5); assert.equal(u.num("nope"), 0); assert.equal(u.num(true), 1);
  assert.equal(u.str(null), ""); assert.equal(u.str(["a", "b"]), "a\nb"); assert.equal(u.str(3), "3");
});
