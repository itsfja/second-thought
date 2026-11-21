  /* Plex and Tautulli on the page (#402): a sample server. Exported Python talks to your Plex through the
     X-Plex-Token API and to Tautulli: reads, and a library scan and a stream stop after a yes, every time.
     Matches the runtime's plex_ and tautulli_ methods and tests/fake_plex.py. */
  const plexSample = () => { connNote("Plex"); return CONN.plex || {}; };
  function plexServer(){
    const s = plexSample(), out = { name:str((s.server || {}).name), version:str((s.server || {}).version), up:true };
    addStep("Plex server", { mono:true, text:out.name + " " + out.version }).done(tr("up"), "ok");
    return out;
  }
  function plexLibraries(){
    const out = (plexSample().libraries || []).map(l => ({ name:str(l.name), type:str(l.type), count:Math.trunc(num(l.count)) }));
    addStep("Plex libraries", { mono:true, text:out.map(l => l.name + " (" + l.type + "): " + l.count).join("\n") || tr("(nothing)") })
      .done(tr("{n} libraries", { n:out.length }), "ok");
    return out;
  }
  function plexSessions(){
    const out = (plexSample().sessions || []).map(s => ({ id:str(s.id), user:str(s.user), title:str(s.title), player:str(s.player),
      state:str(s.state), transcode:!!s.transcode }));
    addStep("Plex sessions", { mono:true, text:out.map(s => s.user + ": " + s.title + " (" + s.state + ")").join("\n") || tr("(nothing)") })
      .done(tr("{n} sessions", { n:out.length }), "ok");
    return out;
  }
  function plexRecent(days){
    const n = Math.max(1, Math.min(365, Math.trunc(num(days)) || 7)), cutoff = Date.now() / 1000 - n * 86400;
    const out = (plexSample().recent || []).filter(r => !num(r.added) || num(r.added) >= cutoff)
      .map(r => ({ title:str(r.title), library:str(r.library), added:num(r.added) ? sbWhen(num(r.added)) : "" }));
    addStep("Plex new items", { mono:true, text:out.map(r => r.title + " (" + r.library + ")").join("\n") || tr("(nothing)") })
      .done(tr("{n} items", { n:out.length }), "ok");
    return out;
  }
  function tautulliHistory(days){
    const n = Math.max(1, Math.min(365, Math.trunc(num(days)) || 7)), cutoff = Date.now() / 1000 - n * 86400;
    const out = (plexSample().history || []).filter(h => !num(h.when) || num(h.when) >= cutoff)
      .map(h => ({ user:str(h.user), title:str(h.title), when:num(h.when) ? sbWhen(num(h.when)) : "", transcode:!!h.transcode }));
    addStep("Tautulli history", { mono:true, text:out.map(h => h.user + ": " + h.title).join("\n") || tr("(nothing)") })
      .done(tr("{n} plays", { n:out.length }), "ok");
    return out;
  }
  function tautulliWatchtime(days){
    const n = Math.max(1, Math.min(365, Math.trunc(num(days)) || 7)), cutoff = Date.now() / 1000 - n * 86400;
    const seen = {};
    (plexSample().history || []).filter(h => !num(h.when) || num(h.when) >= cutoff)
      .forEach(h => { seen[str(h.user)] = (seen[str(h.user)] || 0) + num(h.duration); });
    const out = Object.keys(seen).map(u => ({ user:u, hours:cents(seen[u] / 3600) }))
      .sort((a, b) => b.hours - a.hours);
    addStep("Tautulli watch time", { mono:true, text:out.map(w => w.user + ": " + w.hours).join("\n") || tr("(nothing)") })
      .done(tr("{n} users", { n:out.length }), "ok");
    return out;
  }
  async function plexAsking(what){
    if (!(await confirmAction(what + " (it always asks)"))) return false;
    addStep("Plex", { mono:true, text:what }).done(tr("done"), "ok");
    return true;
  }
