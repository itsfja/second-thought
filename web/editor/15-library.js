  // 15-library.js: Saved programs and the prompt library.
  /* ---------- Saved programs and prompt library ---------- */
  const LIB_LS = "reflection-blocks-library-v1";
  const lib = { program:new Map(), prompt:new Map() };
  const libDocId = (type, key) => (type === "program" ? "p" : "q") + memDocId(key).slice(1);
  function persistLibBrowser(){
    try { const o = {}; ["program","prompt"].forEach(t => lib[t].forEach((v, k) => o[t + ":" + k] = v)); localStorage.setItem(LIB_LS, JSON.stringify(o)); } catch(e) {}
  }
  async function libSave(type, name, payload){
    const key = memKey(name);
    if (!key) throw new Error(tr("Give it a name first."));
    const entry = Object.assign({ type, name:String(name).trim(), updated:Date.now() }, payload);
    if (JSON.stringify(entry).length > 240000) throw new Error(tr("That's too big to save (over 240 KB)."));
    await memInit();
    if (mem.backend === "none") throw new Error(tr("Saving isn't available here. Use Import / export to keep a copy as a file."));
    lib[type].set(key, entry); renderLibrary();
    if (mem.backend === "account") {
      try { await mem.db.collection("data/users/" + mem.uid).doc(libDocId(type, key)).set(entry); }
      catch(e) { lib[type].delete(key); renderLibrary(); throw new Error(e && e.code === "quota_exceeded" ? tr("Your saved space is full. Delete something first.") : tr("That couldn't be saved ({problem}).", { problem:(e && e.code) || "error" })); }
    } else persistLibBrowser();
  }
  async function libDelete(type, key){
    lib[type].delete(key); renderLibrary();
    if (mem.backend === "account") { try { await mem.db.collection("data/users/" + mem.uid).doc(libDocId(type, key)).delete(); } catch(e) {} }
    else persistLibBrowser();
  }
  const libMsg = (text, kind) => { const m = $("lib-msg"); if (!m) return; m.textContent = tr(text); m.className = "msg" + (kind ? " " + kind : ""); };
  let beforeOpen = null;
  function when(t){ try { return new Date(t).toLocaleString([], { day:"numeric", month:"short", hour:"2-digit", minute:"2-digit" }); } catch(e) { return ""; } }
  function renderLibrary(){
    const pl = $("lib-programs"), ql = $("lib-prompts");
    if (!pl || !ql) return;
    $("lib-where").textContent = tr({ checking:"Checking where things can be saved…", account:"Saved to your account for this page. Only you can see them.",
      browser:"Saved in this browser only.", none:"Saving isn't available here. Use Import / export to keep files instead." }[mem.backend]);
    const mk = (type, holder, emptyText, onOpen) => {
      holder.innerHTML = "";
      const rows = [...lib[type].entries()].sort((a, b) => a[0].localeCompare(b[0]));
      if (!rows.length) { const p = document.createElement("div"); p.className = "mem-empty"; p.textContent = tr(emptyText); holder.appendChild(p); return; }
      rows.forEach(([k, e]) => {
        const row = document.createElement("div"); row.className = "lib-row";
        const n = document.createElement("div"); n.className = "mem-name"; n.textContent = e.name;
        const d = document.createElement("div"); d.className = "mem-val"; d.textContent = type === "prompt" ? short(e.text, 90) : tr("saved {when}", { when:when(e.updated) });
        const open = document.createElement("button"); open.type = "button"; open.textContent = type === "prompt" ? tr("Edit") : tr("Open"); open.onclick = () => onOpen(e);
        const del = document.createElement("button"); del.type = "button"; del.textContent = tr("Delete");
        del.onclick = () => { if (del.dataset.armed) libDelete(type, k); else { del.dataset.armed = "1"; del.textContent = tr("Confirm delete"); del.className = "danger"; setTimeout(() => { if (del.isConnected) { delete del.dataset.armed; del.textContent = tr("Delete"); del.className = ""; } }, 4000); } };
        row.append(n, d, open, del); holder.appendChild(row);
      });
    };
    mk("program", pl, tr("No saved programs yet. Name the one on the canvas and press Save."), e => {
      let state; try { state = JSON.parse(e.program); } catch(err) { libMsg("That saved program is damaged and can't be opened.", "bad"); return; }
      try { state = migrateProgram(state, e.version).state; } catch(err) { libMsg(err.message, "bad"); return; }
      const prev = saveWs();
      try { load(state); try { ws.zoomToFit(); } catch(x) {} }
      catch(err) { load(prev); libMsg("That program couldn't be opened, so the canvas was left as it was.", "bad"); return; }
      try { setTests(e.tests ? JSON.parse(e.tests) : []); } catch(err) { setTests([]); }
      beforeOpen = prev; $("lib-undo").hidden = false; $("lib-name").value = e.name; $("io-name").value = slug(e.name);
      libMsg(tr("Opened \u201c{name}\u201d.", { name:e.name }), "ok");
    });
    mk("prompt", ql, tr("No prompts yet. Add reusable prompt text here, then use the 'prompt' block in Ask Claude."), e => {
      $("prompt-name").value = e.name; $("prompt-text").value = e.text; $("prompt-text").focus();
    });
  }
  $("lib-toggle").onclick = () => {
    const el = $("lib"), open = el.hidden;
    el.hidden = !open; $("lib-toggle").setAttribute("aria-expanded", String(open));
    if (open) { memInit(); renderLibrary(); if (!$("lib-name").value) $("lib-name").value = $("io-name").value || ""; }
    setTimeout(() => Blockly.svgResize(ws), 0);
  };
  $("lib-save").onclick = async () => {
    const name = $("lib-name").value.trim();
    if (!name) { libMsg("Type a name for this program first.", "bad"); $("lib-name").focus(); return; }
    const exists = lib.program.has(memKey(name));
    if (exists && !$("lib-save").dataset.armed) { $("lib-save").dataset.armed = "1"; $("lib-save").textContent = tr("Replace \u201c{name}\u201d", { name }); libMsg("A program with that name exists. Press again to replace it."); return; }
    delete $("lib-save").dataset.armed; $("lib-save").textContent = tr("Save");
    try { await libSave("program", name, { program:JSON.stringify(saveWs()), version:FORMAT_VERSION, tests:JSON.stringify(programTests) }); libMsg(tr("Saved \u201c{name}\u201d.", { name }), "ok"); }
    catch(e) { libMsg(e.message, "bad"); }
  };
  $("lib-name").addEventListener("input", () => { delete $("lib-save").dataset.armed; $("lib-save").textContent = tr("Save"); libMsg(""); });
  $("lib-undo").onclick = () => { if (!beforeOpen) return; load(beforeOpen); beforeOpen = null; $("lib-undo").hidden = true; libMsg("Back to the program you had before.", "ok"); };
  $("prompt-save").onclick = async () => {
    const name = $("prompt-name").value.trim(), text = $("prompt-text").value;
    if (!name) { libMsg("Give the prompt a name.", "bad"); $("prompt-name").focus(); return; }
    if (!text.trim()) { libMsg("Type the prompt text.", "bad"); $("prompt-text").focus(); return; }
    try { await libSave("prompt", name, { text }); libMsg(tr("Saved prompt \u201c{name}\u201d. Use it with the 'prompt' block.", { name }), "ok"); $("prompt-name").value = ""; $("prompt-text").value = ""; }
    catch(e) { libMsg(e.message, "bad"); }
  };
  setTimeout(memInit, 0);

