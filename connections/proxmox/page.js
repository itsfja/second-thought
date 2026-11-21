  /* Proxmox on the page (#357): a sample cluster. Exported Python talks to your cluster's REST API: reads, and start,
     shut down and reboot after a yes, every time. Matches the runtime's proxmox_ methods and tests/fake_proxmox.py. */
  const pxSample = () => { connNote("Proxmox"); return CONN.proxmox || {}; };
  const pct10 = (used, size) => num(size) ? Math.round(num(used) / num(size) * 1000) / 10 : "";
  const pxWhen = secs => { const d = new Date(secs * 1000); return d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate()) + " " + pad2(d.getHours()) + ":" + pad2(d.getMinutes()); };
  function proxmoxNodes(){
    return (pxSample().nodes || []).map(n => ({ node:str(n.node), status:str(n.status), cpu:Math.round(num(n.cpu) * 1000) / 10, memory:pct10(n.mem, n.maxmem),
      uptime:cents(num(n.uptime) / 3600) })).sort((a, b) => a.node < b.node ? -1 : a.node > b.node ? 1 : 0);
  }
  function proxmoxGuests(){
    const out = (pxSample().guests || []).filter(g => !g.template).map(g => ({ vmid:Math.trunc(num(g.vmid)), name:str(g.name), node:str(g.node),
      type:g.type === "lxc" ? "container" : "vm", status:str(g.status), cpu:Math.round(num(g.cpu) * 1000) / 10, memory:pct10(g.mem, g.maxmem),
      uptime:cents(num(g.uptime) / 3600), onboot:g.status === "stopped" ? str(g.onboot) === "1" : "" })).sort((a, b) => a.vmid - b.vmid);
    addStep("Proxmox guests", { mono:true, text:out.map(g => g.vmid + " " + g.name + ": " + g.status).join("\n") || tr("(nothing)") }).done(tr("{n} guests", { n:out.length }), "ok");
    return out;
  }
  function proxmoxStorage(){
    return (pxSample().storage || []).map(s => ({ storage:str(s.storage), node:str(s.node), used:pct10(s.disk, s.maxdisk), used_gb:cents(num(s.disk) / 1073741824),
      size_gb:cents(num(s.maxdisk) / 1073741824), status:str(s.status) }))
      .sort((a, b) => (a.node + "\u0000" + a.storage) < (b.node + "\u0000" + b.storage) ? -1 : 1);
  }
  function proxmoxTasks(hours){
    const now = Math.floor(Date.now() / 1000), span = Math.max(1, Math.min(24 * 31, num(hours) || 24)) * 3600;
    return (pxSample().tasks || []).filter(t => num(t.ago) <= span).map(t => ({ started:pxWhen(now - num(t.ago)), node:str(t.node), type:str(t.type),
      id:str(t.id), status:str(t.status) || "running", user:str(t.user) })).sort((a, b) => a.started < b.started ? 1 : a.started > b.started ? -1 : 0);
  }
  async function proxmoxPower(action, vmid){
    const words = { start:"start", shutdown:"shut down", reboot:"reboot" };
    action = str(action).trim().toLowerCase().replace(/ /g, "");
    if (!words[action]) fail(tr("A Proxmox guest can be started, shut down or rebooted."));
    if (!isNumLike(vmid) || num(vmid) !== Math.trunc(num(vmid)) || num(vmid) < 100) fail(tr("Which Proxmox guest? Give its VMID, like 101."));
    const g = (pxSample().guests || []).find(g => num(g.vmid) === num(vmid));
    if (!g) fail(tr("Proxmox: {why}.", { why:tr("not found") }));
    const what = words[action] + " the Proxmox guest " + num(vmid) + " (" + g.name + ", on " + g.node + ", now " + g.status + ")";
    if (!(await confirmAction(what + " (it always asks)"))) return false;
    addStep("Proxmox", { mono:true, text:what }).done("sample cluster", "ok");
    return true;
  }
