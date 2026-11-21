#!/usr/bin/env node
/* Export a program to Python without the page (#441).

    node tools/export.cjs program.json                 # writes program.py (named after the program) next to it
    node tools/export.cjs program.json -o out.py       # or to out.py; "-o -" prints it
    node tools/export.cjs program.json --name rye-rain # the program's name, as the page's Name box (default: the file's)
    node tools/export.cjs program.json --lang de       # print in German, as the page does in German (default: English)
    node tools/export.cjs program.json --model complex # the Model menu's choice (default: default), --backups quick,…
    node tools/export.cjs gallery/*.json --out-dir out # several at once, each named after its program

It writes the Python the page would, byte for byte (only the date in the notes is today's): it runs the editor's own
code from second-thought.html, with the real Blockly package, and loads the file as Import does. Run tools/sync.py
first, so the page holds the current editor. Blockly comes from node_modules (npm install blockly@13.4.0
@blockly/field-multilineinput@13.4.0) or from tests/vendor (bash tests/setup.sh). Needs Node 18 or later.

Saved programs a 'run program' block names, and saved prompts, live in a browser's storage, so a program using them
exports here as it would on a page without them. A right-to-left language's block file positions aren't the page's.
*/
"use strict";
const fs = require("fs"), path = require("path"), vm = require("vm");

const ROOT = path.resolve(__dirname, "..");
const read = file => fs.readFileSync(file, "utf8").replace(/\r\n/g, "\n");

// Blockly and its multiline field, from node_modules if they're installed, else from the tests' copies.
function packageFile(name, file){
  try { return require.resolve(name + "/package.json").replace(/package\.json$/, file); } catch (e) { /* not installed */ }
  const vendored = path.join(ROOT, "tests", "vendor", name.replace(/^@blockly\//, ""), "package", file);
  if (fs.existsSync(vendored)) return vendored;
  throw new Error("Blockly isn't here. Run: npm install blockly@13.4.0 @blockly/field-multilineinput@13.4.0 (or bash tests/setup.sh)");
}

// A stand-in for anything the page has and Node doesn't: it can be called, constructed, read and written, and every
// part of it is another stand-in. It's never a promise, and iterating over it gives nothing.
function standIn(){
  const parts = {};
  return new Proxy(function(){}, {
    get(target, key){
      if (key === Symbol.toPrimitive) return () => "";
      if (key === Symbol.iterator) return function*(){};
      if (key === "then") return undefined;
      if (!(key in parts)) parts[key] = standIn();
      return parts[key];
    },
    set(target, key, value){ parts[key] = value; return true; },
    apply(){ return standIn(); },
    construct(){ return standIn(); },
  });
}

function element(text, value){
  const e = standIn();
  Object.assign(e, { textContent:text === undefined ? "" : text, value:value === undefined ? "" : value, innerHTML:"", hidden:false,
    checked:false, disabled:false, children:[], childNodes:[], dataset:{}, style:{},
    classList:{ add(){}, remove(){}, toggle(){}, contains(){ return false; } } });
  return e;
}

// What each text box starts with in the page's HTML, and the Model menu and backups as a fresh page has them: the
// menus are filled in by the editor's code, which a stand-in element can't keep, so their values are set here.
function startingValues(html, model, backups){
  const values = { tier:model };
  ["bk-1", "bk-2", "bk-3"].forEach((id, i) => { values[id] = backups[i] || ""; });
  for (const m of html.matchAll(/<input\b([^>]*)>/g)) {
    const id = (/\bid="([^"]+)"/.exec(m[1]) || [])[1], value = (/\bvalue="([^"]*)"/.exec(m[1]) || [])[1];
    if (id && value !== undefined) values[id] = value;
  }
  return values;
}

// The page, in Node: the editor's code from second-thought.html, with real Blockly and a headless workspace.
function loadPage(lang = "en", model = "default", backups = []){
  const html = read(path.join(ROOT, "second-thought.html"));
  const data = {};
  for (const m of html.matchAll(/<script type="(?:application\/json|text\/plain)" id="([^"]+)">\n([\s\S]*?)<\/script>/g)) data[m[1]] = m[2];
  const editor = /<script id="editor">\n([\s\S]*?)<\/script>/.exec(html);
  if (!editor) throw new Error("second-thought.html has no editor script: run python tools/sync.py");
  const values = startingValues(html, model, backups), elements = {};
  const document = standIn();
  Object.assign(document, {
    getElementById:id => elements[id] || (elements[id] = element(data[id], values[id])),
    querySelector:() => element(), querySelectorAll:() => [], createElement:() => element(),
    createTextNode:t => element(t), documentElement:element(), body:element(), visibilityState:"visible", fonts:undefined,
  });
  const memory = {};
  const g = {
    document, console, URL, TextEncoder, TextDecoder, Intl, Date, Math, JSON, Promise, AbortController,
    performance, structuredClone, queueMicrotask, atob, btoa, crypto:globalThis.crypto,
    setTimeout:() => 0, clearTimeout(){}, setInterval:() => 0, clearInterval(){}, requestAnimationFrame:() => 0,
    fetch:() => new Promise(() => {}),
    localStorage:{ getItem:k => k in memory ? memory[k] : null, setItem:(k, v) => { memory[k] = String(v); }, removeItem:k => { delete memory[k]; } },
    navigator:{ language:lang, languages:[lang] }, location:{ hash:"", search:"", href:"" },
    ST_LANG:lang, ST_I18N:null, ST_I18N_FILES:{},
  };
  for (const name of ["MutationObserver", "ResizeObserver", "IntersectionObserver", "FileReader", "Image", "Blob", "HTMLElement",
                      "getComputedStyle", "matchMedia", "addEventListener", "removeEventListener", "CustomEvent", "Event", "Worker",
                      "Notification", "speechSynthesis", "SpeechSynthesisUtterance", "alert", "confirm", "prompt", "open",
                      "pdfjsLib", "history", "DOMParser", "XMLSerializer", "scrollTo"]) g[name] = standIn();
  g.window = g.self = g.globalThis = g;
  vm.createContext(g);
  const run = (code, filename) => vm.runInContext(code, g, { filename });

  // Blockly, as the page loads it: the library, the chosen language's words, the multiline field.
  run(read(packageFile("blockly", "blockly.min.js")), "blockly.min.js");
  if (lang !== "en") {
    const file = path.join(ROOT, "lang", lang + ".js");
    if (!fs.existsSync(file)) throw new Error("There's no language " + lang + " (no lang/" + lang + ".js).");
    run(read(file), "lang/" + lang + ".js");
    g.ST_I18N = g.ST_I18N_FILES[lang];
    if (g.ST_I18N.blockly && g.ST_I18N.blockly !== "en") run(read(packageFile("blockly", "msg/" + g.ST_I18N.blockly + ".js")), "msg/" + g.ST_I18N.blockly + ".js");
    if (g.ST_I18N.blocklyMsg) Object.assign(g.Blockly.Msg, g.ST_I18N.blocklyMsg);
    if (g.ST_I18N.dir === "rtl") g.document.documentElement.dir = "rtl";
  }
  const gen = new Proxy({}, { get:(o, k) => k === "Order" ? new Proxy({}, { get:() => 0 }) : (k === "forBlock" ? {} : undefined) });
  ["Blockly.JavaScript", "Blockly.Dart", "Blockly.Lua", "Blockly.PHP", "Blockly.Python"].forEach(n => { g[n] = gen; });
  run(read(packageFile("@blockly/field-multilineinput", "dist/index.js")), "field-multilineinput");

  // The canvas: a headless workspace, so blocks load, save and are read exactly as on the page, and nothing is drawn.
  // Whatever only a drawn workspace has (zoom, scrolling, the toolbox) is a stand-in.
  g.Blockly.inject = (where, options) => {
    const ws = new g.Blockly.Workspace(new g.Blockly.Options(Object.assign({}, options, { toolbox:undefined })));
    const extra = standIn();
    return new Proxy(ws, {
      get(target, key){
        if (key in target) { const v = target[key]; return typeof v === "function" ? v.bind(target) : v; }
        if (key === "getWidth") return () => 0;
        return extra[key];
      },
    });
  };
  run(editor[1], "second-thought.html (editor)");
  return g;
}

const slug = name => String(name || "").trim().replace(/\.json$/i, "").replace(/[^\w\- ]+/g, "").replace(/\s+/g, "-").slice(0, 80) || "my-program";

function main(argv){
  const args = { files:[], out:null, dir:null, name:null, lang:"en", model:"default", backups:[] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "-o" || a === "--out") args.out = argv[++i];
    else if (a === "--out-dir") args.dir = argv[++i];
    else if (a === "--name") args.name = argv[++i];
    else if (a === "--lang") args.lang = argv[++i];
    else if (a === "--model") args.model = argv[++i];
    else if (a === "--backups") args.backups = String(argv[++i] || "").split(",").filter(Boolean);
    else if (a === "-h" || a === "--help") { process.stdout.write(USAGE); return 0; }
    else if (a.startsWith("-") && a !== "-") { process.stderr.write("Unknown option " + a + ".\n" + USAGE); return 2; }
    else args.files.push(a);
  }
  if (!args.files.length) { process.stderr.write(USAGE); return 2; }
  if (args.files.length > 1 && (args.out || args.name)) { process.stderr.write("-o and --name are for one program; use --out-dir for several.\n"); return 2; }
  const page = loadPage(args.lang, args.model, args.backups);
  let failed = 0;
  for (const file of args.files) {
    const text = fs.readFileSync(file, "utf8");
    let fileName = "";
    try { fileName = JSON.parse(text.replace(/^\uFEFF/, "")).name || ""; }
    catch (e) { process.stderr.write(file + " isn't a block file (it isn't JSON).\n"); failed++; continue; }
    const name = args.name || fileName || path.basename(file).replace(/\.json$/i, "");
    let code;
    try { code = page.__exportBlockFile(text, name); }
    catch (e) { process.stderr.write(file + ": " + (e && e.message ? e.message : e) + "\n"); failed++; continue; }
    const out = args.out || path.join(args.dir || path.dirname(file), slug(name) + ".py");
    if (out === "-") process.stdout.write(code);
    else { fs.writeFileSync(out, code); process.stderr.write("Wrote " + out + "\n"); }
  }
  return failed ? 1 : 0;
}

const USAGE = "Usage: node tools/export.cjs program.json [more.json ...] [-o out.py | --out-dir DIR] [--name NAME]\n" +
  "       [--lang CODE] [--model TIER] [--backups TIER,TIER]\n";

if (require.main === module) process.exitCode = main(process.argv.slice(2));
module.exports = { loadPage };
