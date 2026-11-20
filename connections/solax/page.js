  /* Solax on the page (#361): a sample inverter. Exported Python reads your own through SolaxCloud's end-user API, and
     only reads. Matches the runtime's solax_now and tests/fake_solax.py, which serves the same sample. */
  const solaxNum = v => { const m = /-?\d+(?:\.\d+)?/.exec(str(v)); return m ? Number(m[0]) : ""; };
  const solaxStatus = code => ({ 100:"Wait Mode", 101:"Check Mode", 102:"Normal Mode", 103:"Fault Mode", 104:"Permanent Fault Mode",
    105:"Update Mode", 106:"EPS Check Mode", 107:"EPS Mode", 108:"Self-Test Mode", 109:"Idle Mode", 110:"Standby Mode",
    111:"Pv Wake Up Bat Mode", 112:"Gen Check Mode", 113:"Gen Run Mode" })[Number(str(code))] || str(code);
  function solaxNow(){
    connNote("Solax");
    const r = ((CONN.solax || {}).result) || {}, n = solaxNum;
    const soc = n(r.soc);
    const out = { ac_power_w:n(r.acpower),
      yield_today_kwh: n(r.yieldtoday) !== "" ? Math.round(n(r.yieldtoday) / 10 * 10) / 10 : "",
      yield_total_kwh: n(r.yieldtotal) !== "" ? Math.round(n(r.yieldtotal) / 10 * 10) / 10 : "",
      feedin_power_w:n(r.feedinpower),
      feedin_energy_kwh: n(r.feedinenergy) !== "" ? Math.round(n(r.feedinenergy) / 100 * 100) / 100 : "",
      import_energy_kwh: n(r.consumeenergy) !== "" ? Math.round(n(r.consumeenergy) / 100 * 100) / 100 : "",
      battery_soc_pct: soc === -1 ? "" : soc, status:solaxStatus(r.inverterStatus), upload_time:str(r.uploadTime || "") };
    addStep("Solax figures", { mono:true, text:Object.entries(out).filter(([, v]) => v !== "").map(([k, v]) => k + ": " + v).join("\n") }).done(tr("from {time}", { time:out.upload_time || "?" }), "ok");
    return out;
  }
