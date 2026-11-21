  /* Radarr and Sonarr on the page (#398): a sample queue and wanted list. Exported Python talks to their Servarr API:
     reads, and a search after a yes, every time. Matches the runtime's arr_ methods and tests/fake_arr.py. */
  const arrSample = which => { connNote(which === "sonarr" ? "Sonarr" : "Radarr"); return (CONN.arr || {})[which] || {}; };
  const arrName = which => { const w = str(which).trim().toLowerCase();
    if (!["radarr", "sonarr"].includes(w)) fail(tr("Which one? Radarr or Sonarr.")); return w; };
  function arrQueue(which){
    const w = arrName(which), out = (arrSample(w).queue || []).map(r => ({ title:str(r.title), status:str(r.status),
      size_mb:r.size ? cents(num(r.size) / 1048576) : "", left_mb:r.sizeleft ? cents(num(r.sizeleft) / 1048576) : "",
      quality:str(((r.quality || {}).quality || {}).name || ""), eta:str(r.timeleft) }));
    addStep(str(w === "sonarr" ? "Sonarr" : "Radarr") + " queue", { mono:true, text:out.map(r => r.title + ": " + r.status).join("\n") || tr("(nothing)") })
      .done(tr("{n} downloading", { n:out.length }), "ok");
    return out;
  }
  function arrMissing(which){
    const w = arrName(which), out = (arrSample(w).missing || []).map(r => ({ title:str(r.title), added:str(r.added).slice(0, 10), id:Math.trunc(num(r.id)) }));
    addStep(str(w === "sonarr" ? "Sonarr" : "Radarr") + " wanted list", { mono:true, text:out.map(r => r.title + " (added " + r.added + ")").join("\n") || tr("(nothing)") })
      .done(tr("{n} missing", { n:out.length }), "ok");
    return out;
  }
  function arrDiskspace(which){
    const w = arrName(which), out = (arrSample(w).diskspace || []).map(r => ({ path:str(r.path), label:str(r.label),
      free_gb:r.freeSpace ? cents(num(r.freeSpace) / 1073741824) : "", total_gb:r.totalSpace ? cents(num(r.totalSpace) / 1073741824) : "" }));
    addStep(str(w === "sonarr" ? "Sonarr" : "Radarr") + " diskspace", { mono:true, text:out.map(d => d.label + ": " + d.free_gb + " GB free").join("\n") || tr("(nothing)") })
      .done(tr("{n} folders", { n:out.length }), "ok");
    return out;
  }
  async function arrSearch(which){
    const w = arrName(which), who = w === "sonarr" ? "Sonarr" : "Radarr";
    const what = "search " + who + "'s wanted list for what's missing";
    if (!(await confirmAction(what + " (it always asks)"))) return false;
    addStep(who, { mono:true, text:what }).done(tr("done"), "ok");
    return true;
  }
