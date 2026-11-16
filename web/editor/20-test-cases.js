  // 20-test-cases.js: Test cases: Save as test case and Run tests.
  /* ---------- Test cases ---------- */
  // After a good run: keep its answers with what the result must do. Run tests replays them, with the models live, and a
  // strict reviewer checks each result. Exported, python my-program.py --test does the same.
  function saveTestButton(resultEl){
    const btn = document.createElement("button"); btn.type = "button"; btn.textContent = tr("Save as test case");
    const inputs = run.inputs, incomplete = run.inputsIncomplete;
    btn.onclick = () => {
      btn.disabled = true;
      const form = document.createElement("div"); form.className = "test-form";
      const name = document.createElement("input"); name.type = "text"; name.value = tr("Test {n}", { n:programTests.length + 1 });
      name.setAttribute("aria-label", tr("Test name"));
      const crit = document.createElement("textarea"); crit.placeholder = tr("What the result must do, separated by semicolons, like: under 200 words; names the date");
      crit.setAttribute("aria-label", tr("What the result must do"));
      const row = document.createElement("div"); row.className = "row";
      const save = document.createElement("button"); save.type = "button"; save.className = "primary"; save.textContent = tr("Save test");
      const msg = document.createElement("p"); msg.className = "msg";
      save.onclick = () => {
        const c = crit.value.trim();
        if (!c) { msg.textContent = tr("Say what the result must do first."); msg.className = "msg bad"; crit.focus(); return; }
        programTests.push({ name:name.value.trim() || tr("Test {n}", { n:programTests.length + 1 }), value:"", inputs:JSON.parse(JSON.stringify(inputs)), criteria:c });
        testsChanged();
        form.replaceChildren(msg);
        msg.textContent = tr("Saved. Run tests checks it again whenever you like; exported, it's in the zip for python my-program.py --test.") +
          (incomplete ? " " + tr("A file was too big to keep, so that step will ask when the test runs.") : "");
        msg.className = "msg ok";
      };
      row.appendChild(save);
      form.append(name, crit, row, msg);
      resultEl.appendChild(form); crit.focus();
    };
    return btn;
  }
  async function runTests(){
    if (run && run.active) return;
    const starts = ws.getTopBlocks(true).filter(b => b.type === "rb_start" && (!b.isEnabled || b.isEnabled()));
    stepsEl.innerHTML = "";
    if (!starts.length) { addStep("Nothing to run", { text:tr("Drag 'when Run is clicked' from Events and attach your steps under it.") }).done("stopped", "bad"); return; }
    const outcome = [];
    for (const t of programTests.slice()) {
      const hats = starts.map(b => ({ getNextBlock:() => b.getNextBlock(), payload:t.value || "" }));
      let verdict = null;
      const check = async () => {
        if (!String(t.criteria || "").trim()) { verdict = [true, []]; return; }
        const s = addStep(tr("Test check: {name}", { name:t.name }));
        const ending = run.ending;
        run.ending = false;  // the program has finished; the check is one more call
        try {
          const rules = parseRules(t.criteria);
          const ruleList = rules.map((r, i) => (i + 1) + ". " + r).join("\n") || String(t.criteria || "");
          const v = await askChecked(q => ask(q, s, "json"), "You are a strict reviewer. Judge the text ONLY against these rules, one per line:\n" + ruleList +
            "\n\nText:\n" + (finalText() || "(no result)") + '\n\nReply with only JSON like {"approved": false, "rules": [{"rule": "the rule\'s own words", "met": false, "problem": "specific fixable problem", "shows": "the words in the text that show it"}], "problems": ["specific fixable problem"]}. ' +
            "approved is true only if every rule is met; problems repeats the unmet rules' problems as a flat list.", SCHEMAS.review);
          const res = reviewVerdicts(rules, v);
          const ok = res.approved;
          // name the rule that failed (#424)
          let probs = ok ? [] : res.verdicts.filter(x => !x.met).map(x => x.rule + ": " + (x.problem || tr("not met")));
          if (!ok && !probs.length) probs = res.problems.filter(x => x.trim()) || [tr("It doesn't yet meet the criteria.")];
          s.text(ok ? tr("Meets every criterion.") : probs.map(x => "- " + x).join("\n")); s.done(ok ? tr("passed") : tr("failed"), ok ? "ok" : "bad");
          verdict = [ok, probs];
        } catch(e) { s.text(errText(e)); s.done("error", "bad"); verdict = [false, [errText(e)]]; }
        finally { run.ending = ending; }
      };
      await startRun(hats, tr("Test: {name}", { name:t.name }), false, t.inputs || {}, check);
      const [passed, problems] = verdict || [false, [run.error ? errText(threadError(run.error)) : tr("The run stopped.")]];
      outcome.push([t.name, passed, problems]);
    }
    const n = outcome.length, ok = outcome.filter(o => o[1]).length;
    addStep(tr("Tests"), { text:outcome.map(([name, p, probs]) => (p ? "PASS  " : "FAIL  ") + name + (probs.length ? "\n" + probs.map(x => "      - " + x).join("\n") : "")).join("\n") })
      .done(tr("{passed} of {n} passed.", { passed:ok, n }), ok === n ? "ok" : "bad");
    setStatus(tr("{passed} of {n} passed.", { passed:ok, n }));
  }
  window.__runTests = runTests;
  $("log-tests").onclick = () => runTests();
  testsChanged();

