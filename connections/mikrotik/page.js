  /* MikroTik on the page (#360): a sample switch. Exported Python reads your own through RouterOS's REST API, and
     only reads. Matches the runtime's mikrotik_ methods and tests/fake_mikrotik.py, which serves the same sample. */
  const mtSample = () => { connNote("MikroTik"); return CONN.mikrotik || {}; };
  const mtNum = v => { const m = /-?\d+(?:\.\d+)?/.exec(str(v)); return m ? Number(m[0]) : ""; };
  function mikrotikPorts(){
    const s = mtSample(), mon = s.monitor || {};
    const add = (i, ...ks) => ks.reduce((t, k) => t + (Number(mtNum(i[k])) || 0), 0);
    const out = (s.interfaces || []).filter(i => i.disabled !== "true" && ["ether", "bridge", "vlan", "bond"].includes(i.type)).map(i => ({
      port:str(i.name), running:i.running === "true", speed:i.running === "true" ? str((mon[i.name] || {}).rate || "") : "",
      errors:add(i, "rx-error", "tx-error"), drops:add(i, "rx-drop", "tx-drop"), link_downs:add(i, "link-downs"), comment:str(i.comment || "") }));
    addStep("MikroTik ports", { mono:true, text:out.map(p => p.port + ": " + (p.speed || "-")).join("\n") || tr("(nothing)") }).done(tr("{n} ports", { n:out.length }), "ok");
    return out;
  }
  function mikrotikSfp(){
    const s = mtSample(), mon = s.monitor || {};
    return (s.interfaces || []).filter(i => i.type === "ether" && i.disabled !== "true" && (mon[i.name] || {})["sfp-module-present"] === "true").map(i => {
      const m = mon[i.name];
      return { port:str(i.name), module:[str(m["sfp-vendor-name"] || "").trim(), str(m["sfp-vendor-part-number"] || "").trim()].filter(Boolean).join(" "),
               temperature:mtNum(m["sfp-temperature"]), rx_power:mtNum(m["sfp-rx-power"]), tx_power:mtNum(m["sfp-tx-power"]) };
    });
  }
  function mikrotikHealth(){
    const s = mtSample(), r = s.resource || {};
    const out = { board:str(r["board-name"] || ""), version:str(r.version || ""), uptime:str(r.uptime || ""), cpu_load:mtNum(r["cpu-load"]),
                  free_memory:Math.round((Number(mtNum(r["free-memory"])) || 0) / 1048576 * 10) / 10, temperature:"" };
    for (const h of s.health || []) {
      const v = str(h.value);
      out[str(h.name).replace(/\W+/g, "_").replace(/^_+|_+$/g, "")] = mtNum(v) !== "" && /^-?[\d.]+\w?$/.test(v) ? mtNum(v) : v;
    }
    return out;
  }
  function mikrotikLog(count){
    const n = Math.max(1, Math.min(500, Math.trunc(num(count)) || 20));
    return (mtSample().log || []).slice(-n).map(r => str(r.time) + " " + str(r.topics) + ": " + str(r.message));
  }
