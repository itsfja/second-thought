  // 22-search.js: Finding a block.
  /* ---------- Block search ---------- */
  const searchIndex = [];
  (function buildIndex(){
    const hw = new Blockly.Workspace();
    toolbox.contents.forEach(cat => {
      (cat.contents || []).forEach(entry => {
        if (entry.kind !== "block") return;
        try {
          const json = Object.assign({}, entry); delete json.kind;
          const blk = Blockly.serialization.blocks.append(json, hw);
          // Found by the words it shows, and by its English words too (so a guide written in English still finds it).
          const en = BLOCK_DEFS.find(d => d.type === json.type);
          const enText = en ? Object.keys(en).filter(k => /^message\d+$/.test(k)).map(k => en[k].replace(/%\d+/g, " ")).join(" ") : "";
          searchIndex.push({ text:(cat.name + " " + catName(cat.name) + " " + blk.toString() + " " + enText).toLowerCase(), entry });
          blk.dispose();
        } catch(e) {}
      });
    });
    hw.dispose();
  })();
  let searchQuery = "";
  ws.registerToolboxCategoryCallback("SEARCH", () => {
    if (!searchQuery) return [{ kind:"label", text:tLabel("Type in 'Find a block' above the canvas.") }];
    const words = searchQuery.split(/\s+/).filter(Boolean);
    const hits = searchIndex.filter(x => words.every(w => x.text.includes(w))).slice(0, 40).map(x => x.entry);
    return hits.length ? hits : [{ kind:"label", text:tLabel("No blocks match") + " \u201c" + searchQuery + "\u201d." }];
  });
  $("block-search").addEventListener("input", e => {
    searchQuery = e.target.value.trim().toLowerCase();
    const tb = ws.getToolbox();
    if (!tb) return;
    const item = tb.getToolboxItems().find(i => i.getName && i.getName() === catName("Search results"));
    if (!searchQuery) { tb.clearSelection(); return; }
    if (item) { tb.setSelectedItem(item); tb.refreshSelection(); }
  });
  $("block-search").addEventListener("keydown", e => { if (e.key === "Escape") { e.target.value = ""; searchQuery = ""; const tb = ws.getToolbox(); if (tb) tb.clearSelection(); } });

  /* Each script runs as its own thread, like Scratch. A finish block anywhere ends them all. */
  function threadError(e){
    if (e instanceof BreakSig || e instanceof ContinueSig) return { code:"user", message:"A 'break out of loop' block was used outside a loop." };
    if (e instanceof ReturnSig) return { code:"user", message:"A 'return' block was used outside a My Blocks definition." };
    return e;
  }
  function startScript(first, payload, evalBlock){
    const tc = { payload:payload === undefined ? "" : payload };
    const p = (async () => {
      try {
        if (evalBlock) {
          const v = await evalv(evalBlock, tc);
          const st = addStep("Value of that block", { text:str(v) });
          if (isImg(v)) showPictureIn(st, v);
          st.done("done", "ok");
          return;
        }
        await runChain(first, tc);
      }
      catch(e) {
        if (e instanceof Halt) return;
        if (run.ending) return;
        run.ending = true;
        if (e instanceof FinishSig) run.finished = true; else run.error = threadError(e);
        endAll();
      }
    })();
    run.threads.add(p);
    const r = run;
    p.finally(() => { r.threads.delete(p); if (r === run) checkStuck(); });
    return p;
  }

  $("stop").onclick = () => {
    if (!run) return;
    run.stopped = true;
    endAll();
    setStatus("stopping…");
  };

  async function startRun(hats, reason, quiet, replay, check){
    if (run && run.active) return false;
    showBanner("");
    if (reason === "manual") stepsEl.innerHTML = "";
    else {
      const empty = stepsEl.querySelector(".empty"); if (empty) empty.remove();
      const div = document.createElement("div"); div.className = "divider";
      div.textContent = reason + " \u00b7 " + hhmm(new Date());
      stepsEl.appendChild(div);
    }
    run = { task:"", draft:"", problems:[], approved:undefined, answer:"", result:[], vars:new Map(),
            tier:$("tier").value, primary:$("tier").value, backups:backupTiers(), calls:0, steps:0, depth:0, stopped:false, ending:false, finished:false, error:null,
            ctls:new Set(), stoppers:new Set(), threads:new Set(), started:0, broadcasts:0, sample:null,
            active:true, ready:false, pending:hats.slice(), timerStart:Date.now(),
            msgWaiters:new Map(), msgNames:new Map(), msgWaiting:0, instructions:"", chats:new Map(), lastError:"",
            budget:0, tokIn:0, tokOut:0, cost:0, costKnown:true, askFirst:new Set(), programs:[], t0:Date.now(), reason, reflect:null, checkpoints:new Map(), agentTrace:[],
            inputs:{}, inputsIncomplete:false, replay:replay ? JSON.parse(JSON.stringify(replay)) : null };
    $("run").disabled = true; $("stop").disabled = false; setStatus("running");
    const started = Date.now();
    try {
      run.sample = await getSample();
      if (!run.sample) { showBanner("Running needs Claude. Open this page in claude.ai while signed in."); throw new Halt(); }
      await memInit();
      run.ready = true;
      run.pending.forEach(h => h.evalBlock ? startScript(null, "", h.evalBlock) : startScript(h.getNextBlock(), h.payload));
      run.pending = [];
      while (run.threads.size) await Promise.all([...run.threads]);
      if (run.error) throw run.error;
      if (run.stopped) throw new Halt();
      if (check) await check();  // a test's check of the result: one more model call, while the run is still open
      stepsEl.querySelectorAll(".pill").forEach(p => { if (["running","waiting","waiting for you"].includes(p.dataset.state)) { p.dataset.state = "ended"; p.textContent = tr("ended"); p.className = "pill warn"; } });
      if (!(quiet && !resultItems().length)) showResult();
      setStatus(tr("done in {time}", { time:fmtLeft(Date.now() - started) }) + " \u00b7 " + tr(run.calls === 1 ? "{n} Claude call" : "{n} Claude calls", { n:run.calls }) + (run.calls ? " \u00b7 " + tr("~{n} tokens", { n:fmtTokens(tokensUsed()) }) : ""));
    } catch(e) {
      stepsEl.querySelectorAll(".pill").forEach(p => { if (["running","waiting","waiting for you"].includes(p.dataset.state)) { p.dataset.state = "interrupted"; p.textContent = tr("interrupted"); p.className = "pill bad"; } });
      if (e instanceof Halt) {
        setStatus("stopped");
        if (run.stopped && resultItems().length) { addStep("Stopped", { text:tr("Run stopped. What was ready so far is below.") }).done("stopped", "warn"); showResult("partial"); }
      } else {
        addStep("Run stopped", { text:errText(threadError(e)) }).done("error", "bad"); setStatus("error");
        if (!(e instanceof Error) && e && e.text) addStep("Partial answer", { text:e.text }).done("kept", "warn");
      }
    } finally {
      try { ws.highlightBlock(null); } catch(e) {}
      $("run").disabled = false; $("stop").disabled = true;
      if (run) { run.active = false; run.ctls.clear(); run.stoppers.clear(); }
      stepper.queue = []; updateStepUi(); renderWatch();
      updateSchedChip();
    }
    return true;
  }

  $("run").onclick = () => {
    const starts = ws.getTopBlocks(true).filter(b => b.type === "rb_start" && (!b.isEnabled || b.isEnabled()));
    if (!starts.length) {
      stepsEl.innerHTML = ""; showBanner("");
      const hasSched = scheduleHats().length;
      addStep("Nothing to run", { text: hasSched
        ? tr("This program only has scheduled scripts. Turn Schedules on to let them run, or add 'when Run is clicked' from Events.")
        : tr("Drag 'when Run is clicked' from Events and attach your steps under it.") }).done("stopped", "bad");
      return;
    }
    startRun(starts, "manual");
  };

