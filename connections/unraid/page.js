  /* Unraid on the page (#399): a sample server. Exported Python talks to its GraphQL API: reads, and start, stop
     and parity that always ask. */
  const unraidSample = () => { connNote("Unraid"); return CONN.unraid || {}; };
  function unraidArray(){
    const s = unraidSample(), a = s.array || {}, kb = (a.capacity || {}).kilobytes || {},
      out = { state:str(a.state), started:str(a.state) === "STARTED",
        free_gb:kb.free ? cents(num(kb.free) / 1048576) : "", total_gb:kb.total ? cents(num(kb.total) / 1048576) : "",
        uptime:str(((s.info || {}).os || {}).uptime) };
    addStep("Unraid array", { mono:true, text:out.state + (out.free_gb ? ", " + out.free_gb + " GB free of " + out.total_gb + " GB" : "") })
      .done(tr("done"), "ok");
    return out;
  }
  function unraidDisks(){
    const a = (unraidSample().array || {}),
      out = ["parities", "disks", "caches"].flatMap(k => a[k] || []).map(r => ({ name:str(r.name), type:str(r.type).toLowerCase() ===
        "parity" ? "Parity" : str(r.type).toLowerCase() === "cache" ? "Cache" : "Data", status:str(r.status),
        temp_c:r.temp === null || r.temp === undefined ? "" : num(r.temp), errors:r.numErrors === null || r.numErrors === undefined ? "" : num(r.numErrors),
        size_gb:r.fsSize ? cents(num(r.fsSize) / 1048576) : "", free_gb:r.fsFree ? cents(num(r.fsFree) / 1048576) : "" }));
    addStep("Unraid disks", { mono:true, text:out.map(r => r.name + " (" + r.type + ")" + (r.temp_c === "" ? "" : ": " + r.temp_c + " \u00b0C")).join("\n") || tr("(nothing)") })
      .done(tr("{n} disks", { n:out.length }), "ok");
    return out;
  }
  function unraidShares(){
    const out = (unraidSample().shares || []).map(r => ({ name:str(r.name),
      free_gb:r.free ? cents(num(r.free) / 1048576) : "", used_gb:r.used ? cents(num(r.used) / 1048576) : "",
      total_gb:r.size ? cents(num(r.size) / 1048576) : "" }));
    addStep("Unraid shares", { mono:true, text:out.map(r => r.name + ": " + r.free_gb + " GB free").join("\n") || tr("(nothing)") })
      .done(tr("{n} shares", { n:out.length }), "ok");
    return out;
  }
  function unraidContainers(){
    const out = (unraidSample().dockerContainers || []).map(r => ({ name:str((r.names || [""])[0]), state:str(r.state),
      status:str(r.status), auto_start:!!r.autoStart }));
    addStep("Unraid containers", { mono:true, text:out.map(r => r.name + ": " + r.state).join("\n") || tr("(nothing)") })
      .done(tr("{n} containers", { n:out.length }), "ok");
    return out;
  }
  function unraidVms(){
    const out = (((unraidSample().vms || {}).domains) || []).map(r => ({ name:str(r.name), state:str(r.state) }));
    addStep("Unraid VMs", { mono:true, text:out.map(r => r.name + ": " + r.state).join("\n") || tr("(nothing)") })
      .done(tr("{n} VMs", { n:out.length }), "ok");
    return out;
  }
  async function unraidPower(kind, action, name){
    const what = action + " the Unraid " + (kind === "vm" ? "VM " : "container ") + name;
    if (!(await confirmAction(what + " (it always asks)"))) return false;
    addStep("Unraid", { mono:true, text:what }).done(tr("done"), "ok");
    return true;
  }
  async function unraidParity(){
    const what = "check Unraid's parity";
    if (!(await confirmAction(what + " (it always asks)"))) return false;
    addStep("Unraid", { mono:true, text:what }).done(tr("done"), "ok");
    return true;
  }
