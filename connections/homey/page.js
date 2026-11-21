  /* Homey on the page: a sample home. Exported Python talks to your Homey Pro. Matches the runtime's wording. */
  const HOMEY = { devices:null };
  function homeyHome(){
    connNote("Homey");
    const h = CONN.homey || { zones:{}, devices:[] };
    if (!HOMEY.devices) HOMEY.devices = JSON.parse(JSON.stringify(h.devices || []));
    return HOMEY.devices.map(d => ({ id:d.id, name:d.name, zone:(h.zones || {})[d.zone] || "", class:d.class,
      caps:Object.fromEntries(Object.entries(d.capabilitiesObj || {}).map(([k, c]) => [k, c.value])) }))
      .sort((a, b) => (a.zone + "\u0000" + a.name).localeCompare(b.zone + "\u0000" + b.name));
  }
  const homeyShow = v => v === true ? "on" : v === false ? "off" : v == null ? "-" : str(v);
  const homeyLine = d => d.name + " (" + (d.zone || "no zone") + ", " + d.class + "): " + Object.entries(d.caps).map(([k, v]) => k + "=" + homeyShow(v)).join(", ");
  function homeyDevice(name){
    name = str(name).trim();
    if (!name) fail(tr("Which Homey device? Give its name, like Kitchen light."));
    const home = homeyHome(), exact = home.filter(d => d.name.toLowerCase() === name.toLowerCase() || d.id === name);
    if (exact.length) return exact[0];
    const some = home.filter(d => name.toLowerCase().split(/\s+/).every(w => d.name.toLowerCase().includes(w)));
    if (some.length === 1) return some[0];
    fail(tr("There's no Homey device called “{name}”.", { name }) + (some.length ? " " + tr("Did you mean: {names}?", { names:some.slice(0, 6).map(d => d.name).join(", ") }) : ""));
  }
  const homeyMatch = text => { const words = str(text).toLowerCase().split(/\s+/).filter(w => w && w !== "*");
    return homeyHome().filter(d => words.every(w => (d.name + " " + d.zone + " " + d.class).toLowerCase().includes(w))); };
  const homeyFindText = text => homeyMatch(text).map(homeyLine).join("\n") || "No Homey devices match “" + str(text).trim() + "”.";
  const homeyFind = text => homeyMatch(text).map(d => Object.assign({ name:d.name, zone:d.zone, class:d.class },
    Object.fromEntries(Object.entries(d.caps).map(([k, v]) => [k, typeof v === "boolean" ? homeyShow(v) : v]))));
  function homeyValue(cap, device){
    const d = homeyDevice(device); cap = str(cap).trim();
    if (!(cap in d.caps)) fail(tr("{device} has no “{cap}”. It has: {caps}.", { device:d.name, cap, caps:Object.keys(d.caps).join(", ") || tr("nothing") }));
    const v = d.caps[cap]; return typeof v === "boolean" ? homeyShow(v) : v;
  }
  function homeyValueFor(old, value){
    const words = ["on", "off", "true", "false", "yes", "no", "1", "0"];
    if (typeof old === "boolean" || (typeof value === "string" && words.slice(0, 6).includes(value.trim().toLowerCase()))) {
      if (typeof value === "string") { const t = value.trim().toLowerCase(); if (!words.includes(t)) fail(tr("“{value}” isn't on or off.", { value })); return ["on", "true", "yes", "1"].includes(t); }
      return !!value;
    }
    if (typeof old === "number") { if (!isNumLike(value)) fail(tr("“{value}” isn't a number.", { value })); return num(value); }
    return typeof value === "number" || typeof value === "boolean" ? value : str(value);
  }
  const HOMEY_SENSITIVE = SAFETY.homey_sensitive;  // unlocking, opening and disarming
  async function homeySet(device, cap, value, approved){
    const d = homeyDevice(device); cap = str(cap).trim();
    if (!(cap in d.caps)) fail(tr("{device} has no “{cap}”. It has: {caps}.", { device:d.name, cap, caps:Object.keys(d.caps).join(", ") || tr("nothing") }));
    const v = homeyValueFor(d.caps[cap], value), what = "set " + d.name + " " + cap + " to " + homeyShow(v);
    // Unlocking, opening and disarming always ask, unless you've just said yes to this very change.
    if (HOMEY_SENSITIVE.some(([c, x]) => c === cap && x === v)) { if (!approved && !(await confirmAction(what + " (a safety check: unlocking, opening and disarming always ask)"))) return false; }
    else if (!approved && !(await allowed(["ha"], what))) return false;
    HOMEY.devices.find(x => x.id === d.id).capabilitiesObj[cap].value = v;
    addStep("Homey: " + d.name, { mono:true, text:cap + ": " + homeyShow(d.caps[cap]) + " → " + homeyShow(v) }).done("sample home", "ok");
    return true;
  }
  const homeyFlows = () => { homeyHome(); return ((CONN.homey || {}).flows || []).slice(); };
  const homeyFlowsText = () => homeyFlows().sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase())).map(f => f.name + (f.advanced ? " (advanced)" : "")).join("\n") || "No flows.";
  async function homeyRunFlow(name, approved){
    name = str(name).trim();
    const flows = homeyFlows(), some = flows.filter(x => x.name.toLowerCase().includes(name.toLowerCase()));
    const f = flows.find(x => x.name.toLowerCase() === name.toLowerCase()) || (some.length === 1 ? some[0] : null);
    if (!f) fail(tr("There's no Homey flow called “{name}”.", { name }));
    if (!approved && !(await allowed(["ha"], "start the Homey flow “" + f.name + "”"))) return false;
    addStep("Homey flow started", { mono:true, text:f.name }).done("sample home", "ok");
    return true;
  }
  function homeyVar(name){
    name = str(name).trim(); homeyHome();
    const vs = (CONN.homey || {}).variables || [], v = vs.find(x => x.name.toLowerCase() === name.toLowerCase());
    if (!v) fail(tr("There's no Homey variable called “{name}”.", { name }) + (vs.length ? " " + tr("Its variables are: {names}", { names:vs.slice(0, 12).map(x => x.name).join(", ") }) : ""));
    return v;
  }
  async function homeySetVariable(name, value, approved){
    const v = homeyVar(name), old = v.value, nv = ["boolean", "number"].includes(v.type) ? homeyValueFor(old, value) : str(value);
    if (!approved && !(await allowed(["ha"], "set the Homey variable “" + v.name + "” to " + homeyShow(nv)))) return false;
    v.value = nv;
    addStep(tr("Homey variable {name}", { name:v.name }), { mono:true, text:homeyShow(old) + " → " + homeyShow(nv) }).done("sample home", "ok");
    return true;
  }
