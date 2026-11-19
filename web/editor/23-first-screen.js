// 23-first-screen.js: The first screen (#443). A browser with nothing kept yet (no saved program in localStorage)
// gets three ways in — Describe it (the plain-English box, large, with three sentences to click), Start from an
// example (six chosen ones), Open a file — and lands in the editor with the result on the canvas. Anyone who has
// a program lands in the editor as now: the screen only shows when localStorage holds no program.
  const FIRST_EXAMPLES = ["review", "brainstorm", "r_web", "a_inbox", "ha_doorbell", "w_judges"];
  // Literal tr() calls, so the page's words collector (tests/e2e/i18n.py) sees them; this file runs after 02-blocks.js.
  const FIRST_STARTERS = [
    tr("Every Friday at 6pm, find the best two hours this weekend to dry washing and send it to me on Telegram"),
    tr("When the front door opens, turn on the porch light and send me a Telegram message"),
    tr("Each morning at 8am, summarize my unread email and send me the three most important on Telegram"),
  ];

  function hideFirst(){ $("first").hidden = true; }

  function showFirst(){
    const starters = $("first-starters"); starters.innerHTML = "";
    FIRST_STARTERS.forEach(s => {
      const b = document.createElement("button"); b.type = "button"; b.className = "chip"; b.textContent = s;
      b.onclick = () => { $("first-text").value = s; $("first-text").focus(); };
      starters.appendChild(b);
    });
    const examples = $("first-examples"); examples.innerHTML = "";
    FIRST_EXAMPLES.forEach(k => {
      const e = exampleByKey(k); if (!e) return;
      const b = document.createElement("button"); b.type = "button"; b.textContent = e.title;
      b.onclick = () => { $("example").value = k; loadExample(k); hideFirst(); };
      examples.appendChild(b);
    });
    $("first-build").onclick = () => {
      $("describe-text").value = $("first-text").value;
      hideFirst();  // the editor and the Build-it result show while Claude works
      describeProgram(false);
    };
    $("first-file").onclick = () => $("io-file").click();  // importing a file hides the screen the same way
    $("first").hidden = false;
    $("first").querySelector("h2").focus();
  }

  // firstVisit comes from 08-workspace.js, read before the default program loads (and autosaves) anything.
  let settleUntil = 0;
  if (firstVisit) { showFirst(); settleUntil = Date.now() + 800; }  // the initial load's own events must not hide it
  // Anything that lands a program on the canvas (an import, say) hides the first screen; from then on the autosave
  // keeps it, so the editor is the landing.
  ws.addChangeListener(ev => { if (!ev.isUiEvent && Date.now() > settleUntil) hideFirst(); });
