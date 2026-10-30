  // 16-pictures-files.js: Pictures, files and error messages.
  /* ---------- Pictures ---------- */
  const IMG_TYPES = ["image/jpeg","image/png","image/webp","image/gif"];
  function isRec(v){ return !!(v && typeof v === "object" && !Array.isArray(v) && v.kind !== "image" && !(v instanceof Blob)); }
  const fieldList = f => str(f).split(/[,\n]+/).map(x => x.trim()).filter(Boolean);
  function toRecord(o, fields){
    const r = {};
    if (o && typeof o === "object" && !Array.isArray(o)) Object.keys(o).forEach(k => { const v = o[k]; r[k] = (v && typeof v === "object" && !Array.isArray(v)) ? JSON.stringify(v) : v; });
    (fields || []).forEach(f => { if (!(f in r)) r[f] = ""; });
    return r;
  }
  function isImg(v){ return !!(v && typeof v === "object" && v.kind === "image"); }
  let picCount = 0;
  function blobToDataURL(blob){ return new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(String(r.result)); r.onerror = () => rej(new Error("The picture couldn't be read.")); r.readAsDataURL(blob); }); }
  async function makeImage(blob, name, svg){ return { kind:"image", name:name || ("picture-" + (++picCount)), type:blob.type, blob, svg:svg || null, url:await blobToDataURL(blob) }; }
  function cleanSvg(text){
    const m = String(text).match(/<svg[\s\S]*<\/svg>/i);
    if (!m) return null;
    const doc = new DOMParser().parseFromString(m[0], "image/svg+xml");
    const root = doc.documentElement;
    if (doc.querySelector("parsererror") || !root || root.nodeName.toLowerCase() !== "svg") return null;
    root.querySelectorAll("script, foreignObject, iframe").forEach(n => n.remove());
    root.querySelectorAll("*").forEach(n => [...n.attributes].forEach(a => {
      const nm = a.name.toLowerCase();
      if (nm.startsWith("on") || ((nm === "href" || nm === "xlink:href") && !/^(#|data:image\/)/i.test(a.value.trim()))) n.removeAttribute(a.name);
    }));
    [...root.attributes].forEach(a => { if (a.name.toLowerCase().startsWith("on")) root.removeAttribute(a.name); });
    root.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    let vb = (root.getAttribute("viewBox") || "").trim().split(/[\s,]+/).map(Number);
    const w0 = parseFloat(root.getAttribute("width")), h0 = parseFloat(root.getAttribute("height"));
    if (vb.length !== 4 || vb.some(isNaN)) { vb = [0, 0, w0 || 800, h0 || 600]; root.setAttribute("viewBox", vb.join(" ")); }
    const scale = 1024 / Math.max(vb[2], vb[3]);
    root.setAttribute("width", String(Math.round(vb[2] * scale)));
    root.setAttribute("height", String(Math.round(vb[3] * scale)));
    return new XMLSerializer().serializeToString(root);
  }
  async function svgImage(svg, name){ return makeImage(new Blob([svg], { type:"image/svg+xml" }), name, svg); }
  async function toPng(img, maxSide){
    const el = new Image(); el.src = img.url;
    await el.decode();
    let w = el.naturalWidth || 1024, h = el.naturalHeight || 768;
    const scale = Math.min(img.svg ? 4 : 1, maxSide / Math.max(w, h));
    const c = document.createElement("canvas");
    c.width = Math.max(1, Math.round(w * scale)); c.height = Math.max(1, Math.round(h * scale));
    const g = c.getContext("2d");
    if (img.svg) { g.fillStyle = "#ffffff"; g.fillRect(0, 0, c.width, c.height); }
    g.drawImage(el, 0, 0, c.width, c.height);
    const blob = await new Promise(r => c.toBlob(r, "image/png"));
    if (!blob) throw new Error("The picture couldn't be converted to PNG.");
    return blob;
  }
  function needImg(v, where){ if (!isImg(v)) fail(tr("The '{where}' block needs a picture in its picture slot.", { where })); return v; }
  /* Sends a prompt with a picture attached. Drawn pictures fall back to their SVG source when this view can't send images. */
  async function askWithPicture(prompt, img, step, mode){
    const caps = await run.sample.limits().catch(() => null);
    if (caps && caps.images) {
      let blob = img.blob;
      if (img.svg || !caps.images.mediaTypes.includes(blob.type) || blob.size > caps.images.maxInputBytes) blob = await toPng(img, 1536);
      return ask(prompt, step, mode, [blob]);
    }
    if (img.svg) return ask(prompt + "\n\nThe picture is this SVG drawing:\n" + img.svg, step, mode);
    fail(tr("This view can't send pictures to Claude, so blocks that look at photos can't run here."));
  }
  const DRAW_RULES = "Reply with only the SVG code, starting with <svg and ending with </svg>. Use a viewBox, flat shapes and solid fills. " +
    "No scripts, no external images or fonts, no animation. Only add text if the description asks for it.";
  async function drawSvg(prompt, label, img){
    const s = addStep(label, { text:tr("Drawing…") });
    const out = img ? await askWithPicture(prompt, img, null) : await ask(prompt, null);
    const svg = cleanSvg(out);
    if (!svg) { s.text(tr("Claude's reply wasn't a usable drawing.")); s.done("failed", "bad"); throw { code:"retryable", message:"Claude's drawing came back in a form that can't be shown. Run again, or simplify the description." }; }
    const pic = await svgImage(svg);
    showPictureIn(s, pic); s.done("drawn", "ok");
    return pic;
  }
  function showPictureIn(step, pic, caption){
    step.body.innerHTML = "";
    const im = document.createElement("img"); im.src = pic.url; im.alt = caption || pic.name; im.className = "pic";
    step.body.appendChild(im);
    if (caption) { const c = document.createElement("div"); c.className = "pic-cap"; c.textContent = caption; step.body.appendChild(c); }
  }
  async function savePicture(pic, fmt){
    if (!downloads) fail(tr("Saving files isn't available in this view."));
    let blob, ext;
    if (fmt === "svg") { if (!pic.svg) fail(tr("Only drawn pictures can be saved as SVG. Choose PNG instead.")); blob = new Blob([pic.svg], { type:"image/svg+xml" }); ext = "svg"; }
    else if (fmt === "orig") { blob = pic.blob; ext = { "image/jpeg":"jpg", "image/png":"png", "image/webp":"webp", "image/gif":"gif", "image/svg+xml":"svg" }[pic.type] || "png"; }
    else { blob = pic.type === "image/png" ? pic.blob : await toPng(pic, 2048); ext = "png"; }
    const filename = slug(pic.name) + "." + ext;
    try { await downloads.save({ filename, data:blob }); return "Saved " + filename + "."; }
    catch(e) { if (e && e.code === "declined") return "Save cancelled."; if (e && e.code === "rate_limited") return "Another save prompt was open, so this one was skipped."; fail(tr("The picture couldn't be saved here.")); }
  }
  function choosePicture(){
    return waitForYou("Choose a picture", tr("Pick a JPEG, PNG, WebP, GIF or SVG file."), (box, done, step) => {
      const id = "pick-" + (++picCount);
      const input = document.createElement("input"); input.type = "file"; input.id = id; input.accept = "image/jpeg,image/png,image/webp,image/gif,image/svg+xml,.svg";
      input.className = "pickfile";
      const label = document.createElement("label"); label.htmlFor = id; label.className = "filebtn"; label.textContent = tr("Choose picture");
      const preview = document.createElement("img"); preview.className = "pic"; preview.hidden = true; preview.alt = "Chosen picture";
      const err = document.createElement("div"); err.className = "err"; err.hidden = true;
      const row = document.createElement("div"); row.className = "row";
      const use = document.createElement("button"); use.type = "button"; use.className = "primary"; use.textContent = tr("Use this picture"); use.disabled = true;
      let chosen = null;
      input.onchange = async () => {
        err.hidden = true; chosen = null; use.disabled = true;
        const f = input.files && input.files[0]; if (!f) return;
        try {
          if (f.size > 20 * 1024 * 1024) throw new Error("That picture is over 20 MB. Choose a smaller one.");
          const name = f.name.replace(/\.[a-z0-9]+$/i, "");
          if (f.type === "image/svg+xml" || /\.svg$/i.test(f.name)) {
            const svg = cleanSvg(await f.text()); if (!svg) throw new Error("That SVG file couldn't be read.");
            chosen = await svgImage(svg, name);
          } else if (IMG_TYPES.includes(f.type)) chosen = await makeImage(f, name);
          else throw new Error("That file isn't a JPEG, PNG, WebP, GIF or SVG picture.");
          preview.src = chosen.url; preview.hidden = false; use.disabled = false;
        } catch(e) { err.textContent = e.message; err.hidden = false; }
      };
      use.onclick = () => { if (!chosen) { err.textContent = tr("Choose a picture first."); err.hidden = false; return; } const pic = chosen; done(pic, "chosen"); showPictureIn(step, pic, pic.name); };
      row.append(input, label, use);
      box.append(row, preview, err);
    });
  }

  /* ---------- Files ---------- */
  const TEXT_EXT = /\.(txt|md|markdown|csv|tsv|json|html?|xml|ya?ml|log|py|js|ts|css|ini|cfg|toml|rtf|srt|vtt)$/i;
  function chooseTextFile(why){
    return waitForYou("Choose a file", (why ? why + "\n\n" : "") + tr("Pick a PDF, a Word file (.docx), or a text file such as .txt, .md, .csv or .json."), (box, done, step) => {
      const id = "pickf-" + (++picCount);
      const input = document.createElement("input"); input.type = "file"; input.id = id; input.className = "pickfile";
      input.accept = ".txt,.md,.markdown,.csv,.tsv,.json,.html,.htm,.xml,.yaml,.yml,.log,.py,.js,.css,.toml,.srt,.vtt,.pdf,.docx,text/*,application/pdf";
      const label = document.createElement("label"); label.htmlFor = id; label.className = "filebtn"; label.textContent = tr("Choose file");
      const err = document.createElement("div"); err.className = "err"; err.hidden = true;
      const info = document.createElement("div"); info.className = "pic-cap"; info.hidden = true;
      const row = document.createElement("div"); row.className = "row";
      const use = document.createElement("button"); use.type = "button"; use.className = "primary"; use.textContent = tr("Use this file"); use.disabled = true;
      let chosen = null;
      input.onchange = async () => {
        err.hidden = true; info.hidden = true; chosen = null; use.disabled = true;
        const f = input.files && input.files[0]; if (!f) return;
        try {
          if (f.size > 25 * 1024 * 1024) throw new Error("That file is over 25 MB. Choose a smaller one, or split it.");
          if (/\.(doc|xlsx?|pptx?|zip|png|jpe?g|gif|webp)$/i.test(f.name)) throw new Error("That file type can't be read here. Use a PDF, a .docx, or a text file (pictures go in the Pictures blocks).");
          info.textContent = tr("Reading {file}…", { file:f.name }); info.hidden = false;
          let text;
          if (/\.pdf$/i.test(f.name) || f.type === "application/pdf") text = await pdfText(await f.arrayBuffer());
          else if (/\.docx$/i.test(f.name)) text = await docxText(await f.arrayBuffer());
          else { if (f.size > 2 * 1024 * 1024) throw new Error("That text file is over 2 MB. Choose a smaller one, or split it."); text = await f.text(); }
          if (!text.trim()) throw new Error("No text could be found in that file. A scanned PDF holds pictures of pages, not text.");
          if (/\u0000/.test(text.slice(0, 4000))) throw new Error("That file isn't text. Save it as .txt or .md first.");
          chosen = { name:f.name, text };
          info.textContent = f.name + " \u00b7 " + tr("{n} characters", { n:text.length.toLocaleString() }); info.hidden = false; use.disabled = false;
        } catch(e) { err.textContent = e.message; err.hidden = false; }
      };
      use.onclick = () => {
        if (!chosen) { err.textContent = tr("Choose a file first."); err.hidden = false; return; }
        const c = chosen; done(c, "chosen");
        step.text((why ? why + "\n\n" : "") + c.name + " \u00b7 " + tr("{n} characters", { n:c.text.length.toLocaleString() }) + "\n\n" + c.text.slice(0, 600) + (c.text.length > 600 ? "\n…" : ""));
      };
      row.append(input, label, use);
      box.append(row, info, err);
    });
  }
  let pdfLoading = null;
  function loadScript(src){ return new Promise((res, rej) => { const el = document.createElement("script"); el.src = src; el.onload = res; el.onerror = () => rej(new Error("The PDF reader couldn't load. Check your connection and try again.")); document.head.appendChild(el); }); }
  async function pdfText(buf){
    if (!pdfLoading) pdfLoading = (async () => {
      const base = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/";
      await loadScript(base + "pdf.min.js");
      await loadScript(base + "pdf.worker.min.js");
      window.pdfjsLib.GlobalWorkerOptions.workerSrc = base + "pdf.worker.min.js";
    })();
    try { await pdfLoading; } catch(e) { pdfLoading = null; throw e; }
    const doc = await window.pdfjsLib.getDocument({ data:new Uint8Array(buf), isEvalSupported:false }).promise;
    const pages = [];
    for (let i = 1; i <= Math.min(doc.numPages, 300); i++) {
      const c = await (await doc.getPage(i)).getTextContent();
      let line = "", out = [];
      c.items.forEach(it => { line += it.str; if (it.hasEOL) { out.push(line); line = ""; } });
      if (line) out.push(line);
      pages.push(out.join("\n"));
    }
    return pages.join("\n\n").replace(/[ \t]+\n/g, "\n").slice(0, 400000);
  }
  async function docxText(buf){
    const xml = await readZipEntry(buf, n => n === "word/document.xml");
    if (!xml) throw new Error("That .docx file has no document text inside.");
    return xml.replace(/<w:tab\/>/g, "\t").replace(/<w:br[^>]*\/>/g, "\n").replace(/<\/w:p>/g, "\n").replace(/<[^>]+>/g, "")
      .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&amp;/g, "&").replace(/\n{3,}/g, "\n\n").trim();
  }
  async function saveTextFile(value, name, ext){
    if (isImg(value)) fail(tr("To save a picture, use the 'save picture' block."));
    if (!downloads) fail(tr("Saving files isn't available in this view."));
    let text;
    if (ext === "json") text = typeof value === "string" ? value : JSON.stringify(value, (k, v) => isImg(v) ? str(v) : v, 2);
    else if (ext === "csv" && Array.isArray(value)) text = value.map(r => Array.isArray(r) ? r.map(c => '"' + str(c).replace(/"/g, '""') + '"').join(",") : str(r)).join("\n");
    else text = str(value);
    if (!text) fail(tr("There's nothing to save: the value in the 'save as file' block is empty."));
    const filename = slug(name || "output") + "." + ext;
    try { await downloads.save({ filename, data:text }); return "Saved " + filename + "."; }
    catch(e) {
      if (e && e.code === "declined") return "Save cancelled.";
      if (e && e.code === "rate_limited") return "Another save prompt was open, so this one was skipped.";
      fail(tr("The file couldn't be saved here."));
    }
  }
  /* ---------- Errors ---------- */
  const isControlSignal = e => e instanceof Halt || e instanceof FinishSig || e instanceof BreakSig || e instanceof ContinueSig || e instanceof ReturnSig;
  const RETRYABLE = new Set(["upstream_error", "invalid_json", "empty_completion", "retryable"]);
  function markFailedSince(index){
    [...stepsEl.children].slice(index).forEach(el => { const p = el.querySelector(".pill"); if (p && ["running","waiting","waiting for you"].includes(p.dataset.state)) { p.dataset.state = "failed"; p.textContent = tr("failed"); p.className = "pill bad"; const bd = el.querySelector(".step-body"); if (bd && bd.textContent === "Thinking…") bd.textContent = tr("No answer."); } });
  }

  class Halt {}
  class BreakSig {} class ContinueSig {}
  class ReturnSig { constructor(v){ this.value = v; } }
  class FinishSig {}

  let run = null;               // current run state
  const fail = message => { throw { code:"user", message }; };

  const isNumLike = v => typeof v === "number" || (typeof v === "string" && v.trim() !== "" && !isNaN(Number(v)));
  const num = v => { if (typeof v === "boolean") return v ? 1 : 0; const n = Number(v); return isNaN(n) ? 0 : n; };
  const str = v => v == null ? "" : Array.isArray(v) ? v.map(str).join("\n") : isImg(v) ? "[picture: " + v.name + "]"
    : isRec(v) ? Object.keys(v).map(k => k + ": " + (Array.isArray(v[k]) ? v[k].map(str).join(", ") : str(v[k]))).join("\n") : String(v);
  const bool = v => typeof v === "string" ? !(v === "" || v.toLowerCase() === "false" || v === "0") : !!v;
  const list = v => Array.isArray(v) ? v : (v == null || v === "") ? [] : String(v).split(/\n+/).map(s => s.replace(/^\s*(?:[-*](?=\s)|•|\(?\d+[.)](?!\d))\s*/, "").trim()).filter(Boolean);  // as _BULLET in core.py
  window.__list = v => list(v);
  const short = (s, n) => { s = str(s).replace(/\s+/g, " ").trim(); return s.length > n ? s.slice(0, n - 1) + "…" : s; };

  const halting = () => run.stopped || run.ending;
  function endAll(){
    run.ctls.forEach(c => { try { c.abort(); } catch(e) {} });
    [...run.stoppers].forEach(f => f());
  }
  async function tick(){
    if (halting()) throw new Halt();
    if (++run.steps > MAX_STEPS) fail(tr("Stopped after {n} steps. A loop may never end; check repeat and while blocks.", { n:MAX_STEPS }));
    if (run.steps % 200 === 0) await new Promise(r => setTimeout(r, 0));
  }
  function mark(block){ try { ws.highlightBlock(block.id); } catch(e) {} }

  function withInstructions(input){
    const turns = typeof input === "string" ? [{ role:"user", content:input }] : input;
    if (!run.instructions) return typeof input === "string" ? input : turns;
    return [{ role:"user", content:"Standing instructions for every reply (follow them unless the request below says otherwise):\n" + run.instructions }].concat(turns);
  }
  async function ask(prompt, step, mode, images){
    prompt = withInstructions(prompt);
    if (halting()) throw new Halt();
    if (++run.calls > MAX_AI_CALLS) fail(tr("Stopped after {n} Claude calls in one run, to protect your usage. Check for loops that call Claude too often.", { n:MAX_AI_CALLS }));
    if (run.budget && tokensUsed() >= run.budget) fail(tr("Stopped: this run has used about {used} tokens, which reaches its budget of {budget}. Raise the number in the 'limit this run' block.", { used:tokensUsed().toLocaleString(), budget:run.budget.toLocaleString() }));
    run.tokIn += estTokens(prompt) + (images ? images.length * 1600 : 0);
    setStatus(tr("running") + " · " + tr(run.calls === 1 ? "{n} Claude call" : "{n} Claude calls", { n:run.calls }) + " · " + tr("~{n} tokens", { n:fmtTokens(tokensUsed()) }));
    const sample = run.sample;
    // Backups stand in for the primary model only; a block that names its own model keeps it.
    const tiers = [run.tier].concat(run.tier === run.primary ? run.backups : []);
    let last = null;
    for (let n = 0; n < tiers.length; n++) {
      if (n) addStep("Backup", { mono:true, text:tr("{model} failed: {problem}\nTrying {next} instead.", { model:tierLabel(tiers[n - 1]), problem:String((last && last.message) || last).slice(0, 160), next:tierLabel(tiers[n]) }) }).done("backup", "warn");
      const t0 = performance.now(), tin = estTokens(prompt) + (images ? images.length * 1600 : 0);
      const note = (ok, out) => { addCost(tiers[n], tin, ok ? estTokens(out) : 0); if (step && step.call) step.call({ who:tierLabel(tiers[n]), ms:performance.now() - t0, tin, tout:ok ? estTokens(out) : 0, ok, prompt:promptText(prompt, images) }); };
      try {
        const got = await askOn(tiers[n], prompt, step, mode, images, sample);
        const out = mode === "json" ? got : got.text;
        run.tokOut += estTokens(out); note(true, out);
        return mode !== "json" && got.truncated ? continueReply(tiers[n], prompt, out, step, sample) : out;
      }
      catch(e) {
        note(false);
        if (isControlSignal(e) || halting()) throw e;
        last = e;
      }
    }
    if (tiers.length > 1) fail(tr(tiers.length === 2 ? "The primary model and its backup failed. Last error: {problem}" : "The primary model and all {n} backups failed. Last error: {problem}", { n:tiers.length - 1, problem:(last && last.message) || last }));
    throw last;
  }
  /* A reply cut off by the length limit: ask once for the rest, on the same model, and join the two parts. Matches the runtime. */
  const CONTINUE_PROMPT = "Continue exactly where you stopped. Don't repeat anything you've already written.";
  async function continueReply(tier, prompt, text, step, sample){
    addStep("Reply continued", { mono:true, text:tr("The reply reached the length limit, so the model was asked to carry on from where it stopped.") }).done("continued", "warn");
    if (++run.calls > MAX_AI_CALLS) fail(tr("Stopped after {n} Claude calls in one run, to protect your usage. Check for loops that call Claude too often.", { n:MAX_AI_CALLS }));
    const turns = (typeof prompt === "string" ? [{ role:"user", content:prompt }] : prompt).concat([{ role:"assistant", content:text }, { role:"user", content:CONTINUE_PROMPT }]);
    if (step) step.prefix = text;
    const t0 = performance.now();
    let more;
    try { more = await askOn(tier, turns, step, "text", null, sample); }
    finally { if (step) step.prefix = ""; }
    run.tokIn += estTokens(turns); run.tokOut += estTokens(more.text); addCost(tier, estTokens(turns), estTokens(more.text));
    if (step && step.call) step.call({ who:tierLabel(tier), ms:performance.now() - t0, tin:estTokens(turns), tout:estTokens(more.text), ok:true, prompt:promptText(turns) });
    const joined = text + more.text;  // the continuation picks up exactly where the first part stopped
    if (step) step.text(joined);
    if (more.truncated) {
      run.outOfRounds = true;
      addStep("Cut short", { text:tr("Even after carrying on, the reply was still too long, so it stops part-way. It's kept as it is, marked best effort. Ask for something shorter, or split the job into smaller steps.") }).done("cut short", "warn");
    }
    return joined;
  }
  async function askOn(tier, prompt, step, mode, images, sample){
    const ctl = new AbortController(); run.ctls.add(ctl);
    const away = isElsewhere(tier);
    const opts = { signal:ctl.signal, modelTier:away ? ((/-(quick|default|complex)$/.exec(tier) || [0, "default"])[1]) : tier, cache:false };
    if (away) {
      const svc = serviceOf(tier), who = svc.who || svc.name;
      if (step && step.el && !step.el.dataset.stand) { step.el.dataset.stand = "1"; const n = step.el.querySelector(".step-name"); if (n) n.textContent += " \u00b7 Claude standing in for " + tierLabel(tier); }
      run.awayNoted = run.awayNoted || {};
      if (!run.awayNoted[who]) { run.awayNoted[who] = true; addStep(who, { mono:true, text:tr("{who} can't be reached from this page, so Claude answers in its place. Export to Python to use {who} itself.", { who }) }).done("note", "warn"); }
    }
    if (images && images.length) opts.images = images;
    if (mode !== "json" && step) opts.onText = ({ text }) => step.text((step.prefix || "") + text);
    try {
      if (mode === "json") return await sample.json(prompt, opts);
      const r = await sample(prompt, opts);
      return { text:r.text.trim(), truncated:!!r.truncated };
    } catch(e) {
      if (e && e.code === "cancelled") throw new Halt();
      throw e;
    } finally { run.ctls.delete(ctl); }
  }
  /* The page can't see exact token counts, so it estimates: about 4 characters per token. */
  function estTokens(x){
    if (x == null) return 0;
    if (Array.isArray(x)) return x.reduce((n, t) => n + estTokens(t && typeof t === "object" && "content" in t ? t.content : t), 0);
    const t = typeof x === "string" ? x : JSON.stringify(x);
    return Math.ceil((t || "").length / 4);
  }
  const tokensUsed = () => run ? run.tokIn + run.tokOut : 0;
  const fmtTokens = n => n >= 10000 ? Math.round(n / 1000) + "k" : n >= 1000 ? (n / 1000).toFixed(1) + "k" : String(n);
  /* What the run would cost at the models' list prices (SERVICES' "prices", US dollars per million tokens). On this page
     Claude answers for every model, so that's the price used for another service's tier of the same size. */
  const PRICES = {};
  SERVICES.forEach(s => Object.keys(s.tiers).forEach(k => { const p = s.prices && s.prices[s.tiers[k][0]]; if (p) PRICES[s.prefix + k] = p; }));
  function addCost(tier, tin, tout){
    const p = PRICES[isElsewhere(tier) ? ((/-(quick|default|complex)$/.exec(tier) || [0, "default"])[1]) : tier];
    if (!p) { run.costKnown = false; return; }
    run.cost += (tin * p[0] + tout * p[1]) / 1e6;
  }
  // 'about $0.03' or 'under $0.01'. Matches the runtime's money().
  const money = d => d < 0.005 ? tr("under {cost}", { cost:"$0.01" }) : tr("about {cost}", { cost:"$" + d.toFixed(2) });
  function usageLine(){
    if (!run || !run.calls) return "";
    return "About " + tokensUsed().toLocaleString() + " tokens (" + run.tokIn.toLocaleString() + " sent, " + run.tokOut.toLocaleString() + " received), estimated from the length of the text. Exported Python reports exact counts." +
      (run.budget ? " Budget: " + run.budget.toLocaleString() + "." : "") +
      (run.costKnown && run.cost ? " " + tr("At the models' list prices that's {cost}; on this page it counts toward your Claude usage instead.", { cost:money(run.cost) }) : "");
  }

  /* 'ask me before …': returns true if the action may go ahead. */
  async function allowed(kinds, what){
    if (!kinds.some(k => run.askFirst.has(k))) return true;
    return confirmAction(what);
  }
  async function confirmAction(what){
    const said = what + (/[.!?]$/.test(what) ? "" : ".");
    const ok = await waitForYou("Allow this?", tr("The program wants to {said}", { said }), (box, done) => {
      const row = document.createElement("div"); row.className = "row";
      const yes = document.createElement("button"); yes.type = "button"; yes.className = "primary"; yes.textContent = tr("Allow");
      const no = document.createElement("button"); no.type = "button"; no.textContent = tr("Don't");
      yes.onclick = () => done(true, "allowed"); no.onclick = () => done(false, "refused");
      row.append(yes, no); box.appendChild(row);
    });
    if (!ok) addStep("Not done", { mono:true, text:tr("You said no, so the program skipped this: {said}", { said }) }).done("refused", "warn");
    return ok;
  }

  /* The person answers a question in the log. */
  async function askPerson(q){
    const a = await waitForYou("Question for you", q, (box, done) => {
      const ta = document.createElement("textarea"); ta.id = "answer-" + run.steps + "-" + Date.now(); ta.setAttribute("aria-label", tr("Your answer"));
      const err = document.createElement("div"); err.className = "err"; err.hidden = true; err.textContent = tr("Type an answer first.");
      const row = document.createElement("div"); row.className = "row";
      const send = document.createElement("button"); send.type = "button"; send.className = "primary"; send.textContent = tr("Send answer");
      const go = () => { const v = ta.value.trim(); if (!v) { err.hidden = false; ta.focus(); return; } done(v); };
      send.onclick = go;
      ta.addEventListener("input", () => { err.hidden = true; });
      ta.addEventListener("keydown", e => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) go(); });
      row.appendChild(send); box.append(ta, err, row);
    });
    const last = stepsEl.lastElementChild; if (last) { const bd = last.querySelector(".step-body"); if (bd) bd.textContent = q + "\n\nYou: " + a; }
    return a;
  }

