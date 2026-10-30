  // 08-workspace.js: The Blockly workspace: injecting it, saving and loading, the autosave.
  /* ---------- Workspace ---------- */
  const ws = Blockly.inject("blockly", {
    toolbox:localizeToolbox(toolbox), renderer:"zelos", theme:makeTheme(isDark()),
    grid:{ spacing:24, length:2, colour:isDark() ? "#2A2E40" : "#E4E7F0", snap:true },
    zoom:{ controls:false, wheel:true, startScale:0.8, maxScale:2, minScale:0.35 },
    trashcan:false, sounds:false, move:{ scrollbars:true, drag:true, wheel:false },
    rtl:document.documentElement.dir === "rtl"
  });
  /* Right to left, Blockly keeps a top block's x from the workspace's right edge as it is when the program loads or saves,
     and that width changes once the page settles, so x would drift. Here x is always measured from one fixed edge (the
     width when the page opened): a program then saves the same x in any language, and loads where it was. */
  const RTL_EDGE = ws.RTL ? ws.getWidth() : 0;
  const shiftX = (state, by, round) => ((state && state.blocks && state.blocks.blocks) || []).forEach(b => {
    if (typeof b.x === "number") b.x = round ? Math.round(b.x + by) : b.x + by; });
  function saveWs(){ const state = Blockly.serialization.workspaces.save(ws); if (ws.RTL) shiftX(state, RTL_EDGE - ws.getWidth(), true); return state; }
  function loadWs(state){
    if (ws.RTL) { state = JSON.parse(JSON.stringify(state)); shiftX(state, ws.getWidth() - RTL_EDGE); }
    Blockly.serialization.workspaces.load(state, ws);
  }
  function load(state){ ws.clear(); loadWs(state); ws.scrollCenter && ws.scroll(0, 0); }
  // Blocks are measured as they're drawn; a language's own font may arrive after that, so measure them again once it has.
  if (window.ST_I18N && window.ST_I18N.font && document.fonts && document.fonts.load)
    // A letter of the language's own name is in its script, so the font is loaded for that script, whichever it is.
    document.fonts.load('bold 12px "' + window.ST_I18N.font + '"', [...window.ST_I18N.name].find(c => c > "\u02ff") || "\u{10000}").then(() => {
      ws.getAllBlocks(false).forEach(b => b.inputList.forEach(i => i.fieldRow.forEach(f => f.forceRerender())));
      ws.refreshToolboxSelection();
    }, () => {});
  // The blocks' language. Changing it saves the program, then reloads the page in the new language.
  (function langPicker(){
    const sel = $("lang"), langs = JSON.parse(document.getElementById("i18n").textContent || "{}");
    [["en", "English"]].concat(Object.keys(langs).sort().map(k => [k, langs[k].name || k])).forEach(([k, name]) => {
      const o = document.createElement("option"); o.value = k; o.textContent = name; sel.appendChild(o);
    });
    sel.value = window.ST_LANG || "en";
    // The chosen language's words didn't load (lang/<language>.js missing or unreachable): say so, in English, since
    // that's what the page is showing. The choice is kept, so reloading tries again.
    if (window.ST_I18N_MISSING) {
      const b = $("banner");
      b.textContent = "The " + window.ST_I18N_MISSING + " words for this page couldn't be loaded, so it's in English. Check your connection and reload to try again.";
      b.hidden = false;
    }
    sel.addEventListener("change", () => {
      try { localStorage.setItem(STORE_KEY, JSON.stringify(saveWs())); localStorage.setItem(STORE_KEY + ":version", String(FORMAT_VERSION)); } catch(e) {}
      try { localStorage.setItem("second-thought-language", sel.value); } catch(e) {}
      location.reload();
    });
  })();
  // Test cases for the program on the canvas (see 'Save as test case' and Run tests). They travel with the program: in
  // block files, exported Python and its zip (<program>.tests.json), saved programs and what the page keeps.
  let programTests = [];
  function setTests(tests){ programTests = Array.isArray(tests) ? tests.filter(t => t && typeof t === "object") : []; testsChanged(); }
  function testsChanged(){
    try { localStorage.setItem(STORE_KEY + ":tests", JSON.stringify(programTests)); } catch(e) {}
    const b = document.getElementById("log-tests");
    if (b) { b.hidden = !programTests.length; b.textContent = tr("Run tests ({n})", { n:programTests.length }); }
  }
  let saved = null;
  try { const raw = localStorage.getItem(STORE_KEY); if (raw) saved = migrateProgram(JSON.parse(raw), localStorage.getItem(STORE_KEY + ":version")).state; } catch(e) {}
  try { programTests = JSON.parse(localStorage.getItem(STORE_KEY + ":tests") || "[]"); if (!Array.isArray(programTests)) programTests = []; } catch(e) { programTests = []; }
  try { load(saved || EXAMPLES.review()); } catch(e) { load(EXAMPLES.review()); }
  ws.addChangeListener(ev => {
    if (ev.isUiEvent) return;
    try { localStorage.setItem(STORE_KEY, JSON.stringify(saveWs())); localStorage.setItem(STORE_KEY + ":version", String(FORMAT_VERSION)); } catch(e) {}
  });
  $("zin").onclick = () => ws.zoomCenter(1);
  $("zout").onclick = () => ws.zoomCenter(-1);
  $("zfit").onclick = () => ws.zoomToFit();
  (function fillExamples(){
    const sel = $("example");
    EXAMPLE_CATEGORIES.forEach(cat => {
      const g = document.createElement("optgroup"); g.label = tr(cat);
      EXAMPLE_LIST.filter(e => e.cat === cat).forEach(e => { const o = document.createElement("option"); o.value = e.key; o.textContent = e.title; g.appendChild(o); });
      sel.appendChild(g);
    });
    const body = $("gal-body");
    EXAMPLE_CATEGORIES.forEach(cat => {
      const sec = document.createElement("div"); sec.className = "gal-cat";
      const h = document.createElement("h3"); h.textContent = tr(cat); sec.appendChild(h);
      if (cat === COMMUNITY_GROUPS[0]) {
        const note = document.createElement("p"); note.className = "hint";
        note.textContent = tr("Programs other people shared. Each was checked before it was added, and says what it can do, worked out from its blocks. To share one of yours, see gallery/README.md in the Second Thought folder.");
        sec.appendChild(note);
      }
      const grid = document.createElement("div"); grid.className = "gal-grid";
      EXAMPLE_LIST.filter(e => e.cat === cat).forEach(e => {
        const card = document.createElement("div"); card.className = "gal-card"; card.dataset.key = e.key;
        const t = document.createElement("h4"); t.textContent = e.title;
        const d = document.createElement("p"); d.textContent = e.desc;
        const tip = document.createElement("p"); tip.className = "tip"; tip.textContent = tr("Try: {tip}", { tip:e.tip });
        const btn = document.createElement("button"); btn.type = "button"; btn.textContent = e.community ? tr("Load this program") : tr("Load this example");
        btn.onclick = () => { sel.value = e.key; loadExample(e.key); toggleGallery(false); };
        if (e.community) {
          const by = document.createElement("p"); by.className = "by"; by.textContent = tr("Shared by {author}, made with runtime {runtime}.", { author:e.author, runtime:e.runtime });
          const can = document.createElement("p"); can.className = "can"; can.textContent = communityCanText(e);
          card.append(t, by, d, can, tip, btn);
        } else card.append(t, d, tip, btn);
        grid.appendChild(card);
      });
      sec.appendChild(grid); body.appendChild(sec);
    });
  })();
  function describeExample(key){
    const e = exampleByKey(key), el = $("ex-desc");
    el.innerHTML = "";
    if (!e) return;
    const b = document.createElement("b"); b.textContent = e.title + ": ";
    el.append(b, document.createTextNode(e.desc + (e.community ? " " + communityCanText(e) + " " + tr("Shared by {author}.", { author:e.author }) : "") + " " + tr("Try: {tip}", { tip:e.tip })));
  }
  function loadExample(key){ setTests([]); load(exampleState(key)); describeExample(key); try { ws.zoomToFit(); if (ws.getScale() > 0.9) ws.setScale(0.9); } catch(e) {} }
  function toggleGallery(open){
    const g = $("gallery"); if (open === undefined) open = g.hidden;
    g.hidden = !open; $("ex-toggle").setAttribute("aria-expanded", String(open));
    setTimeout(() => Blockly.svgResize(ws), 0);
  }
  $("ex-toggle").onclick = () => toggleGallery();
  $("ha-toggle").onclick = () => toggleHaPanel();
  $("ha-filter").addEventListener("input", renderHaPanel);
  $("example").addEventListener("change", e => describeExample(e.target.value));
  describeExample($("example").value);
  $("load").onclick = () => loadExample($("example").value);
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  const retheme = () => ws.setTheme(makeTheme(isDark()));
  mq.addEventListener && mq.addEventListener("change", retheme);
  new MutationObserver(retheme).observe(document.documentElement, { attributes:true, attributeFilter:["data-theme"] });
  window.addEventListener("resize", () => Blockly.svgResize(ws));

  /* ---------- Building with the keyboard ---------- */
  // Blockly's keyboard navigation (the @blockly/keyboard-navigation plugin), turned on in the keyboard help (?) or with
  // Ctrl+Shift+K, and remembered. A screen reader hears where the cursor goes, through the page's announcer.
  function announce(text){
    const a = $("announce"); a.textContent = "";
    setTimeout(() => { a.textContent = text; }, 30);  // emptied first, so the same words are read again
  }
  const KEYS_KEY = "second-thought-keyboard";
  // Blockly listens for keys on the box it draws in, so that box can take the focus (Tab reaches it), and a screen
  // reader passes keys straight to it (an "application"), named, with where to find the keyboard help.
  const editorEl = ws.getInjectionDiv();
  editorEl.tabIndex = 0; editorEl.setAttribute("role", "application");
  editorEl.setAttribute("aria-label", tr("Block editor")); editorEl.setAttribute("aria-describedby", "keys-where");
  let keyNav = null;
  if (typeof window.NavigationController === "function") {
    // The plugin for Blockly 11 calls the toolbox's moves by their older names (selectNext_); Blockly 11.2 dropped the "_".
    ["selectNext", "selectPrevious", "selectParent", "selectChild"].forEach(n => {
      const proto = Blockly.Toolbox.prototype;
      if (!proto[n + "_"] && proto[n]) proto[n + "_"] = function(){ return this[n](); };
    });
    try { keyNav = new window.NavigationController(); keyNav.init(); keyNav.addWorkspace(ws); } catch(e) { keyNav = null; }
  }
  const keyboardOn = () => !!ws.keyboardAccessibilityMode;
  function setKeyboard(on, quiet){
    if (!keyNav) return;
    if (on !== keyboardOn()) { if (on) keyNav.enable(ws); else keyNav.disable(ws); }
    keyboardChanged(quiet);
  }
  function keyboardChanged(quiet){
    $("keys-on").checked = keyboardOn();
    try { localStorage.setItem(KEYS_KEY, keyboardOn() ? "on" : ""); } catch(e) {}
    if (quiet) return;
    announce(tr(keyboardOn() ? "Building with the keyboard is on. Press T for the blocks." : "Building with the keyboard is off."));
    // Blockly hears keys inside the block editor only, so that's where the keyboard goes next.
    if (keyboardOn() && !editorEl.contains(document.activeElement)) setTimeout(() => editorEl.focus(), 0);
  }
  function describeNode(node){
    if (!node) return "";
    const T = Blockly.ASTNode.types, type = node.getType(), at = node.getLocation();
    const blockText = b => { try { return squash(b.toString()) || b.type; } catch(e) { return b.type; } };
    if (type === T.WORKSPACE) return tr("Empty space");
    if (type === T.STACK) return tr("Script: {block}", { block:blockText(at) });
    if (type === T.BLOCK) return tr("Block: {block}", { block:blockText(at) });
    if (type === T.FIELD) return tr("Field {value}, in: {block}", { value:squash(at.getText ? at.getText() : at.getValue()), block:blockText(at.getSourceBlock()) });
    if (type === T.INPUT) return tr("Slot {name}, in: {block}", { name:at.getParentInput && at.getParentInput() ? at.getParentInput().name : "", block:blockText(at.getSourceBlock()) });
    if (type === T.NEXT) return tr("After: {block}", { block:blockText(at.getSourceBlock()) });
    if (type === T.PREVIOUS || type === T.OUTPUT) return tr("Before: {block}", { block:blockText(at.getSourceBlock()) });
    return "";
  }
  if (keyNav) {
    ws.addChangeListener(e => {
      if (e && e.type === Blockly.Events.MARKER_MOVE && e.isCursor && keyboardOn()) { const t = describeNode(e.newNode); if (t) announce(t); }
    });
    // The flyout's cursor (choosing a block from a category) has its own workspace.
    const flyWs = () => { const f = ws.getToolbox() && ws.getToolbox().getFlyout(); return f && f.getWorkspace(); };
    if (flyWs()) flyWs().addChangeListener(e => {
      if (e && e.type === Blockly.Events.MARKER_MOVE && e.isCursor && keyboardOn() && e.newNode) {
        const at = e.newNode.getLocation(); if (at && at.toString) announce(tr("Block to add: {block}", { block:squash(at.toString()) }));
      }
    });
    ws.addChangeListener(e => {
      if (e && e.type === Blockly.Events.TOOLBOX_ITEM_SELECT && keyboardOn() && e.newItem) announce(tr("Category: {name}", { name:e.newItem }));  // its shown name
    });
    // Ctrl+Shift+K is the plugin's own switch: keep the box and the saved choice in step with it.
    document.addEventListener("keydown", e => { if (e.ctrlKey && e.shiftKey && (e.key === "K" || e.key === "k")) setTimeout(() => keyboardChanged(), 0); });
    let saved = ""; try { saved = localStorage.getItem(KEYS_KEY) || ""; } catch(e) {}
    if (saved === "on") setKeyboard(true, true);
  }
  $("keys-on").disabled = !keyNav;
  $("keys-on").addEventListener("change", e => setKeyboard(e.target.checked));
  $("keys-toggle").onclick = () => {
    const el = $("keys"), open = el.hidden;
    el.hidden = !open; $("keys-toggle").setAttribute("aria-expanded", String(open));
    if (open) $("keys-on").focus();
    setTimeout(() => Blockly.svgResize(ws), 0);
  };
