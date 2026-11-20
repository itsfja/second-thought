  /* UniFi on the page (#359): a sample network. Exported Python reads your console's Network API, and only reads.
     Matches the runtime's unifi_ methods and tests/fake_unifi.py, which serves the same sample. */
  const ufSample = () => { connNote("UniFi"); return CONN.unifi || {}; };
  const ufWhen = t => { const d = new Date(str(t)); return isNaN(d) ? str(t) : d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate()) + " " + pad2(d.getHours()) + ":" + pad2(d.getMinutes()); };
  function unifiClients(){
    const s = ufSample(), names = Object.fromEntries((s.devices || []).map(d => [str(d.id), str(d.name)]));
    const out = (s.clients || []).map(c => ({ name:str(c.name || c.hostname || c.macAddress), mac:str(c.macAddress).toLowerCase(), ip:str(c.ipAddress || ""),
      type:str(c.type).toLowerCase(), connected:ufWhen(c.connectedAt), uplink:names[str(c.uplinkDeviceId)] || "" }));
    addStep("UniFi clients", { mono:true, text:out.map(c => c.name + " (" + (c.ip || c.mac) + ")").join("\n") || tr("(nothing)") }).done(tr("{n} clients", { n:out.length }), "ok");
    return out;
  }
  function unifiDevices(){
    const s = ufSample(), stats = s.statistics || {};
    return (s.devices || []).map(d => {
      const rec = { name:str(d.name), model:str(d.model), mac:str(d.macAddress).toLowerCase(), ip:str(d.ipAddress || ""), state:str(d.state).toLowerCase(),
                    firmware:str(d.firmwareVersion || ""), update:!!d.firmwareUpdatable, uptime:"", cpu:"", memory:"" };
      const st = rec.state === "online" ? stats[str(d.id)] : null;
      if (st) Object.assign(rec, { uptime:isNumLike(st.uptimeSec) ? cents(num(st.uptimeSec) / 3600) : "", cpu:isNumLike(st.cpuUtilizationPct) ? num(st.cpuUtilizationPct) : "",
                                    memory:isNumLike(st.memoryUtilizationPct) ? num(st.memoryUtilizationPct) : "" });
      return rec;
    });
  }
