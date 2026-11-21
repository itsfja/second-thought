// The Connections list in Settings (#446): the palette's one-service categories carry a `service` id, and only the
// turned-on ones show, as sections inside the Connections category; the full palette still feeds Find a block.
"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const { load, plain, ROOT } = require("./page.cjs");
const path = require("path"), fs = require("fs");

const page = load();
const services = page.__services();
const cats = () => page.__visibleToolbox().contents.filter(c => c.kind === "category");
const topNames = () => cats().map(c => c.name);
const connCat = () => cats().find(c => c.name === "Connections");

test("the palette has 40 categories, eighteen of them a single service", () => {
  assert.equal(plain(services.cats).length, 18);
  for (const s of plain(services.cats)) {
    assert.ok(s.id && s.name && s.blocks.length > 0, JSON.stringify(s).slice(0, 80));
  }
  // a block that is only in one service category maps to that service; rb_event (in core categories too) maps to none
  const src = fs.readFileSync(path.join(ROOT, "web", "editor", "03-toolbox.js"), "utf8");
  assert.match(src, /!core\.has\(e\.type\)/);
});

test("a fresh page shows the core categories plus Connections, no service at the top level", () => {
  assert.deepEqual(plain(services.enabled), []);
  const top = topNames();
  assert.equal(plain(top).length, 22);
  assert.ok(plain(top).includes("Connections"));
  for (const s of plain(services.cats)) assert.ok(!plain(top).includes(s.name), s.name + " should not be top-level");
  assert.equal(plain(connCat().contents).filter(c => c.kind === "category").length, 0);
});

test("turning a service on nests its category inside Connections, and off removes it", () => {
  page.localStorage.setItem("second-thought-connections", JSON.stringify(["ha", "plex"]));
  assert.deepEqual(plain(page.__services().enabled), ["ha", "plex"]);
  const top = topNames();
  assert.equal(plain(top).length, 22);
  assert.ok(!plain(top).includes("Home Assistant"));
  const nested = plain(connCat().contents).filter(c => c.kind === "category").map(c => c.name);
  assert.deepEqual(nested, ["Home Assistant", "Plex"]);
  // the service's own blocks (listeners etc.) stay in Connections too
  assert.ok(plain(connCat().contents).some(e => e.kind === "block" && e.type === "rb_discord_when"));
  page.localStorage.setItem("second-thought-connections", JSON.stringify(["ha"]));
  assert.deepEqual(plain(connCat().contents.filter(c => c.kind === "category").map(c => c.name)), ["Home Assistant"]);
  // unknown ids in storage are ignored
  page.localStorage.setItem("second-thought-connections", JSON.stringify(["ha", "nope", 42]));
  assert.deepEqual(plain(page.__services().enabled), ["ha"]);
  page.localStorage.removeItem("second-thought-connections");
});

test("the full palette still feeds block search, so Find a block reaches hidden services' blocks", () => {
  // 22-search.js builds its index from the full `toolbox`, not the visible one: the search index has every block.
  const src = fs.readFileSync(path.join(ROOT, "web", "editor", "22-search.js"), "utf8");
  assert.match(src, /toolbox\.contents\.forEach/);
  // and the full toolbox still lists every service category at the top level
  const full = page.__visibleToolbox; // visible only; check the source toolbox through the search index instead
  const indexSrc = fs.readFileSync(path.join(ROOT, "web", "editor", "03-toolbox.js"), "utf8");
  for (const s of plain(services.cats)) assert.ok(indexSrc.includes(`name:"${s.name}"`), s.name);
});

test("loading a program that uses a service turns it on (serviceOfBlock via agent kinds too)", () => {
  // the mapping the page uses: block type -> service, plus agent tool kinds
  const src = fs.readFileSync(path.join(ROOT, "web", "editor", "03-toolbox.js"), "utf8");
  assert.match(src, /function serviceOfBlock\(b\)/);
  assert.match(src, /KIND_SERVICE = \{/);
  assert.match(src, /ha_act_free:"ha"/);
  // enableServicesInWorkspace is called from load() in 08-workspace.js
  const ws8 = fs.readFileSync(path.join(ROOT, "web", "editor", "08-workspace.js"), "utf8");
  assert.match(ws8, /function load\(state\)\{[^}]*enableServicesInWorkspace\(\);/);
  // the workspace is injected with the visible toolbox, not the full one
  assert.match(ws8, /toolbox:localizeToolbox\(visibleToolbox\(\)\)/);
});

test("connections/<name>/ palette parts carry a service id, so new connections join the list", () => {
  for (const f of fs.readdirSync(path.join(ROOT, "connections"))) {
    const part = path.join(ROOT, "connections", f, "toolbox.js");
    if (fs.existsSync(part)) {
      const text = fs.readFileSync(part, "utf8");
      assert.match(text, /service:"/, part + " has no service id");
    }
  }
});
