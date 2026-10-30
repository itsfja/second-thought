/* The editor's code (web/editor/*.js) run in Node, without a browser, for its unit tests.

The page's data (the safety rules, capabilities, services, gallery...) comes from the tags in second-thought.html, so
run tools/sync.py first. Everything a browser would give it (the document, Blockly, storage) is a stand-in that
accepts anything and does nothing, so only functions that don't need the page can be tested this way; they're listed
in window.__editorUnits, at the end of web/editor/23-schedules.js.

  const { load } = require("./page.cjs");
  const units = load().__editorUnits;          // English
  const de = load({ lang:"de" }).__editorUnits; // with lang/de.js loaded, as the page does for German
*/
"use strict";
const fs = require("fs"), path = require("path"), vm = require("vm");

const ROOT = path.resolve(__dirname, "..", "..");

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

function element(text){
  const e = standIn();
  Object.assign(e, { textContent:text === undefined ? "" : text, value:"", innerHTML:"", hidden:false, checked:false,
    children:[], childNodes:[], dataset:{}, style:{}, classList:{ add(){}, remove(){}, toggle(){}, contains(){ return false; } } });
  return e;
}

function load(options = {}){
  const lang = options.lang || "en";
  const page = fs.readFileSync(path.join(ROOT, "second-thought.html"), "utf8");
  const data = {};
  for (const m of page.matchAll(/<script type="(?:application\/json|text\/plain)" id="([^"]+)">\n([\s\S]*?)<\/script>/g)) data[m[1]] = m[2];

  const elements = {};
  const document = standIn();
  Object.assign(document, {
    getElementById:id => elements[id] || (elements[id] = element(data[id])),
    querySelector:() => element(), querySelectorAll:() => [], createElement:() => element(),
    documentElement:element(), body:element(), visibilityState:"visible",
  });
  // Blockly's block definitions are kept, so the code can see which blocks exist.
  const Blockly = standIn();
  Blockly.Blocks = {};
  Blockly.defineBlocksWithJsonArray = defs => defs.forEach(d => { Blockly.Blocks[d.type] = { json:d }; });

  const memory = {};
  const g = {
    document, Blockly, console, URL, TextEncoder, TextDecoder, Intl, Date, Math, JSON, Promise, AbortController,
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
  if (lang !== "en") {
    vm.runInContext(fs.readFileSync(path.join(ROOT, "lang", lang + ".js"), "utf8"), g, { filename:"lang/" + lang + ".js" });
    g.ST_I18N = g.ST_I18N_FILES[lang];
    if (!g.ST_I18N) throw new Error("lang/" + lang + ".js didn't load");
  }
  // One script, as in the page. A line in an error is given as the file it's in.
  const dir = path.join(ROOT, "web", "editor"), files = [];
  let code = "", line = 1;
  for (const name of fs.readdirSync(dir).filter(f => f.endsWith(".js")).sort()) {
    let text = fs.readFileSync(path.join(dir, name), "utf8");
    if (!text.endsWith("\n")) text += "\n";
    files.push([line, name]);
    code += text;
    line += text.split("\n").length - 1;
  }
  const where = n => { const f = files.filter(([start]) => start <= n).pop(); return "web/editor/" + f[1] + ":" + (n - f[0] + 1); };
  try {
    vm.runInContext(code, g, { filename:"EDITOR" });
  } catch (e) {
    if (e && e.stack) e.stack = e.stack.replace(/EDITOR:(\d+)(?::\d+)?/g, (m, n) => where(+n));
    throw e;
  }
  return g;
}

// Objects made in the editor have its Object and Array, so compare them with deepEqual after this.
const plain = v => JSON.parse(JSON.stringify(v));

module.exports = { load, plain, ROOT };
