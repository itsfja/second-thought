  /* Powerwall on the page (#362): a sample Powerwall. Exported Python reads your own through the gateway's local
     API, and the reserve change always asks. Matches the runtime's powerwall_ methods and tests/fake_powerwall.py. */
  const pwSample = () => { connNote("Powerwall"); return CONN.powerwall || {}; };
  const pwNum = v => { const m = /-?\d+(?:\.\d+)?/.exec(str(v)); return m ? Number(m[0]) : ""; };
  const pwGrid = { SystemGridConnected:"connected", SystemConnectedToGrid:"connected", SystemIslandedActive:"islanded (power cut)", SystemTransitionToIsland:"transitioning" };
  function powerwallNow(){
    const s = pwSample(), meter = name => pwNum(((s.meters_aggregates || {})[name] || {}).instant_power);
    const out = { battery_soc_pct:pwNum((s.system_status_soe || {}).percentage), solar_power_w:meter("solar"),
      battery_power_w:meter("battery"), grid_power_w:meter("site"), load_power_w:meter("load"),
      reserve_pct:pwNum((s.operation || {}).backup_reserve_percent), mode:str((s.operation || {}).real_mode || ""),
      grid:pwGrid[str((s.system_status_grid_status || {}).grid_status)] || str((s.system_status_grid_status || {}).grid_status) };
    addStep("Powerwall figures", { mono:true, text:Object.entries(out).filter(([, v]) => v !== "").map(([k, v]) => k + ": " + v).join("\n") }).done(tr("battery at {pct}%", { pct:out.battery_soc_pct }), "ok");
    return out;
  }
  async function powerwallReserve(percent){
    const n = Math.max(0, Math.min(100, Math.round(num(percent))));
    const old = pwNum(((pwSample().operation) || {}).backup_reserve_percent);
    const what = tr("set the Powerwall backup reserve to {n}% (now {old}%)", { n, old });
    if (!(await confirmAction(what + " (it always asks)"))) return false;
    addStep("Powerwall", { mono:true, text:what }).done(tr("done"), "ok");
    return true;
  }
