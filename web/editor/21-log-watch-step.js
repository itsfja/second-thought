  // 21-log-watch-step.js: Saving the log, the watch panel, step mode and running one script.
  /* ---------- Save the run log ---------- */
  function logMarkdown(){
    const name = ($("io-name").value || "").trim() || "my program";
    const out = ["# " + name + ": run log", ""];
    if (run) {
      const d = new Date(run.t0);
      out.push("- Started: " + d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate()) + " " + hhmm(d) + " (" + (run.reason === "manual" ? "Run clicked" : run.reason) + ")");
      out.push("- Model: " + tierLabel(run.primary) + (run.backups.length ? " (backups: " + run.backups.map(tierLabel).join(", ") + ")" : ""));
      out.push("- Claude calls: " + run.calls);
      if (run.calls) out.push("- Tokens: about " + tokensUsed().toLocaleString() + " (" + run.tokIn.toLocaleString() + " sent, " + run.tokOut.toLocaleString() + " received), estimated from text length");
      if (run.budget) out.push("- Budget: " + run.budget.toLocaleString() + " tokens");
    }
    out.push("- Status: " + $("status").textContent, "");
    let n = 0;
    [...stepsEl.children].forEach(el => {
      if (el.classList.contains("divider")) { out.push("---", "", "**" + el.textContent + "**", ""); return; }
      if (!el.classList.contains("step") && !el.classList.contains("result")) return;
      const nameEl = el.querySelector(".step-name"), pill = el.querySelector(".pill"), body = el.querySelector(".step-body");
      const ms = Number(el.dataset.ms), at = run && el.dataset.t0 ? (Number(el.dataset.t0) - run.t0) / 1000 : null;
      const timing = [at != null && at >= 0 ? "+" + at.toFixed(1) + " s" : "", ms >= 0 && !isNaN(ms) ? "took " + (ms / 1000).toFixed(1) + " s" : ""].filter(Boolean).join(", ");
      out.push((el.classList.contains("result") ? "## Result" : "## " + (++n) + ". " + (nameEl ? nameEl.textContent : "Step")) +
        (pill && pill.textContent ? " [" + pill.textContent + "]" : "") + (timing ? "  \u00b7  " + timing : ""));
      const pics = body ? body.querySelectorAll("img").length : 0;
      const text = body ? body.innerText.trim() : "";
      if (el._md) out.push("", el._md);  // a table, written as a markdown table
      else if (text) out.push("", "~~~~", text, "~~~~");
      if (el._calls && el._calls.length) {
        out.push("", "*" + callsSummary(el._calls) + "*");
        el._calls.forEach((c, k) => out.push("", "<details><summary>Prompt sent" + (el._calls.length > 1 ? " (" + (k + 1) + " of " + el._calls.length + ")" : "") + "</summary>", "", "~~~~", c.prompt, "~~~~", "", "</details>"));
      }
      if (pics) out.push("", "(" + pics + " picture" + (pics === 1 ? "" : "s") + ")");
      out.push("");
    });
    return out.join("\n");
  }
  $("log-save").onclick = async () => {
    const btn = $("log-save");
    if (!downloads || !stepsEl.querySelector(".step, .result")) { btn.textContent = tr("Nothing to save yet"); setTimeout(() => btn.textContent = tr("Save log"), 1600); return; }
    const d = new Date(), stamp = d.getFullYear() + pad2(d.getMonth() + 1) + pad2(d.getDate()) + "-" + pad2(d.getHours()) + pad2(d.getMinutes());
    btn.disabled = true;
    try { await downloads.save({ filename:slug(($("io-name").value || "").trim() || "run") + "-log-" + stamp + ".md", data:logMarkdown() }); btn.textContent = tr("Saved"); }
    catch(e) { btn.textContent = e && e.code === "declined" ? "Cancelled" : "Couldn't save"; }
    finally { btn.disabled = false; setTimeout(() => btn.textContent = tr("Save log"), 1600); }
  };

  /* ---------- Watch panel ---------- */
  function renderWatch(){
    const body = $("watch-body");
    if (!$("watch").open || !run) return;
    const rows = [];
    const add = (k, v) => rows.push([k, v]);
    add("task", short(run.task, 160) || "(none)");
    add("draft", run.draft ? short(run.draft, 220) : "(none)");
    if (run.instructions) add("instructions", short(run.instructions, 160));
    if (run.answer) add("answer", short(run.answer, 120));
    if (run.approved !== undefined) add("passed review", run.approved ? "yes" : "no");
    if (run.problems && run.problems.length) add("review problems", run.problems.map(p => "\u2022 " + short(p, 80)).join("\n"));
    run.vars.forEach((v, id) => { const m = ws.getVariableById(id); add(m ? m.name : id, isImg(v) ? str(v) : isRec(v) ? short(str(v).replace(/\n/g, " \u00b7 "), 200) : Array.isArray(v) ? memPreview(v) : short(str(v), 160)); });
    run.chats.forEach((h, k) => add("chat " + k, (h.length / 2) + " turns"));
    if (run.result.length) add("result", run.result.length + " part" + (run.result.length === 1 ? "" : "s"));
    if (run.lastError) add("last error", short(run.lastError, 160));
    add("Claude calls", String(run.calls));
    body.innerHTML = "";
    rows.forEach(([k, v]) => { const a = document.createElement("div"); a.className = "k"; a.textContent = k; const b = document.createElement("div"); b.className = "v"; b.textContent = v; body.append(a, b); });
  }
  setInterval(() => { if (run && run.active) renderWatch(); }, 400);
  $("watch").addEventListener("toggle", renderWatch);

  /* ---------- Step mode ---------- */
  const stepper = { on:false, queue:[] };
  function updateStepUi(){
    $("step-toggle").textContent = stepper.on ? tr("Step: on") : tr("Step: off");
    $("step-toggle").setAttribute("aria-pressed", String(stepper.on));
    $("step-toggle").classList.toggle("on", stepper.on);
    $("stepbar").hidden = !stepper.queue.length;
    if (stepper.queue.length) $("step-text").textContent = tr("Paused before: {step}", { step:short(stepper.queue[0].label, 90) });
  }
  function stepGate(b){
    mark(b);
    return new Promise((resolve, reject) => {
      const entry = { label:b.toString(), resolve:() => { run.stoppers.delete(stop); resolve(); } };
      const stop = () => { stepper.queue = stepper.queue.filter(x => x !== entry); updateStepUi(); reject(new Halt()); };
      run.stoppers.add(stop);
      stepper.queue.push(entry); updateStepUi();
      renderWatch();
      setStatus("paused");
    });
  }
  function releaseStep(all){
    const n = all ? stepper.queue.length : Math.min(1, stepper.queue.length);
    const out = stepper.queue.splice(0, n);
    updateStepUi(); out.forEach(e => e.resolve());
    if (out.length) setStatus("running");
  }
  $("step-toggle").onclick = () => { stepper.on = !stepper.on; if (!stepper.on) releaseStep(true); updateStepUi(); };
  $("step-next").onclick = () => releaseStep(false);
  $("step-go").onclick = () => { stepper.on = false; releaseStep(true); updateStepUi(); };

  /* ---------- Run this script (right-click a block) ---------- */
  const LISTENER_HATS = new Set(["rb_homey_when", "rb_tg_when", "rb_discord_when", "rb_slack_when", "rb_mqtt_when", "rb_webhook_when", "rb_email_when", "rb_feed_when", "rb_folder_when", "rb_gh_when", "rb_gh_issue_when", "rb_gh_release_when", "rb_cal_when", "rb_page_when", "rb_ha_event_when"]);
  const HATS = new Set(["rb_start", "rb_receive", "rb_when_time", "rb_every", "rb_ha_when", ...LISTENER_HATS]);
  function runFromBlock(block){
    if (run && run.active) return;
    const root = block.getRootBlock();
    if (root.type === "procedures_defnoreturn" || root.type === "procedures_defreturn") {
      stepsEl.innerHTML = ""; addStep("Can't run a definition", { text:tr("Right-click a block that uses this My Block, or the script it's in, to run it.") }).done("note", "warn"); return;
    }
    if (root.outputConnection) { startRun([{ evalBlock:root, getNextBlock:() => null }], "manual", true); return; }
    if (LISTENER_HATS.has(root.type)) {  // tried with a sample of what arrives, as if it had just arrived
      startRun([{ getNextBlock:() => root.getNextBlock(), payload:sampleArrival(root) }], "manual", true); return;
    }
    if (HATS.has(root.type)) { startRun([root], "manual", true); return; }
    startRun([{ getNextBlock:() => root }], "manual", true);
  }
  try {
    Blockly.ContextMenuRegistry.registry.register({
      id:"rb_run_script", weight:-100,
      scopeType:Blockly.ContextMenuRegistry.ScopeType.BLOCK,
      displayText:scope => scope.block && scope.block.getRootBlock().outputConnection ? tr("Run this block and show its value") : tr("Run this script"),
      preconditionFn:() => (run && run.active) ? "disabled" : "enabled",
      callback:scope => runFromBlock(scope.block)
    });
  } catch(e) {}

