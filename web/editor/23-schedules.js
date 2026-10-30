  // 23-schedules.js: Schedules and listeners on the page, and the editor's closing line.
  /* ---------- Schedules ---------- */
  const sched = { armed:false, timer:null, lastFired:new Map(), nextEvery:new Map(), wake:null };
  function scheduleHats(){
    return ws.getTopBlocks(false).filter(b => (b.type === "rb_when_time" || b.type === "rb_every") && (!b.isEnabled || b.isEnabled()) && b.getNextBlock());
  }
  const dayOk = (mode, d) => { const w = d.getDay(); return mode === "weekdays" ? (w >= 1 && w <= 5) : mode === "weekends" ? (w === 0 || w === 6) : true; };
  const dateKey = d => d.getFullYear() + "-" + (d.getMonth() + 1) + "-" + d.getDate();
  function hatTime(b){ return [Math.max(0, Math.min(23, Math.round(num(b.getFieldValue("HOUR"))))), Math.max(0, Math.min(59, Math.round(num(b.getFieldValue("MINUTE")))))]; }
  function everyMs(b){ return Math.max(60000, Math.min(86400000, num(b.getFieldValue("N")) * (b.getFieldValue("UNIT") === "h" ? 3600000 : 60000))); }
  function describeHat(b){
    if (b.type === "rb_ha_when") return tr("When {entity} changes", { entity:String(b.getFieldValue("ENTITY") || "").trim() });
    if (b.type === "rb_every") return tr(b.getFieldValue("UNIT") === "h" ? "Every {n} h" : "Every {n} min", { n:num(b.getFieldValue("N")) });
    const [h, m] = hatTime(b); return tr("Scheduled {time}", { time:pad2(h) + ":" + pad2(m) });
  }
  function nextDueFor(b, now){
    if (b.type === "rb_every") { if (!sched.nextEvery.has(b.id)) sched.nextEvery.set(b.id, now + everyMs(b)); return sched.nextEvery.get(b.id); }
    const [h, m] = hatTime(b), mode = b.getFieldValue("DAYS");
    for (let i = 0; i < 8; i++) {
      const d = new Date(now); d.setDate(d.getDate() + i); d.setHours(h, m, 0, 0);
      if (!dayOk(mode, d)) continue;
      if (i === 0 && (sched.lastFired.get(b.id) === dateKey(d) || d.getTime() + 10 * 60000 < now)) continue;
      return d.getTime();
    }
    return Infinity;
  }
  function fire(b, payload){
    const hat = { getNextBlock:() => b.getNextBlock(), payload };
    if (run && run.active) {
      if (!run.ready) { run.pending.push(hat); return; }
      addStep(describeHat(b), { mono:true, text:tr(b.type === "rb_ha_when" ? "A 'when it changes' script started inside the current run." : "A scheduled script started inside the current run.") }).done("started", "ok");
      startScript(b.getNextBlock(), payload);
      return;
    }
    startRun([hat], describeHat(b));
  }
  function schedTick(){
    if (!sched.armed) return;
    const now = Date.now(), hats = scheduleHats();
    hats.forEach(b => {
      if (b.type === "rb_every") {
        const due = nextDueFor(b, now);
        if (now >= due) {
          const iv = everyMs(b); let next = due;
          while (next <= now) next += iv;
          sched.nextEvery.set(b.id, next);
          fire(b);
        }
      } else {
        const due = nextDueFor(b, now);
        if (now >= due && now < due + 10 * 60000) { sched.lastFired.set(b.id, dateKey(new Date(due))); fire(b); }
      }
    });
    updateSchedChip();
  }
  function updateSchedChip(){
    const chip = $("sched-status"), btn = $("sched");
    btn.setAttribute("aria-pressed", String(sched.armed));
    btn.textContent = sched.armed ? tr("Schedules: on") : tr("Schedules: off");
    btn.classList.toggle("on", sched.armed);
    if (!sched.armed) { chip.textContent = ""; chip.hidden = true; return; }
    const now = Date.now();
    let best = Infinity, bestHat = null;
    scheduleHats().forEach(b => { const t = nextDueFor(b, now); if (t < best) { best = t; bestHat = b; } });
    chip.hidden = false;
    chip.textContent = bestHat ? tr("Next: {time} (in {left})", { time:hhmm(new Date(best)), left:fmtLeft(best - now) }) : tr("No scheduled scripts");
  }
  async function wakeLock(on){
    try {
      if (on && navigator.wakeLock && !sched.wake) sched.wake = await navigator.wakeLock.request("screen");
      if (!on && sched.wake) { await sched.wake.release(); sched.wake = null; }
    } catch(e) { sched.wake = null; }
  }
  $("sched").onclick = () => {
    if (!sched.armed) {
      if (!scheduleHats().length) { showBanner("Add a 'when it's …' or 'every …' block from Events, with steps under it, before turning Schedules on."); return; }
      sched.armed = true; sched.nextEvery.clear();
      showBanner("Schedules are on. They run only while this page stays open and your computer is awake. Each run uses your Claude usage.");
      sched.timer = setInterval(schedTick, 5000);
      wakeLock(true);
    } else {
      sched.armed = false; clearInterval(sched.timer); sched.timer = null;
      showBanner(""); wakeLock(false);
    }
    schedTick(); updateSchedChip();
  };
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible" && sched.armed) { sched.wake = null; wakeLock(true); schedTick(); } });
  updateSchedChip();
  // For tests/editor, which runs these in Node without a browser: the editor's functions that need no page.
  window.__editorUnits = { calcText, calcValue, timePlusText, nextDueFor, actionsCrons, migrateProgram, unknownTypes, tr,
    localizeBlock, short, pad2, num, str };
})();
