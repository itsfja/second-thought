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
    if (!sample) { ioMsg("io-import-msg", tr("Converting needs Claude. Open this page in claude.ai while signed in.") + orOwnKey(), "bad"); return; }
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
  /* ---------- What's different between the program on the canvas and Claude's reply (#306) ----------
     Scripts are compared by their blocks' types in order, blocks by type, and text by the words in a block's fields:
     enough to say what to look at, not a full merge view. New and gone connections come first, in bold. */
  function walkBlocks(o, fn){
    if (Array.isArray(o)) { o.forEach(x => walkBlocks(x, fn)); return; }
    if (o && typeof o === "object") {
      if (typeof o.type === "string") fn(o);
      Object.keys(o).forEach(k => { if (k !== "type") walkBlocks(o[k], fn); });
    }
  }
  function scriptKinds(state){
    const chains = [];
    ((state && state.blocks && state.blocks.blocks) || []).forEach(top => {
      const chain = [];
      for (let b = top; b; b = (b.next && b.next.block) || null) chain.push(b.type);
      chains.push(chain.join(" > "));
    });
    return chains;
  }
  function blockKinds(state){
    const types = [];
    walkBlocks(state && state.blocks, b => types.push(b.type));
    return types;
  }
  function blockTexts(state){
    const texts = [];
    walkBlocks(state && state.blocks, b => {
      const f = b.fields || {};
      Object.keys(f).forEach(k => { if (typeof f[k] === "string" || typeof f[k] === "number") texts.push(b.type + " " + f[k]); });
    });
    return texts;
  }
  function multisetDiff(before, after){
    const count = xs => xs.reduce((m, x) => (m[x] = (m[x] || 0) + 1, m), {});
    const b = count(before), a = count(after), out = { added:0, removed:0 };
    Object.keys(a).forEach(k => out.added += Math.max(0, a[k] - (b[k] || 0)));
    Object.keys(b).forEach(k => out.removed += Math.max(0, b[k] - (a[k] || 0)));
    return out;
  }
  function changeParts(before, after){
    const parts = [], has = (caps, id) => caps.some(c => c[0] === id);
    const beforeCaps = stateCapabilities(before), afterCaps = stateCapabilities(after);
    afterCaps.forEach(c => { if (!has(beforeCaps, c[0])) parts.push({ b:tr("New: {what}.", { what:tr(c[1]) }) }); });
    beforeCaps.forEach(c => { if (!has(afterCaps, c[0])) parts.push({ b:tr("Gone: {what}.", { what:tr(c[1]) }) }); });
    const scripts = multisetDiff(scriptKinds(before), scriptKinds(after));
    if (scripts.added || scripts.removed) parts.push(tr("{n} scripts added, {m} removed.", { n:scripts.added, m:scripts.removed }));
    const blocks = multisetDiff(blockKinds(before), blockKinds(after));
    if (blocks.added || blocks.removed) parts.push(tr("{n} blocks added, {m} removed.", { n:blocks.added, m:blocks.removed }));
    const texts = multisetDiff(blockTexts(before), blockTexts(after));
    if (texts.added || texts.removed) parts.push(tr("Text changed in {n} blocks.", { n:texts.added + texts.removed }));
    return parts;
  }
  function describeMsg(text, kind, buttons){
    $("describe-out").hidden = !text;
    const m = $("describe-msg"); m.className = "msg" + (kind ? " " + kind : "");
    m.replaceChildren();
    (Array.isArray(text) ? text : [text]).filter(p => p && (typeof p === "string" || p.b)).forEach((part, i) => {
      if (i) m.appendChild(document.createTextNode(" "));
      const el = document.createElement(typeof part === "string" ? "span" : "strong");
      el.textContent = typeof part === "string" ? part : part.b;
      m.appendChild(el);
    });
    ["load", "discard", "undo"].forEach(b => $("describe-" + b).hidden = !(buttons || []).includes(b));
  }
  function programOnCanvas(){ return ws.getTopBlocks(false).length > 0; }
  async function describeProgram(change){
    const text = $("describe-text").value.trim();
    if (!text) { describeMsg(tr("Describe what the program should do first."), "bad"); $("describe-text").focus(); return; }
    const sample = await getSample();
    if (!sample) { describeMsg(tr("Building a program needs Claude. Open this page in claude.ai while signed in.") + orOwnKey(), "bad"); return; }
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
      const diff = change ? changeParts(saveWs(), state) : [];
      describeMsg([typeof r.summary === "string" && r.summary.trim() ? r.summary.trim() : "",
                   tr("{n} blocks.", { n:countBlocks(state.blocks) }),
                   capabilitySentence(caps) || tr("It only uses your models: it doesn't connect to anything else."),
                   ...diff,
                   notes.length ? tr("Left out: {notes}.", { notes:notes.join("; ") }) : "",
                   tr("Loading it replaces the program on the canvas; you can undo straight after.")
                  ].filter(Boolean), "", ["load", "discard"]);
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
    if (!samplePromise) samplePromise = (window.claude && window.claude.use) ? window.claude.use("sample").catch(() => null)
      : Promise.resolve(ownKey.get() ? ownKeySample(ownKey.get()) : null);
    return samplePromise;
  }

  /* ---------- Your own API key, off claude.ai (#293) ----------
     The copy on GitHub Pages has no Claude of its own, so it can call Claude's API with a key the person gives it. The
     key goes only from this browser to api.anthropic.com (the copy's Content-Security-Policy allows no other
     connection), and calls are charged to that key's account. It's kept for this browser tab unless "Remember on this
     browser" is ticked; it's never put in a saved program, an export, the run log or a test case. */
  const OWN_KEY = "second-thought-anthropic-key";
  const ownKey = {
    get(){ for (const s of ["sessionStorage", "localStorage"]) { try { const k = window[s].getItem(OWN_KEY); if (k) return k; } catch(e) {} } return ""; },
    set(key, remember){
      ownKey.forget();
      try { window[remember ? "localStorage" : "sessionStorage"].setItem(OWN_KEY, key); } catch(e) { return false; }
      return true;
    },
    forget(){ for (const s of ["sessionStorage", "localStorage"]) { try { window[s].removeItem(OWN_KEY); } catch(e) {} } },
    shown(key){ return "…" + String(key).slice(-4); }  // only the last four characters are ever shown
  };
  const API_URL = "https://api.anthropic.com/v1/messages";
  const API_MAX_TOKENS = 16000;
  const JSON_ONLY = "Reply with only the JSON value asked for: no code fences, no other text before or after it.";
  const blobBase64 = blob => new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(String(r.result).split(",")[1]); r.onerror = () => rej(r.error); r.readAsDataURL(blob); });
  // Claude's API's own error, as one of the codes errText knows.
  function apiError(status, body){
    const msg = String((body && body.error && body.error.message) || "");
    if (status === 401) return { code:"bad_key", message:msg };
    if (status === 403) return { code:"key_not_allowed", message:msg };
    if (status === 429) return { code:"rate_limited", message:msg };
    if (/credit balance/i.test(msg)) return { code:"no_credit", message:msg };
    if (/prompt is too long|too many tokens/i.test(msg)) return { code:"prompt_too_large", message:msg };
    if (status === 529 || status >= 500) return { code:"overloaded", message:msg };
    return { code:"api_error", message:msg || ("HTTP " + status) };
  }
  // Reads the API's streamed reply (server-sent events), passing the text so far to onText as it arrives.
  async function readStream(resp, onText){
    const reader = resp.body.getReader(), dec = new TextDecoder();
    let buf = "", text = "", stop = null;
    const handle = ev => {
      if (ev.type === "content_block_delta" && ev.delta && ev.delta.type === "text_delta") {
        text += ev.delta.text; if (onText) onText({ text, delta:ev.delta.text });
      } else if (ev.type === "message_delta" && ev.delta && ev.delta.stop_reason) stop = ev.delta.stop_reason;
      else if (ev.type === "error") throw apiError(ev.error && ev.error.type === "overloaded_error" ? 529 : 500, ev);
    };
    for (;;) {
      const { done, value } = await reader.read();
      buf += dec.decode(value || new Uint8Array(), { stream:!done });
      let i;
      while ((i = buf.indexOf("\n\n")) >= 0) {
        const chunk = buf.slice(0, i); buf = buf.slice(i + 2);
        const data = chunk.split("\n").filter(l => l.startsWith("data:")).map(l => l.slice(5).trim()).join("");
        if (data) handle(JSON.parse(data));
      }
      if (done) break;
    }
    return { text, stop };
  }
  // A stand-in for claude.ai's "sample" (the same calls the page makes there), calling Claude's API with the key.
  function ownKeySample(key){
    const model = tier => { const t = SERVICES[0].tiers; return (t[tier] || t.default)[0]; };
    async function call(input, o, system){
      const turns = (typeof input === "string" ? [{ role:"user", content:input }] : input).map(t => ({ role:t.role, content:t.content }));
      if (o.images && o.images.length) {
        const last = turns[turns.length - 1], parts = [];
        for (const b of o.images) parts.push({ type:"image", source:{ type:"base64", media_type:b.type || "image/png", data:await blobBase64(b) } });
        last.content = parts.concat([{ type:"text", text:String(last.content) }]);
      }
      const body = { model:model(o.modelTier), max_tokens:API_MAX_TOKENS, stream:true, messages:turns };
      if (system) body.system = system;
      let resp;
      try {
        resp = await fetch(API_URL, { method:"POST", signal:o.signal, body:JSON.stringify(body), headers:{
          "content-type":"application/json", "x-api-key":key, "anthropic-version":"2023-06-01",
          "anthropic-dangerous-direct-browser-access":"true" } });
      } catch(e) {
        if (e && e.name === "AbortError") throw { code:"cancelled" };
        throw { code:"network", message:String(e && e.message || e) };
      }
      if (!resp.ok) { let j = null; try { j = await resp.json(); } catch(e) {} throw apiError(resp.status, j); }
      let got;
      try { got = await readStream(resp, o.onText); }
      catch(e) { if (e && e.name === "AbortError") throw { code:"cancelled" }; throw e; }
      if (got.stop === "refusal") throw { code:"refused" };
      if (!got.text.trim() && got.stop !== "max_tokens") throw { code:"empty_completion" };
      return { text:got.text, truncated:got.stop === "max_tokens" };
    }
    const f = (input, o = {}) => call(input, o);
    f.json = async (input, o = {}) => {
      const { text } = await call(input, Object.assign({}, o, { onText:null }), JSON_ONLY);
      const t = text.trim().replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "");
      try { return JSON.parse(t); } catch(e) {}
      const a = t.search(/[[{]/), z = Math.max(t.lastIndexOf("}"), t.lastIndexOf("]"));
      if (a >= 0 && z > a) { try { return JSON.parse(t.slice(a, z + 1)); } catch(e) {} }
      throw { code:"invalid_json", message:"The reply wasn't readable JSON.", text };
    };
    f.limits = async () => ({ maxPromptBytes:262144, images:{ maxCount:20, maxInputBytes:5000000, mediaTypes:["image/jpeg", "image/png", "image/webp", "image/gif"] } });
    f.ownKey = true;
    return f;
  }
  // The offsite banner's key controls: "Use your own API key", and once one is given, which key and "Forget my key".
  // Off claude.ai, a "needs Claude" message says where else Claude can come from.
  const orOwnKey = () => (window.claude && window.claude.use) ? "" : " " + tr("Or use your own API key, from the bar at the top.");
  function showOwnKey(){
    if (window.claude && window.claude.use) return;
    const key = ownKey.get();
    $("offsite-text").textContent = key
      ? tr("Programs run with your own API key ({key}), charged to its Anthropic account.", { key:ownKey.shown(key) })
      : tr("This copy of Second Thought can build programs, try them on sample data, explain them and export them, but it can't run them with Claude. For that, open it in claude.ai:");
    $("offsite-link").hidden = !!key;
    $("own-key").hidden = !!key || !$("own-key-panel").hidden;
    $("own-key-forget").hidden = !key;
  }
  if (!(window.claude && window.claude.use)) {
    $("own-key").textContent = tr("Use your own API key");
    $("own-key-forget").textContent = tr("Forget my key");
    $("own-key-label").textContent = tr("Your Anthropic API key");
    $("own-key-remember-text").textContent = tr("Remember on this browser");
    $("own-key-use").textContent = tr("Use this key");
    $("own-key-cancel").textContent = tr("Cancel");
    $("own-key-note").textContent = tr("The key goes only from this browser to api.anthropic.com, and runs are charged to its account. It's kept until you close this tab, unless you tick Remember. It's never saved in programs, exports or the run log. Make one at console.anthropic.com.");
    const close = () => { $("own-key-panel").hidden = true; $("own-key-input").value = ""; $("own-key-msg").textContent = ""; showOwnKey(); };
    $("own-key").onclick = () => { $("own-key-panel").hidden = false; showOwnKey(); $("own-key-input").focus(); };
    $("own-key-cancel").onclick = close;
    $("own-key-use").onclick = () => {
      const key = $("own-key-input").value.trim();
      if (!/^sk-ant-[\w-]{20,}$/.test(key)) { $("own-key-msg").textContent = tr("That doesn't look like an Anthropic API key. They start with sk-ant-."); return; }
      if (!ownKey.set(key, $("own-key-remember").checked)) { $("own-key-msg").textContent = tr("This browser won't keep the key. Allow site data for this page, then try again."); return; }
      samplePromise = null; showBanner(""); close();
    };
    $("own-key-input").onkeydown = e => { if (e.key === "Enter") $("own-key-use").click(); };
    $("own-key-forget").onclick = () => { ownKey.forget(); samplePromise = null; showOwnKey(); };
    showOwnKey();
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
    prompt_too_large:"The text is too long for one step. Shorten it.",
    // Your own API key (#293)
    bad_key:"Claude's API refused your API key. Check it, or forget it and enter it again.",
    key_not_allowed:"Your API key isn't allowed to do that. Check its permissions in the Claude Console.",
    no_credit:"Your Anthropic account has no credit left for this key. Add some in the Claude Console, then run again.",
    overloaded:"Claude's API is busy right now. Wait a moment and run again.",
    network:"api.anthropic.com couldn't be reached. Check your connection and run again."
  };
  const errText = e => (e instanceof Error) ? ("The page hit an error: " + e.message)
    : (e && (e.code === "user" || e.code === "retryable" || e.shape)) ? e.message
    : (e && e.code === "api_error") ? tr("Claude's API said: {problem}", { problem:e.message })
    : ERR[e && e.code] || ("Something went wrong talking to Claude" + (e && e.code ? " (" + e.code + ")" : "") + ". Run again.");

