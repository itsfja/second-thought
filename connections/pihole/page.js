  /* Pi-hole on the page (#401): a sample network. Exported Python talks to its REST API: reads, and changes
     that always ask. */
  const piholeSample = () => { connNote("Pi-hole"); return CONN.pihole || {}; };
  function piholeSummary(){
    const s = piholeSample(), q = s.summary.queries || {}, out = { queries:Math.trunc(num(q.total)), blocked:Math.trunc(num(q.blocked)),
      blocked_pct:num(q.percent), gravity:Math.trunc(num((s.summary.gravity || {}).domains)),
      clients:Math.trunc(num((s.summary.clients || {}).total)), blocking:!!s.blocking };
    addStep("Pi-hole summary", { mono:true, text:out.queries + " queries, " + out.blocked + " blocked (" + out.blocked_pct + " %), "
      + (out.blocking ? "blocking on" : "blocking off") })
      .done(tr("done"), "ok");
    return out;
  }
  function piholeTopDomains(n){
    const out = (piholeSample().top_domains || []).slice(0, Math.max(1, Math.trunc(num(n)) || 5))
      .map(r => ({ domain:str(r.domain), count:Math.trunc(num(r.count)) }));
    addStep("Pi-hole top blocked domains", { mono:true, text:out.map(r => r.domain + ": " + r.count).join("\n") || tr("(nothing)") })
      .done(tr("{n} domains", { n:out.length }), "ok");
    return out;
  }
  function piholeTopClients(n){
    const out = (piholeSample().top_clients || []).slice(0, Math.max(1, Math.trunc(num(n)) || 5))
      .map(r => ({ name:str(r.name || r.ip), ip:str(r.ip), count:Math.trunc(num(r.count)) }));
    addStep("Pi-hole top clients", { mono:true, text:out.map(r => r.name + ": " + r.count).join("\n") || tr("(nothing)") })
      .done(tr("{n} clients", { n:out.length }), "ok");
    return out;
  }
  async function piholeAsking(what){
    if (!(await confirmAction(what + " (it always asks)"))) return false;
    addStep("Pi-hole", { mono:true, text:what }).done(tr("done"), "ok");
    return true;
  }
