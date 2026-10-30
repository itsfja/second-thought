  // 13-run-log.js: The run log's steps.
  /* ---------- Run log UI ---------- */
  const stepsEl = $("steps");
  function addStep(name, opts){
    opts = opts || {};
    const el = document.createElement("div"); el.className = "step" + (opts.human ? " human" : "");
    el.dataset.t0 = String(Date.now());
    el.innerHTML = '<div class="step-top"><span class="step-name"></span><span class="pill" data-state="running"></span></div><div class="step-body"></div>';
    el.querySelector(".step-name").textContent = tr(name);
    el.querySelector(".pill").textContent = tr("running");
    const body = el.querySelector(".step-body"); if (opts.mono) body.classList.add("mono");
    body.textContent = opts.text != null ? opts.text : tr("Thinking…");
    stepsEl.appendChild(el); el.scrollIntoView({ block:"nearest" });
    const pill = el.querySelector(".pill");
    return {
      el, body,
      text(t){ body.textContent = t; },
      list(items){ body.innerHTML = ""; const ul = document.createElement("ul"); items.forEach(i => { const li = document.createElement("li"); li.textContent = i; ul.appendChild(li); }); body.appendChild(ul); },
      done(label, kind){ pill.dataset.state = label; pill.textContent = tr(label); pill.className = "pill" + (kind ? " " + kind : ""); el.dataset.ms = String(Date.now() - Number(el.dataset.t0)); },
      call(c){ (el._calls = el._calls || []).push(c); renderCalls(el); }
    };
  }
  function setStatus(t){ $("status").textContent = tr(t); }
  /* 'Claude · 1.4 s · ~812 in, ~120 out' for the model calls behind one step (several for a repair or a backup). Matches the runtime. */
  function callsSummary(calls){
    if (!calls || !calls.length) return "";
    const who = [...new Set(calls.map(c => c.who))].join(", "), secs = calls.reduce((a, c) => a + c.ms, 0) / 1000;
    const tin = calls.reduce((a, c) => a + c.tin, 0), tout = calls.reduce((a, c) => a + c.tout, 0), failed = calls.filter(c => !c.ok).length;
    return (calls.length > 1 ? calls.length + " calls \u00b7 " : "") + who + " \u00b7 " + secs.toFixed(1) + " s \u00b7 ~" + tin.toLocaleString() + " in, ~" +
      tout.toLocaleString() + " out" + (failed ? " \u00b7 " + failed + " failed" : "");
  }
  function renderCalls(el){
    let meta = el.querySelector(":scope > .step-meta"), det = el.querySelector(":scope > .step-prompt");
    if (!meta) { meta = document.createElement("div"); meta.className = "step-meta"; el.appendChild(meta); }
    if (!det) { det = document.createElement("details"); det.className = "step-prompt"; el.appendChild(det); }
    meta.textContent = callsSummary(el._calls);
    const open = det.open; det.innerHTML = "";
    const sum = document.createElement("summary"); sum.textContent = el._calls.length > 1 ? "Prompts sent (" + el._calls.length + ")" : "Prompt sent";
    det.appendChild(sum);
    el._calls.forEach((c, k) => { const pre = document.createElement("pre"); pre.textContent = (el._calls.length > 1 ? "\u2014 " + (k + 1) + " \u2014\n" : "") + c.prompt; det.appendChild(pre); });
    det.open = open;
  }
  /* The prompt as the model received it, for 'Prompt sent' and the saved log. */
  function promptText(prompt, images){
    const t = typeof prompt === "string" ? prompt : prompt.map(x => "[" + x.role + "]\n" + x.content).join("\n\n");
    return t.length > 20000 ? t.slice(0, 20000) + "\n\u2026 (" + (t.length - 20000).toLocaleString() + " more characters)" : t + (images && images.length ? "\n[+ " + images.length + " picture" + (images.length === 1 ? "" : "s") + "]" : "");
  }

