  // 23-phone.js: On a phone (#450): the program shows as a short outline that can't be edited, with a large Run and
  // the run log; "Edit blocks" opens the full editor. The choice is kept per browser.
  /* ---------- Phone outline ---------- */
  const PHONE_MQ = matchMedia("(max-width:600px)");
  const PHONE_EDIT_KEY = "second-thought-phone-edit";
  function outlineMode(){
    let stored = null;
    try { stored = localStorage.getItem(PHONE_EDIT_KEY); } catch(e) {}
    return PHONE_MQ.matches && stored !== "1";
  }
  function applyOutlineMode(){
    const on = outlineMode();
    document.body.classList.toggle("outline", on);
    $("block-outline").hidden = !on; // [hidden]{display:none!important} would otherwise beat the CSS below
    const btn = $("outline-toggle");
    btn.textContent = on ? tr("Edit blocks") : tr("Show the outline");
    renderOutline();
    try { Blockly.svgResize(ws); } catch(e) {}
  }
  $("outline-toggle").onclick = () => {
    try {
      if (outlineMode()) localStorage.setItem(PHONE_EDIT_KEY, "1");
      else localStorage.removeItem(PHONE_EDIT_KEY);
    } catch(e) {}
    applyOutlineMode();
  };
  if (PHONE_MQ.addEventListener) PHONE_MQ.addEventListener("change", applyOutlineMode);
  // The outline: each script as its hat's words and then each block's own words, one per line, capped.
  function renderOutline(){
    const el = $("block-outline");
    if (!el || !outlineMode()) return;
    el.innerHTML = "";
    const h = document.createElement("h3");
    h.textContent = tr("Program");
    el.appendChild(h);
    let lines = 0;
    const cap = 80;
    for (const top of ws.getTopBlocks(false)) {
      const script = document.createElement("div");
      script.className = "outline-script";
      let b = top, n = 0;
      while (b && lines < cap) {
        const row = document.createElement("div");
        row.className = "outline-row" + (b === top ? " hat" : "");
        row.textContent = b.toString();
        script.appendChild(row);
        lines++; n++;
        b = b.getNextBlock();
      }
      if (b) {
        const more = document.createElement("div");
        more.className = "outline-row";
        more.textContent = tr("… and more");
        script.appendChild(more);
      }
      el.appendChild(script);
      if (lines >= cap) break;
    }
  }
  ws.addChangeListener(ev => { if (!ev.isUiEvent) renderOutline(); });
  applyOutlineMode();
  // The whole program as an outline, for the gallery's web pages (tools/pages.py, #438): [depth, words] for each block in
  // each script, a C-block's inside one deeper. Uncapped, unlike the phone's.
  window.__programOutline = () => {
    const rows = [];
    // A field's words: a dropdown's chosen label, a tick box as ☑ or ☐, anything else as it shows.
    const fieldText = f => {
      if (f instanceof Blockly.FieldDropdown) { const o = (f.getOptions(false) || []).find(x => x[1] === f.getValue()); return o && typeof o[0] === "string" ? o[0] : ""; }
      if (f instanceof Blockly.FieldCheckbox) return f.getValueBoolean() ? "\u2611" : "\u2610";
      return f.getText ? String(f.getText() == null ? "" : f.getText()) : "";
    };
    const inputText = i => i.fieldRow.map(fieldText).filter(Boolean).join(" ")
      + (i.connection && i.type === Blockly.inputs.inputTypes.VALUE && i.connection.targetBlock() ? " " + own(i.connection.targetBlock()) : "");
    const own = b => b.inputList.filter(i => i.type !== Blockly.inputs.inputTypes.STATEMENT).map(inputText)
      .filter(t => t.trim()).join(" ").replace(/\s+/g, " ").trim();
    const walk = (b, depth) => {
      for (; b; b = b.getNextBlock()) {
        if (!b.isEnabled()) continue;
        rows.push([depth, own(b)]);
        b.inputList.filter(i => i.type === Blockly.inputs.inputTypes.STATEMENT).forEach(i => {
          const inner = i.connection && i.connection.targetBlock();
          if (inner) { const label = i.fieldRow.map(fieldText).filter(Boolean).join(" "); if (label) rows.push([depth, label]); walk(inner, depth + 1); }
        });
      }
    };
    ws.getTopBlocks(true).forEach((top, n) => { if (n) rows.push([0, ""]); walk(top, 0); });
    return rows;
  };
  window.__outline = () => ({ mode: document.body.classList.contains("outline"), text: $("block-outline").innerText });
