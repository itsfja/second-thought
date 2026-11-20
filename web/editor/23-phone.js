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
  window.__outline = () => ({ mode: document.body.classList.contains("outline"), text: $("block-outline").innerText });
