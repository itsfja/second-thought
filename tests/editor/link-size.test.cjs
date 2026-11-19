// Program links (#436): every gallery program packed the way Copy link packs it — #p= + the compact block file,
// deflated (deflate-raw) and in base64url — stays under 1,800 characters, and at least half under 1,000.
"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const fs = require("fs"), path = require("path"), zlib = require("zlib");
const { read, ROOT } = require("./page.cjs");

// The page's own block-file version, so this test can't drift from the editor's code.
const fmt = read(path.join(ROOT, "web", "editor", "07-format.js"));
const FORMAT_VERSION = Number(/let FORMAT_VERSION = (\d+)/.exec(fmt)[1]);
const b64url = buf => buf.toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

test("every gallery program fits in a #p= link under 1,800 characters, half under 1,000", () => {
  const files = fs.readdirSync(path.join(ROOT, "gallery")).filter(f => f.endsWith(".json"));
  assert.ok(files.length >= 80, `the gallery should have at least 80 programs (found ${files.length})`);
  const sizes = files.map(f => {
    const g = JSON.parse(read(path.join(ROOT, "gallery", f)));
    // The same compact payload linkPayload() packs: the program with its version and name — the #p= hash itself
    // says the link is ours, so no format marker, and no gallery metadata or exported timestamp either.
    const payload = JSON.stringify({ version: FORMAT_VERSION, name: g.name, program: g.program });
    return { file: f, chars: 3 + b64url(zlib.deflateRawSync(Buffer.from(payload, "utf8"))).length };
  });
  const over = sizes.filter(s => s.chars >= 1800);
  assert.deepEqual(over.map(s => `${s.file} (${s.chars})`), [], "links of 1,800 characters or more");
  const under1000 = sizes.filter(s => s.chars < 1000).length;
  assert.ok(under1000 >= sizes.length / 2, `only ${under1000} of ${sizes.length} links are under 1,000 characters`);
  sizes.sort((a, b) => b.chars - a.chars);
  console.log(`    #p= link sizes: largest ${sizes[0].file} at ${sizes[0].chars} chars; under 1,000: ${under1000}/${sizes.length}`);
});
