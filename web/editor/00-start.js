  // 00-start.js: The editor's opening: shared limits and small helpers ($, STORE_KEY, MAX_*). Every file below runs inside the same function, so names declared in one are seen by the rest.
(function(){
  const $ = id => document.getElementById(id);
  const STORE_KEY = "reflection-blocks-program-v3";
  const MAX_AI_CALLS = 60, MAX_STEPS = 20000, MAX_DEPTH = 60, MAX_SCRIPTS = 100, MAX_LIVE = 30;

  /* Panels are drawers over the canvas (#445): opening one never moves the page, so the program stays where it
     was. While one is open, Tab is kept inside it, Esc closes it, and focus returns to what opened it. */
  const drawers = {};
  let openDrawerEl = null, drawerReturn = null;
  function registerDrawer(id, btnIds, onopen){ drawers[id] = { btns: btnIds || [], onopen: onopen || null }; }
  function drawerFocusables(el){
    return [...el.querySelectorAll("button,select,input,textarea,summary,a[href],[tabindex]")].filter(e => !e.disabled && e.offsetParent !== null);
  }
  function setDrawer(el, open){
    if (open !== el.hidden) return !el.hidden;
    const d = drawers[el.id] || { btns: [], onopen: null };
    if (open) {
      const ret = document.activeElement;
      for (const id in drawers) {
        const o = $(id);
        if (o && o !== el && !o.hidden) setDrawer(o, false);
      }
      drawerReturn = ret;
      el.hidden = false;
      d.btns.forEach(id => $(id) && $(id).setAttribute("aria-expanded", "true"));
      if (d.onopen) d.onopen();
      if (!el.contains(document.activeElement)) {
        const f = drawerFocusables(el);
        (f[0] || el.querySelector("h2") || el).focus();
      }
      openDrawerEl = el;
    } else {
      el.hidden = true;
      d.btns.forEach(id => $(id) && $(id).setAttribute("aria-expanded", "false"));
      if (openDrawerEl === el) openDrawerEl = null;
      if (drawerReturn && drawerReturn.offsetParent && drawerReturn.focus) drawerReturn.focus();
      drawerReturn = null;
    }
    setTimeout(() => { try { Blockly.svgResize(ws); } catch(e) {} }, 0);
    return !el.hidden;
  }
  function toggleDrawer(id, open){ const el = $(id); return setDrawer(el, open === undefined ? el.hidden : open); }
  window.__openDrawer = () => openDrawerEl && openDrawerEl.id;
  document.addEventListener("keydown", e => {
    if (!openDrawerEl) return;
    if (e.key === "Escape") { setDrawer(openDrawerEl, false); e.preventDefault(); e.stopPropagation(); return; }
    if (e.key === "Tab") {
      const f = drawerFocusables(openDrawerEl);
      if (!f.length) { e.preventDefault(); return; }
      const first = f[0], last = f[f.length - 1], a = document.activeElement;
      if (e.shiftKey && (a === first || !openDrawerEl.contains(a))) { last.focus(); e.preventDefault(); }
      else if (!e.shiftKey && (a === last || !openDrawerEl.contains(a))) { first.focus(); e.preventDefault(); }
    }
  });

