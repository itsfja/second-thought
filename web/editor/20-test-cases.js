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
      // A must-fail case (#427): a saved bad run, and the rule it must break — the test passes only if the review fails it on that rule.
      const badRow = document.createElement("label"); badRow.className = "row";
      const bad = document.createElement("input"); bad.type = "checkbox";
      const badTxt = document.createElement("span"); badTxt.textContent = tr("This run is bad on purpose: it must fail a rule");
      const badRule = document.createElement("input"); badRule.type = "text"; badRule.placeholder = tr("The rule it must break, like: under 200 words");
      badRule.setAttribute("aria-label", tr("The rule it must break, like: under 200 words"));
      badRow.append(bad, badTxt, badRule);
      const row = document.createElement("div"); row.className = "row";
      const save = document.createElement("button"); save.type = "button"; save.className = "primary"; save.textContent = tr("Save test");
      const msg = document.createElement("p"); msg.className = "msg";
      save.onclick = () => {
        const c = crit.value.trim(), mf = bad.checked ? badRule.value.trim() : "";
        if (bad.checked && !mf) { msg.textContent = tr("Say which rule it must break first."); msg.className = "msg bad"; badRule.focus(); return; }
        if (!bad.checked && !c) { msg.textContent = tr("Say what the result must do first."); msg.className = "msg bad"; crit.focus(); return; }
        const t = { name:name.value.trim() || tr("Test {n}", { n:programTests.length + 1 }), value:"", inputs:JSON.parse(JSON.stringify(inputs)), criteria:c };
        if (mf) t.must_fail = mf;
        programTests.push(t);
        testsChanged();
        form.replaceChildren(msg);
        msg.textContent = tr("Saved. Run tests checks it again whenever you like; exported, it's in the zip for python my-program.py --test.") +
          (incomplete ? " " + tr("A file was too big to keep, so that step will ask when the test runs.") : "");
        msg.className = "msg ok";
      };
      row.appendChild(save);
      form.append(name, crit, badRow, row, msg);
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
        const mustFail = String(t.must_fail || "").trim();  // a saved bad run: passes only if the review fails it on that rule (#427)
        const criteria = String(t.criteria || "") || mustFail;
        if (!criteria.trim()) { verdict = [true, []]; return; }
        const s = addStep(tr("Test check: {name}", { name:t.name }));
        const ending = run.ending;
        run.ending = false;  // the program has finished; the check is one more call
        try {
          const rules = parseRules(criteria);
          const ruleList = rules.map((r, i) => (i + 1) + ". " + r).join("\n") || criteria;
          const v = await askChecked(q => ask(q, s, "json"), "You are a strict reviewer. Judge the text ONLY against these rules, one per line:\n" + ruleList +
            "\n\nText:\n" + (finalText() || "(no result)") + '\n\nReply with only JSON like {"approved": false, "rules": [{"rule": "the rule\'s own words", "met": false, "problem": "specific fixable problem", "shows": "the words in the text that show it"}], "problems": ["specific fixable problem"]}. ' +
            "approved is true only if every rule is met; problems repeats the unmet rules' problems as a flat list.", SCHEMAS.review);
          const res = reviewVerdicts(rules, v);
          const unmet = res.verdicts.filter(x => !x.met);
          let ok, probs;
          if (mustFail) {
            ok = !res.approved && unmet.some(x => x.rule === mustFail);
            if (res.approved) probs = [tr("The rule was met: a must-fail case must break it, so rewrite the rule or save a worse draft.")];
            else if (!ok) probs = [tr("The review failed, but not on the rule it must break ({rule}).", { rule:mustFail })]
                                 .concat(unmet.map(x => x.rule + ": " + (x.problem || tr("not met"))));
            else probs = [];
          } else {
            ok = res.approved;
            // name the rule that failed (#424)
            probs = ok ? [] : unmet.map(x => x.rule + ": " + (x.problem || tr("not met")));
            if (!ok && !probs.length) probs = res.problems.filter(x => x.trim()) || [tr("It doesn't yet meet the criteria.")];
          }
          s.text(ok ? tr("Meets every criterion.") : probs.map(x => "- " + x).join("\n")); s.done(ok ? tr("passed") : tr("failed"), ok ? "ok" : "bad");
          verdict = [ok, probs];
        } catch(e) { s.text(errText(e)); s.done("error", "bad"); verdict = [false, [errText(e)]]; }
        finally { run.ending = ending; }
      };
      await startRun(hats, tr("Test: {name}", { name:t.name }), false, t.inputs || {}, check);
      const [passed, problems] = verdict || [false, [run.error ? errText(threadError(run.error)) : tr("The run stopped.")]];
      outcome.push([t, t.name, passed, problems]);
    }
    const n = outcome.length, ok = outcome.filter(o => o[2]).length;
    addStep(tr("Tests"), { text:outcome.map(([t, name, p, probs]) => (p ? "PASS  " : "FAIL  ") + name + (t.must_fail ? "  [" + tr("must fail") + "]" : "") + (probs.length ? "\n" + probs.map(x => "      - " + x).join("\n") : "")).join("\n") })
      .done(tr("{passed} of {n} passed.", { passed:ok, n }), ok === n ? "ok" : "bad");
    setStatus(tr("{passed} of {n} passed.", { passed:ok, n }));
  }
  window.__runTests = runTests;
  $("log-tests").onclick = () => runTests();
  testsChanged();

