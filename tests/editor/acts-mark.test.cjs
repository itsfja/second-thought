// The mark on acting blocks (#448): every acting capability in CAPABILITIES is carried by some block or agent
// tool kind, and gets a mark — a triangle when the form asks first, a diamond for the no-asking forms.
"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const path = require("path");
const { load, read, ROOT } = require("./page.cjs");

const page = load();
const html = read(path.join(ROOT, "second-thought.html"));
const caps = JSON.parse(/id="capabilities">\n([\s\S]*?)<\/script>/.exec(html)[1]);
const { blocks, kinds } = page.__capBlocks();
const fake = (type, fields) => ({ type, getFieldValue: n => (fields || {})[n] });

test("every acting capability is carried by some block or agent kind, and marked", () => {
  for (const [id, label, acts] of caps) {
    if (!acts) continue;
    let carried = null;
    for (const [t, c] of Object.entries(blocks)) {
      const cap = typeof c === "function" ? c(fake(t, { MODE:"live" })) : c;
      if (cap === id) { carried = { block:t }; break; }
    }
    if (!carried) for (const [k, c] of Object.entries(kinds)) if (c === id) { carried = { kind:k }; break; }
    assert.ok(carried, `acting capability ${id} (${label}) is carried by no block or agent kind`);
    const b = carried.block ? fake(carried.block, { MODE:"live" }) : fake("rb_agent_builtin", { KIND:carried.kind });
    const mark = page.__actsMark(b);
    assert.ok(mark === "triangle" || mark === "diamond", `${id} gets a mark, got ${mark}`);
  }
});

test("asking forms get the triangle, no-asking forms the diamond, reads and model-only blocks none", () => {
  assert.equal(page.__actsMark(fake("rb_agent_builtin", { KIND:"telegram_send" })), "triangle");
  assert.equal(page.__actsMark(fake("rb_agent_builtin", { KIND:"telegram_send_free" })), "diamond");
  assert.equal(page.__actsMark(fake("rb_agent_builtin", { KIND:"ha_act_free" })), "diamond");
  assert.equal(page.__actsMark(fake("rb_tg_send")), "triangle");
  assert.equal(page.__actsMark(fake("rb_ha_call")), "triangle");
  assert.equal(page.__actsMark(fake("rb_agent_kraken", { MODE:"live" })), "triangle");
  assert.equal(page.__actsMark(fake("rb_calendar")), null);   // a read carries no mark
  assert.equal(page.__actsMark(fake("rb_say")), null);        // model only
  assert.equal(page.__actsMark(fake("rb_agent_builtin", { KIND:"calc" })), null);
});
