// The block palette's colours (#447): every colour in HUES must give its white bold label at least 4.5:1 contrast
// (WCAG, computed the same way browsers do), and every connection shares the one Connections family colour, so the
// remaining colours say what a block is for. A new colour that slips under fails this test.
"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const path = require("path"), fs = require("fs");
const { read, ROOT } = require("./page.cjs");

function hues(){
  const src = read(path.join(ROOT, "web", "editor", "01-theme.js"));
  const m = /const HUES = (\{[\s\S]*?\n  \});/.exec(src);
  assert.ok(m, "HUES found in web/editor/01-theme.js");
  return eval("(" + m[1] + ")");  // a plain object literal of key:"#RRGGBB"
}

// WCAG relative luminance and contrast ratio against white.
function luminance(hex){
  const n = parseInt(hex.slice(1), 16);
  const lin = c => { c /= 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
  return 0.2126 * lin((n >> 16) & 255) + 0.7152 * lin((n >> 8) & 255) + 0.0722 * lin(n & 255);
}
const contrastWithWhite = hex => (1.0 + 0.05) / (luminance(hex) + 0.05);

// The service ids: the palette categories that carry one (03-toolbox.js), which must all be the conn family.
function serviceIds(){
  const src = read(path.join(ROOT, "web", "editor", "03-toolbox.js"));
  return [...new Set([...src.matchAll(/service:"(\w+)"/g)].map(m => m[1]))];
}

test("every colour in HUES gives its white label at least 4.5:1 contrast", () => {
  const H = hues();
  assert.ok(Object.keys(H).length >= 30, `HUES has ${Object.keys(H).length} entries`);
  const bad = [];
  for (const [k, v] of Object.entries(H)) {
    assert.match(v, /^#[0-9A-F]{6}$/, `${k} is a hex colour`);
    const r = contrastWithWhite(v);
    if (r < 4.5) bad.push(`${k} ${v} ${r.toFixed(2)}:1`);
  }
  assert.deepEqual(bad, [], "colours under 4.5:1 with a white label: " + bad.join(", "));
});

test("every connection is the one Connections family colour", () => {
  const H = hues();
  const ids = serviceIds();
  assert.ok(ids.length >= 15, `found ${ids.length} service categories`);
  for (const id of ids) {
    assert.ok(H[id], `HUES has an entry for connection ${id}`);
    assert.equal(H[id], H.conn, `connection ${id} is not the Connections colour ${H.conn}`);
  }
  // connections/<name>/hues.js parts say the same, so a new connection can't arrive in its own colour
  for (const dir of fs.readdirSync(path.join(ROOT, "connections"))) {
    const part = path.join(ROOT, "connections", dir, "hues.js");
    if (!fs.existsSync(part)) continue;
    for (const m of read(part).matchAll(/(\w+):"(#[0-9A-Fa-f]{6})"/g))
      assert.equal(m[2].toUpperCase(), H.conn.toUpperCase(), `connections/${dir}/hues.js ${m[1]} is not the Connections colour`);
  }
});

test("the job colours stay distinct, so colour still says what a block is for", () => {
  const H = hues();
  const ids = new Set(serviceIds());
  const jobs = Object.entries(H).filter(([k]) => !ids.has(k) && k !== "conn");
  const seen = new Map();
  for (const [k, v] of jobs) {
    const other = seen.get(v.toUpperCase());
    assert.ok(!other, `job colours ${other} and ${k} are the same (${v})`);
    seen.set(v.toUpperCase(), k);
  }
});
