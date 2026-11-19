// 23-acts.js: What the program on the canvas can act on, before Run (#448). A line under the controls, always
// there, worked out from the blocks as the import panel does — "This program can: send Telegram messages (asks
// first) · read your calendar." — updated as blocks come and go, and read out by screen readers (role=status).
// And a small mark on every block that sends, changes or spends: a triangle when the form asks first, a diamond
// for the no-asking forms (the agent tools' "(no asking)" kinds). A shape, not a colour.
  const MARK_TRIANGLE = "M0 10 L5 0 L10 10 Z";   // asks first
  const MARK_DIAMOND = "M5 0 L10 5 L5 10 L0 5 Z"; // no asking

  // Which mark a block carries, or null: an acting capability, and whether this form of it asks first.
  function actsMark(b){
    const c = blockCapability(b);
    if (!c) return null;
    const cap = CAPABILITIES.find(x => x[0] === c);
    if (!cap || !cap[2]) return null;  // reads and model-only blocks carry no mark
    const kind = b.type === "rb_agent_builtin" ? String(b.getFieldValue("KIND") || "") : "";
    return kind.endsWith("_free") ? "diamond" : "triangle";
  }
  window.__actsMark = b => actsMark(b);       // for the tests
  window.__capBlocks = () => ({ blocks:CAP_BLOCKS, kinds:CAP_KINDS });

  function capsLineText(){
    const caps = programCapabilities();
    if (!caps.length) return tr("It only uses your models: it doesn't connect to anything else.");
    const acts = caps.filter(c => c[2]), reads = caps.filter(c => !c[2]);
    const parts = acts.map(c => tr(c[1]) + " (" + tr("asks first") + ")");
    if (reads.length) parts.push(andList(reads.map(c => tr(c[1]))));
    return tr("This program can: {things}", { things:parts.join(" · ") });
  }

  function updateCapsLine(){ $("caps-line").textContent = capsLineText(); }

  // Re-mark every block after the canvas changes (Blockly rebuilds the SVG on render, so the marks go on after it).
  function markActingBlocks(){
    ws.getAllBlocks(false).forEach(b => {
      const root = b.getSvgRoot && b.getSvgRoot();
      if (!root) return;
      root.querySelectorAll(":scope > .acts-mark").forEach(n => n.remove());
      const shape = actsMark(b);
      if (!shape) return;
      const mark = document.createElementNS("http://www.w3.org/2000/svg", "path");
      mark.setAttribute("class", "acts-mark");
      mark.setAttribute("d", shape === "diamond" ? MARK_DIAMOND : MARK_TRIANGLE);
      mark.setAttribute("transform", `translate(${Math.max(0, (b.width || 0) - 14)} 3)`);
      mark.dataset.shape = shape;
      root.appendChild(mark);
    });
  }
  function refreshActs(){
    updateCapsLine();
    setTimeout(markActingBlocks, 0);
  }
  ws.addChangeListener(ev => { if (!ev.isUiEvent) refreshActs(); });
  refreshActs();
