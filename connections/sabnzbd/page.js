  /* SABnzbd on the page (#397): a sample queue. Exported Python talks to SABnzbd's API: reads, and pause and
     resume after a yes, every time. Matches the runtime's sabnzbd_ methods and tests/fake_sabnzbd.py. */
  const sbSample = () => { connNote("SABnzbd"); return CONN.sabnzbd || {}; };
  const sbWhen = secs => { const d = new Date(secs * 1000); return d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate()) + " " + pad2(d.getHours()) + ":" + pad2(d.getMinutes()); };
  function sabnzbdQueue(){
    const q = sbSample().queue || {}, out = (q.slots || []).map(s => ({ name:str(s.filename), size_mb:cents(num(s.mb)), left_mb:cents(num(s.mbleft)),
      percent:cents(num(s.percentage)), eta:str(s.timeleft) || "0:00:00", status:str(s.status) }));
    const head = (q.paused === true || str(q.paused).toLowerCase() === "true" ? "Paused" : "Downloading") + ", " + cents(num(q.mbleft)) + " MB left";
    addStep("SABnzbd queue", { mono:true, text:head + (out.length ? "\n" + out.map(s => s.name + ": " + s.left_mb + " MB left (" + s.percent + "%)").join("\n") : "") })
      .done(tr("{n} in the queue", { n:out.length }), "ok");
    return out;
  }
  function sabnzbdHistory(hours){
    const n = Math.max(1, Math.min(500, Math.trunc(num(hours)) || 24)), cutoff = Date.now() / 1000 - n * 3600;
    const out = (sbSample().history?.slots || []).filter(s => !num(s.completed) || num(s.completed) >= cutoff)
      .map(s => ({ name:str(s.name), status:str(s.status), size_mb:s.bytes ? cents(num(s.bytes) / 1048576) : "",
        when:num(s.completed) ? sbWhen(num(s.completed)) : "", why:str(s.status).toLowerCase() === "failed" ? str(s.fail_message) : "" })).reverse();
    addStep("SABnzbd history", { mono:true, text:out.map(s => s.name + ": " + s.status).join("\n") || tr("(nothing)") }).done(tr("{n} finished", { n:out.length }), "ok");
    return out;
  }
  function sabnzbdDiskspace(){
    const out = (sbSample().diskspace || []).filter(r => Array.isArray(r) && r.length >= 2).map(r => ({ folder:str(r[0]), free_gb:cents(num(r[1])) }));
    addStep("SABnzbd diskspace", { mono:true, text:out.map(d => d.folder + ": " + d.free_gb + " GB free").join("\n") || tr("(nothing)") }).done(tr("{n} folders", { n:out.length }), "ok");
    return out;
  }
  async function sabnzbdPause(action){
    action = str(action).trim().toLowerCase();
    if (!["pause", "resume"].includes(action)) fail(tr("SABnzbd can be paused or resumed."));
    const q = sbSample().queue || {}, what = (action === "pause" ? "pause" : "resume") + " SABnzbd's queue (" + cents(num(q.mbleft)) + " MB left, " + (q.slots || []).length + " in the queue)";
    if (!(await confirmAction(what + " (it always asks)"))) return false;
    addStep("SABnzbd", { mono:true, text:what }).done(tr("done"), "ok");
    return true;
  }
