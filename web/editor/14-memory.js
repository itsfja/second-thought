  // 14-memory.js: Memory that survives between runs.
  /* ---------- Interpreter ---------- */
  /* ---------- Memory ---------- */
  const MEM_LS = "reflection-blocks-memory-v1";
  const mem = { transient:new Map(), saved:new Map(), backend:"checking", db:null, uid:null, ready:null, warned:false };
  const memKey = n => String(n == null ? "" : n).trim().toLowerCase();
  const memDocId = key => "m" + Array.from(new TextEncoder().encode(key)).map(b => b.toString(16).padStart(2, "0")).join("");
  function memInit(){
    if (mem.ready) return mem.ready;
    mem.ready = (async () => {
      try {
        if (window.claude && window.claude.use) {
          const [db, user] = await Promise.all([window.claude.use("db").catch(() => null), window.claude.use("user").catch(() => null)]);
          const uid = user && user.id ? await user.id().catch(() => null) : null;
          if (db && uid) {
            mem.db = db; mem.uid = uid; mem.backend = "account";
            await new Promise(resolve => {
              let first = true;
              db.collection("data/users/" + uid).limit(1000).onSnapshot(snap => {
                mem.saved.clear();
                lib.program.clear(); lib.prompt.clear();
                snap.docs.forEach(d => {
                  const v = d.data(); if (!v || typeof v.name !== "string") return;
                  if (v.type === "program" || v.type === "prompt") lib[v.type].set(memKey(v.name), Object.assign({}, v));
                  else mem.saved.set(memKey(v.name), Object.assign({}, v));
                });
                renderLibrary();
                renderMemory();
                if (first) { first = false; resolve(); }
              }, () => { if (first) { first = false; resolve(); } });
            });
            renderMemory();
            return;
          }
        }
      } catch(e) {}
      try {
        const libRaw = localStorage.getItem(LIB_LS);
        const lo = libRaw ? JSON.parse(libRaw) : {};
        Object.keys(lo).forEach(k => { const v = lo[k]; if (v && lib[v.type]) lib[v.type].set(memKey(v.name), v); });
        renderLibrary();
        const raw = localStorage.getItem(MEM_LS);
        const obj = raw ? JSON.parse(raw) : {};
        Object.keys(obj).forEach(k => mem.saved.set(k, obj[k]));
        localStorage.setItem(MEM_LS, JSON.stringify(obj));
        mem.backend = "browser";
      } catch(e) { mem.backend = "none"; }
      renderMemory();
    })();
    return mem.ready;
  }
  // Searching notes by what's in them: the same as Runtime.memory_terms and rank_notes in python/second_thought/runtime.py,
  // so the agent finds the same notes on the page and in exported Python. Keep the two the same.
  const MEM_STOP = new Set(("a an and are as at be but by do for from had has have i if in into is it its me my no not of on " +
    "or our so than that the their them then there these they this to was we were what when where which who will with you your").split(" "));
  function memTerms(text){
    const out = [];
    for (let w of (str(text).normalize("NFKC").toLowerCase().match(/[\p{L}\p{N}]+/gu) || [])) {
      if (MEM_STOP.has(w)) continue;
      if (w.length > 4 && w.endsWith("ing")) w = w.slice(0, -3);
      else if (w.length > 3 && w.endsWith("ed")) w = w.slice(0, -2);
      else if (w.length > 3 && w.endsWith("s") && !w.endsWith("ss")) w = w.slice(0, -1);
      out.push(w);
    }
    return out;
  }
  function memRank(notes, query, limit){
    const terms = [...new Set(memTerms(query))];
    if (!terms.length || !notes.length) return [];
    const docs = notes.map(n => { const t = memTerms(n.name); return t.concat(t, memTerms(n.value == null ? "" : n.value)); });
    const avg = (docs.reduce((a, d) => a + d.length, 0) / docs.length) || 1;
    const part = (t, w) => t !== w && t.length >= 3 && w.length >= 3 && (w.startsWith(t) || t.startsWith(w));
    const found = [];
    notes.forEach((n, i) => {
      const d = docs[i];
      let score = 0;
      terms.forEach(t => {
        const tf = d.reduce((a, w) => a + (w === t ? 1 : part(t, w) ? 0.5 : 0), 0);
        if (!tf) return;
        const df = docs.filter(e => e.some(w => w === t || part(t, w))).length;
        const idf = Math.log(1 + (docs.length - df + 0.5) / (df + 0.5));
        score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * d.length / avg));
      });
      if (score > 0) found.push({ name:n.name, value:n.value == null ? "" : n.value, updated:n.updated || null, score:Math.round(score * 1e6) / 1e6 });
    });
    found.sort((a, b) => b.score - a.score || (b.updated || 0) - (a.updated || 0) || (a.name.toLowerCase() < b.name.toLowerCase() ? -1 : a.name.toLowerCase() > b.name.toLowerCase() ? 1 : 0));
    return found.slice(0, Math.max(1, Math.floor(limit || 5)));
  }
  window.__memRank = (notes, query, limit) => memRank(notes, query, limit);
  function memSearchText(query, limit){
    query = str(query == null ? "" : query).trim();
    if (!query) fail(tr("search_memory needs some words to look for."));
    const now = Date.now(), notes = [];
    mem.transient.forEach(e => notes.push({ name:e.name, value:str(e.value), updated:now }));
    mem.saved.forEach((e, k) => { if (!mem.transient.has(k) && !(e.expires && e.expires <= now)) notes.push({ name:e.name, value:str(e.value), updated:e.updated || 0 }); });
    const found = memRank(notes, query, limit || 5);
    if (!found.length) return "No saved note matches \u201c" + query + "\u201d." + (notes.length ? " list_memory gives the names of all " + notes.length + "." : " Nothing is saved yet.");
    const day = ms => { if (!ms) return "earlier"; const d = new Date(ms); return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); };
    return "Notes matching \u201c" + query + "\u201d, best first (" + found.length + " of " + notes.length + "):\n" +
      found.map(f => "- " + f.name + " (saved " + day(f.updated) + "): " + short(str(f.value), 300)).join("\n");
  }
  function persistBrowser(){
    try { const o = {}; mem.saved.forEach((v, k) => o[k] = v); localStorage.setItem(MEM_LS, JSON.stringify(o)); } catch(e) {}
  }
  function memStorable(v){
    if (isImg(v)) fail(tr("Pictures can only be remembered 'while this page is open'. Save the picture as a file to keep it."));
    if (Array.isArray(v)) return v.map(memStorable);
    if (isRec(v)) { const o = {}; Object.keys(v).forEach(k => o[k] = memStorable(v[k])); return o; }
    if (v == null) return "";
    if (typeof v === "number" || typeof v === "boolean" || typeof v === "string") return v;
    return String(v);
  }
  function memLive(key){
    let e = mem.transient.get(key) || mem.saved.get(key) || null;
    if (e && e.expires && e.expires <= Date.now()) { memRemove(key); e = null; }
    return e;
  }
  async function memRemoveSaved(key){
    if (!mem.saved.has(key)) return;
    mem.saved.delete(key);
    if (mem.backend === "account") { try { await mem.db.collection("data/users/" + mem.uid).doc(memDocId(key)).delete(); } catch(e) {} }
    else if (mem.backend === "browser") persistBrowser();
  }
  async function memRemove(key){ mem.transient.delete(key); await memRemoveSaved(key); renderMemory(); }
  async function memWrite(name, value, kind, expires){
    const key = memKey(name);
    if (!key) fail(tr("A memory block has no name. Type a name into its name slot."));
    if (kind === "transient") {
      mem.transient.set(key, { name:String(name).trim(), value, kind, expires:null, updated:Date.now() });
      await memRemoveSaved(key); renderMemory(); return "transient";
    }
    const stored = memStorable(value);
    const entry = { name:String(name).trim(), value:stored, kind, expires:expires || null, updated:Date.now() };
    if (JSON.stringify(entry).length > 200000) fail(tr("That value is too big to remember (over 200 KB). Remember something shorter."));
    await memInit();
    if (mem.backend === "none") {
      mem.transient.set(key, Object.assign({}, entry, { kind:"transient", expires:null }));
      renderMemory();
      if (!mem.warned) { mem.warned = true; addStep("Memory", { mono:true, text:tr("Saved memory isn't available here, so this will only last while the page is open.") }).done("note", "warn"); }
      return "transient";
    }
    mem.transient.delete(key);
    mem.saved.set(key, entry); renderMemory();
    if (mem.backend === "account") {
      try { await mem.db.collection("data/users/" + mem.uid).doc(memDocId(key)).set(entry); }
      catch(e) { mem.saved.delete(key); renderMemory(); fail(e && e.code === "quota_exceeded" ? tr("Memory is full. Forget some entries in the Memory panel, then run again.") : tr("That couldn't be saved to memory ({problem}).", { problem:(e && e.code) || "error" })); }
    } else persistBrowser();
    return kind;
  }
  const kindLabel = e => e.kind === "transient" ? tr("while page is open") : e.expires ? tr("until {when}", { when:new Date(e.expires).toLocaleString(document.documentElement.lang || [], { weekday:"short", day:"numeric", month:"short", hour:"2-digit", minute:"2-digit" }) }) : tr("forever");
  function memPreview(v){
    if (isRec(v)) return Object.keys(v).length + " fields: " + Object.keys(v).slice(0, 5).join(", ");
    if (Array.isArray(v)) return v.length + " item" + (v.length === 1 ? "" : "s") + (v.length ? ": " + v.slice(0, 4).map(x => short(str(x), 40)).join(" · ") + (v.length > 4 ? " …" : "") : "");
    return short(str(v), 140) || "(empty)";
  }
  function renderMemory(){
    const where = $("mem-where"), list = $("mem-list");
    if (!where || !list) return;
    where.textContent = tr({
      checking:"Checking where memory can be saved…",
      account:"'Forever' and timed memories are saved to your account for this page. Only you can see them.",
      browser:"'Forever' and timed memories are saved in this browser only. They won't follow you to another device.",
      none:"Saved memory isn't available here. Everything lasts only while the page is open."
    }[mem.backend]);
    const now = Date.now(), rows = [];
    mem.transient.forEach((e, k) => rows.push([k, e]));
    mem.saved.forEach((e, k) => { if (!mem.transient.has(k) && !(e.expires && e.expires <= now)) rows.push([k, e]); });
    rows.sort((a, b) => a[0].localeCompare(b[0]));
    list.innerHTML = "";
    if (!rows.length) { const p = document.createElement("div"); p.className = "mem-empty"; p.textContent = tr("Nothing remembered yet. Use the Memory blocks to remember values between runs."); list.appendChild(p); }
    rows.forEach(([k, e]) => {
      const row = document.createElement("div"); row.className = "mem-row";
      const n = document.createElement("div"); n.className = "mem-name"; n.textContent = e.name;
      const kind = document.createElement("span"); kind.className = "mem-kind " + (e.kind === "transient" ? "transient" : e.expires ? "timed" : "permanent"); kind.textContent = kindLabel(e);
      const v = document.createElement("div"); v.className = "mem-val"; v.textContent = memPreview(e.value);
      const del = document.createElement("button"); del.type = "button"; del.textContent = tr("Forget"); del.setAttribute("aria-label", tr("Forget {name}", { name:e.name }));
      del.onclick = () => memRemove(k);
      row.append(n, kind, v, del); list.appendChild(row);
    });
    $("mem-clear").disabled = !rows.length;
  }
  $("mem-toggle").onclick = () => {
    const el = $("mem"), open = el.hidden;
    el.hidden = !open; $("mem-toggle").setAttribute("aria-expanded", String(open));
    $("mem-confirm").hidden = true;
    if (open) { memInit(); renderMemory(); }
    setTimeout(() => Blockly.svgResize(ws), 0);
  };
  $("mem-clear").onclick = () => { $("mem-confirm").hidden = false; $("mem-clear-no").focus(); };
  $("mem-clear-no").onclick = () => { $("mem-confirm").hidden = true; };
  $("mem-clear-yes").onclick = async () => {
    $("mem-confirm").hidden = true;
    const keys = new Set([...mem.transient.keys(), ...mem.saved.keys()]);
    for (const k of keys) await memRemove(k);
  };
  setInterval(() => { if (!$("mem").hidden) renderMemory(); }, 30000);

