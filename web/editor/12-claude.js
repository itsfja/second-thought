  // 12-claude.js: Asking Claude to convert code or build a program from a description, and Claude access.
  /* ---------- Claude conversion of other code ---------- */
  function exampleForPrompt(key){
    const ex = EXAMPLES[key]();
    const names = {}; (ex.variables || []).forEach(v => names[v.id] = v.name);
    const walk = o => {
      if (Array.isArray(o)) return o.map(walk);
      if (o && typeof o === "object") { const r = {}; Object.keys(o).forEach(k => { r[k] = (k === "VAR" && o[k] && o[k].id) ? { name:names[o[k].id] || o[k].id } : walk(o[k]); }); return r; }
      return o;
    };
    return JSON.stringify({ blocks:walk(ex.blocks) });
  }
  function normaliseConverted(state){
    if (!state || typeof state !== "object") return null;
    if (Array.isArray(state.blocks)) state = { variables:state.variables, blocks:{ languageVersion:0, blocks:state.blocks } };
    if (!state.blocks || !Array.isArray(state.blocks.blocks)) return null;
    state.blocks.languageVersion = 0;
    if (state.variables && !Array.isArray(state.variables)) delete state.variables;
    if (Array.isArray(state.variables)) state.variables = state.variables.filter(v => v && v.id && v.name);
    let x = 30;
    state.blocks.blocks.forEach(b => { if (typeof b.x !== "number") { b.x = x; b.y = 30; x += 480; } });
    return state;
  }
  async function convertWithClaude(code, label){
    const sample = await getSample();
    if (!sample) { ioMsg("io-import-msg", "Converting needs Claude. Open this page in claude.ai while signed in.", "bad"); return; }
    clearChoice();
    ioMsg("io-import-msg", "Converting with Claude. This can take a minute or two…");
    $("io-load-paste").disabled = true;
    const prompt = document.getElementById("convert-guide").textContent +
      "\n\nEXAMPLE 1 (review loop):\n" + exampleForPrompt("review") +
      "\n\nEXAMPLE 2 (variables, loops, if):\n" + exampleForPrompt("brainstorm") +
      "\n\nEXAMPLE 3 (broadcast and receivers):\n" + exampleForPrompt("parallel") +
      "\n\nCODE TO CONVERT:\n```\n" + String(code).slice(0, 60000) + "\n```\n\n" +
      'Reply with only JSON: {"program": {"blocks": {"languageVersion": 0, "blocks": [ ...top-level scripts... ]}}, "unmapped": ["one short note per thing you could not convert"]}';
    try {
      const r = await sample.json(prompt, { modelTier:"complex", cache:false });
      const state = normaliseConverted(r && r.program);
      if (!state) { ioMsg("io-import-msg", "Claude's conversion didn't come back as a block program. Try again, or simplify the code.", "bad"); return; }
      const notes = Array.isArray(r.unmapped) ? r.unmapped.map(String).filter(Boolean) : [];
      if (applyProgram(state, label || "converted code", true)) {
        if (notes.length) ioMsg("io-import-msg", $("io-import-msg").textContent + " " + tr("Not converted: {notes}.", { notes:notes.join("; ") }), "ok");
        else ioMsg("io-import-msg", $("io-import-msg").textContent + " " + tr("Claude converted everything. Check the blocks before running."), "ok");
      }
    } catch(e) {
      ioMsg("io-import-msg", tr("Conversion failed: {problem}", { problem:errText(e) }), "bad");
    } finally { $("io-load-paste").disabled = false; }
  }
  /* ---------- Describe a program: Claude builds the blocks, you check them before they load ---------- */
  const DESCRIBE_INTRO = "You build block programs for \"Second Thought\", a Scratch-style editor for AI workflows, from a plain-English " +
    "description. Output the program as Blockly JSON (described below). Use the fewest blocks that do what was asked, and prefer the AI " +
    "blocks for anything a language model does. Use the connector blocks (Telegram, email, GitHub, calendar, feeds, Home Assistant and so " +
    "on) for the services the description names. Times become rb_when_time or rb_every hats, with a 'when Run is clicked' script that does " +
    "the same job so it can be tried straight away. Put text the person would want to change (a town, an address, a project) in a variable " +
    "set at the top of the script. If something asked for can't be done with these blocks, leave it out and say so in \"unmapped\". Ignore " +
    "the HOW TO MAP CODE section below: it's for converting code.";
  let described = null;  // { state, change }: Claude's program, waiting to be loaded
  // The program on the canvas for a prompt: variables by name, without ids or positions, which Claude doesn't need.
  function programForPrompt(state){
    const names = {}; (state.variables || []).forEach(v => names[v.id] = v.name);
    const walk = o => {
      if (Array.isArray(o)) return o.map(walk);
      if (o && typeof o === "object") {
        const r = {};
        Object.keys(o).forEach(k => {
          if (k === "id" || k === "x" || k === "y") return;
          r[k] = (k === "VAR" && o[k] && o[k].id) ? { name:names[o[k].id] || o[k].id } : walk(o[k]);
        });
        return r;
      }
      return o;
    };
    return JSON.stringify({ blocks:walk(state.blocks || { languageVersion:0, blocks:[] }) });
  }
  const countBlocks = o => !o || typeof o !== "object" ? 0 : Array.isArray(o) ? o.reduce((n, x) => n + countBlocks(x), 0)
    : (typeof o.type === "string" ? 1 : 0) + Object.keys(o).reduce((n, k) => n + (k === "type" ? 0 : countBlocks(o[k])), 0);
  function describeMsg(text, kind, buttons){
    $("describe-out").hidden = !text;
    const m = $("describe-msg"); m.textContent = text || ""; m.className = "msg" + (kind ? " " + kind : "");
    ["load", "discard", "undo"].forEach(b => $("describe-" + b).hidden = !(buttons || []).includes(b));
  }
  function programOnCanvas(){ return ws.getTopBlocks(false).length > 0; }
  async function describeProgram(change){
    const text = $("describe-text").value.trim();
    if (!text) { describeMsg(tr("Describe what the program should do first."), "bad"); $("describe-text").focus(); return; }
    const sample = await getSample();
    if (!sample) { describeMsg(tr("Building a program needs Claude. Open this page in claude.ai while signed in."), "bad"); return; }
    described = null;
    $("describe-build").disabled = $("describe-change").disabled = true;
    describeMsg(tr("Claude is working on the program. This can take a minute…"));
    const guide = document.getElementById("convert-guide").textContent;
    const prompt = DESCRIBE_INTRO + "\n\n" + guide.slice(guide.indexOf("FORMAT")) +
      "\n\nEXAMPLE 1 (review loop):\n" + exampleForPrompt("review") +
      "\n\nEXAMPLE 2 (broadcast and receivers):\n" + exampleForPrompt("parallel") +
      (change ? "\n\nTHE PROGRAM NOW:\n" + programForPrompt(saveWs()) + "\n\nCHANGE IT LIKE THIS (keep everything else as it is):\n" : "\n\nDESCRIPTION:\n") +
      text.slice(0, 4000) + "\n\n" +
      'Reply with only JSON: {"program": {"blocks": {"languageVersion": 0, "blocks": [ ...top-level scripts... ]}}, ' +
      '"summary": "one plain sentence on what the program does", "unmapped": ["one short note per thing asked for that you left out"]}';
    try {
      const r = await sample.json(prompt, { modelTier:"complex", cache:false });
      const state = normaliseConverted(r && r.program);
      if (!state) { describeMsg(tr("Claude's reply wasn't a block program. Try again, or describe it more simply."), "bad"); return; }
      const bad = unknownTypes(state);
      if (bad.length) { describeMsg(tr("Claude used blocks this page doesn't have ({blocks}), so nothing was loaded. Try again, or describe it differently.", { blocks:bad.join(", ") }), "bad"); return; }
      let caps;
      try { caps = stateCapabilities(state); }
      catch(e) { describeMsg(tr("Claude's reply wasn't a block program. Try again, or describe it more simply."), "bad"); return; }
      const notes = Array.isArray(r.unmapped) ? r.unmapped.map(String).filter(Boolean) : [];
      described = { state, change };
      describeMsg([typeof r.summary === "string" && r.summary.trim() ? r.summary.trim() : "",
                   tr("{n} blocks.", { n:countBlocks(state.blocks) }),
                   capabilitySentence(caps) || tr("It only uses your models: it doesn't connect to anything else."),
                   notes.length ? tr("Left out: {notes}.", { notes:notes.join("; ") }) : "",
                   tr("Loading it replaces the program on the canvas; you can undo straight after.")
                  ].filter(Boolean).join(" "), "", ["load", "discard"]);
    } catch(e) {
      describeMsg(tr("Building the program failed: {problem}", { problem:errText(e) }), "bad");
    } finally {
      $("describe-build").disabled = false; $("describe-change").disabled = !programOnCanvas();
    }
  }
  $("describe-text").placeholder = tr("Describe a program, like: every Friday at 6pm, find the best two hours this weekend to dry washing and send it to me on Telegram");
  $("describe-build").onclick = () => describeProgram(false);
  $("describe-change").onclick = () => describeProgram(true);
  $("describe-text").addEventListener("keydown", e => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); describeProgram(false); } });
  $("describe-discard").onclick = () => { described = null; describeMsg(""); };
  $("describe-load").onclick = () => {
    if (!described) return;
    const name = described.change ? $("io-name").value.trim() : "";
    const ok = applyProgram(described.state, name, described.change ? "change" : true);
    described = null;
    if (ok) describeMsg(tr("Loaded Claude's program ({n} blocks). Check the blocks before running.", { n:ws.getAllBlocks(false).length }), "ok", ["undo"]);
    else describeMsg($("io-import-msg").textContent, "bad");
  };
  $("describe-undo").onclick = () => {
    if (!beforeImport) return;
    load(beforeImport); beforeImport = null; $("io-undo").hidden = true; setTests(beforeImportTests);
    describeMsg(tr("Undone. Your previous program is back."), "ok");
  };
  ws.addChangeListener(e => { if (!e.isUiEvent && !$("describe-build").disabled) $("describe-change").disabled = !programOnCanvas(); });
  function clearChoice(){ const c = $("io-choice"); c.innerHTML = ""; c.hidden = true; }
  function offerChoice(message, choices){
    ioMsg("io-import-msg", message);
    const c = $("io-choice"); c.innerHTML = "";
    choices.forEach((ch, i) => {
      const btn = document.createElement("button"); btn.type = "button"; btn.textContent = tr(ch.label);
      if (i === 0) btn.className = "primary";
      btn.onclick = () => { clearChoice(); ch.run(); };
      c.appendChild(btn);
    });
    c.hidden = false;
  }
  // After an exported program loads: if it was made with another runtime, say so, and how to upgrade.
  function noteRuntime(theirs){
    if (!RUNTIME_VERSION || theirs === RUNTIME_VERSION) return;
    const m = $("io-import-msg");
    m.textContent += " " + tr(theirs ? "Its Python was exported with runtime {theirs}; this page has runtime {ours}. Export it again to give the Python program the new runtime (CHANGELOG.md says what changed)."
      : "Its Python was exported with a runtime from before versions were numbered; this page has runtime {ours}. Export it again to give the Python program the new runtime (CHANGELOG.md says what changed).", { theirs, ours:RUNTIME_VERSION });
  }
  function importCode(code, label){
    const ex = readExported(code);
    if (ex) {
      const name = ex.data.name || label;
      if (!ex.edited) { if (applyProgram(ex.data.program, name, false, ex.data.version, ex.data.tests || [])) { $("io-name").value = slug(name); noteRuntime(ex.runtime); } return; }
      offerChoice("This code was exported from here and then edited. The blocks saved inside it are from before the edits.", [
        { label:tr("Convert the edited code with Claude"), run:() => convertWithClaude(code, name) },
        { label:tr("Restore the exported blocks"), run:() => { if (applyProgram(ex.data.program, name, false, ex.data.version, ex.data.tests || [])) $("io-name").value = slug(name); } }
      ]);
      return;
    }
    offerChoice("This code wasn't exported from this page. Claude can try to turn it into blocks. That uses your Claude usage, and you can undo it afterwards.", [
      { label:tr("Convert with Claude"), run:() => convertWithClaude(code, label) }
    ]);
  }

  /* ---------- Claude access ---------- */
  let samplePromise = null;
  function getSample(){
    if (!samplePromise) samplePromise = (window.claude && window.claude.use) ? window.claude.use("sample").catch(() => null) : Promise.resolve(null);
    return samplePromise;
  }
  getSample();
  function showBanner(msg){ const b = $("banner"); b.textContent = tr(msg); b.hidden = !msg; }
  const ERR = {
    not_granted:"Claude access was declined for this page. Allow it from the artifact's Permissions menu, then reload.",
    sampling_disabled:"Claude isn't available on this account.",
    rate_limited:"Too many requests right now. Wait a minute and run again.",
    session_expired:"Your session expired. Sign in again, then run.",
    refused:"Claude declined this step. Change the wording and try again.",
    empty_completion:"Claude returned nothing for this step. Simplify it and try again.",
    invalid_json:"Claude's reply came back in an unreadable format. Run again.",
    prompt_too_large:"The text is too long for one step. Shorten it."
  };
  const errText = e => (e instanceof Error) ? ("The page hit an error: " + e.message)
    : (e && (e.code === "user" || e.code === "retryable" || e.shape)) ? e.message
    : ERR[e && e.code] || ("Something went wrong talking to Claude" + (e && e.code ? " (" + e.code + ")" : "") + ". Run again.");

