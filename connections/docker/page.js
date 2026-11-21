  /* Docker on the page (#358): a sample stack. Exported Python talks to Docker's Engine API: reads, and restart, stop
     and start after a yes, every time. Matches the runtime's docker_ methods and tests/fake_docker.py. */
  const dkSample = () => { connNote("Docker"); return CONN.docker || {}; };
  const byName = (a, b) => a.name < b.name ? -1 : a.name > b.name ? 1 : 0;
  function dkName(name){
    const n = str(name).trim().replace(/^\/+/, "");
    if (!/^[A-Za-z0-9][A-Za-z0-9_.-]*$/.test(n)) fail(tr("Which Docker container? Give its name, like sonarr."));
    return n;
  }
  function dockerContainers(){
    const out = (dkSample().containers || []).map(c => ({ name:str(c.name), image:str(c.image), state:str(c.state), status:str(c.status), health:str(c.health || ""),
      restarts:Math.trunc(num(c.restarts)), started:str(c.started).slice(0, 16).replace("T", " ") })).sort(byName);
    addStep("Docker containers", { mono:true, text:out.map(c => c.name + ": " + c.status).join("\n") || tr("(nothing)") }).done(tr("{n} containers", { n:out.length }), "ok");
    return out;
  }
  function dockerStats(){
    return (dkSample().containers || []).filter(c => c.state === "running" || c.state === "restarting").map(c => {
      const s = c.stats || {}, cpu = s.cpu_stats || {}, pre = s.precpu_stats || {}, mem = s.memory_stats || {};
      const dCpu = num((cpu.cpu_usage || {}).total_usage || 0) - num((pre.cpu_usage || {}).total_usage || 0), dSys = num(cpu.system_cpu_usage || 0) - num(pre.system_cpu_usage || 0);
      const used = num(mem.usage || 0) - num((mem.stats || {}).inactive_file || 0), limit = num(mem.limit || 0);
      return { name:str(c.name), cpu:dSys > 0 && dCpu > 0 ? cents(dCpu / dSys * num(cpu.online_cpus || 1) * 100) : 0, memory_mb:cents(used / 1048576),
               limit_mb:cents(limit / 1048576), memory:limit ? pct10(used, limit) : "" };
    }).sort(byName);
  }
  function dockerLogs(name, count){
    const n = Math.max(1, Math.min(1000, Math.trunc(num(count)) || 50)), s = dkSample(), id = dkName(name);
    if (!(s.containers || []).some(c => c.name === id)) fail(tr("Docker: {why}.", { why:tr("not found") }));
    return ((s.logs || {})[id] || []).slice(-n);
  }
  async function dockerPower(action, name){
    action = str(action).trim().toLowerCase();
    if (!["restart", "stop", "start"].includes(action)) fail(tr("A Docker container can be restarted, stopped or started."));
    const id = dkName(name), c = (dkSample().containers || []).find(c => c.name === id);
    if (!c) fail(tr("Docker: {why}.", { why:tr("not found") }));
    const what = action + " the Docker container " + id + " (" + c.image + ", now " + c.state + ")";
    if (!(await confirmAction(what + " (it always asks)"))) return false;
    addStep("Docker", { mono:true, text:what }).done(tr("done"), "ok");
    return true;
  }
