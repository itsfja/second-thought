  // 05-home-assistant.js: Home Assistant on the page: the sample house, its blocks' behaviour and the safety rules (SAFETY, copied in by tools/sync.py).
  /* ---------- Home Assistant ---------- */
  /* In the page these blocks talk to a built-in sample house; exported Python talks to your real Home Assistant. */
  const HA = { sample:null, states:new Map() };
  (function haLoad(){
    try { HA.sample = JSON.parse(document.getElementById("ha-sample").textContent); }
    catch(e) { HA.sample = { entities:[], cameras:{} }; }
    HA.sample.entities.forEach(e => HA.states.set(e.entity_id, JSON.parse(JSON.stringify(e))));
  })();
  const HA_HUE = "#2C7FB8";
  defineBlocks([
    { type:"rb_ha_when", message0:"when %1 changes to %2", args0:[{ type:"field_input", name:"ENTITY", text:"binary_sensor.doorbell" }, { type:"field_input", name:"STATE", text:"on" }],
      nextStatement:null, style:"ha_hat", tooltip:"Runs the blocks below when this entity changes. Type 'anything' to react to any change. Inside, 'what changed' says what happened." },
    { type:"rb_ha_event_when", message0:"when Home Assistant event %1 happens with %2", args0:[{ type:"field_input", name:"EVENT", text:"zha_event" }, { type:"field_input", name:"DATA", text:"" }],
      nextStatement:null, style:"ha_hat",
      tooltip:"Runs the blocks below the moment Home Assistant sends this event: a button or remote press (zha_event, deconz_event), an automation firing (automation_triggered), a phone notification action, or your own event. Type 'anything' for every event. The second box is optional words the event's data must contain, such as the remote's name. 'What arrived' gives event_type, entity, data, time and text, plus each field of the event's data. On this page, right-click it and choose 'Run this script' to try it with a sample event." },
    { type:"rb_ha_state", message0:"state of %1", args0:[{ type:"input_value", name:"ENTITY" }], output:null, style:"ha", inputsInline:true,
      tooltip:"The entity's current state, for example 'on', 'locked' or 19.5." },
    { type:"rb_ha_attr", message0:"%1 of entity %2", args0:[{ type:"input_value", name:"ATTR" }, { type:"input_value", name:"ENTITY" }], output:null, style:"ha", inputsInline:true,
      tooltip:"One attribute of an entity, for example 'current_temperature' or 'friendly_name'." },
    { type:"rb_ha_find", message0:"entities matching %1", args0:[{ type:"input_value", name:"TEXT" }], output:"Array", style:"ha", inputsInline:true,
      tooltip:"A list of records (entity, name, state, unit, area) for every entity whose id, name, area or state contains all these words. '*' means everything." },
    { type:"rb_ha_summary", message0:"readings for %1", args0:[{ type:"input_value", name:"TEXT" }], output:"String", style:"ha", inputsInline:true,
      tooltip:"A plain-text list of matching entities and their states, ready to put into a question for Claude." },
    { type:"rb_ha_history", message0:"history of %1 for the last %2 hours", args0:[{ type:"input_value", name:"ENTITY" }, { type:"input_value", name:"HOURS" }], output:"Array", style:"ha", inputsInline:true,
      tooltip:"A list of records (time, state) showing how the entity changed." },
    { type:"rb_ha_snapshot", message0:"snapshot from %1", args0:[{ type:"input_value", name:"CAMERA" }], output:"Picture", style:"ha", inputsInline:true,
      tooltip:"A picture from a camera entity. Use it with the Pictures blocks." },
    { type:"rb_ha_trigger", message0:"what changed", output:"Record", style:"ha", tooltip:"In a 'when … changes' script: a record with entity, name, from and to." },
    { type:"rb_ha_call", message0:"call %1 on %2 with %3", args0:[{ type:"input_value", name:"SERVICE" }, { type:"input_value", name:"ENTITY" }, { type:"input_value", name:"DATA" }],
      previousStatement:null, nextStatement:null, style:"ha", inputsInline:true,
      tooltip:"Calls a service, for example light.turn_off. Optional data is JSON like {\"temperature\": 20}. Unlocking, opening and disarming always ask you first." },
    { type:"rb_ha_notify", message0:"notify %1 : %2", args0:[{ type:"input_value", name:"TARGET" }, { type:"input_value", name:"TEXT" }],
      previousStatement:null, nextStatement:null, style:"ha", inputsInline:true,
      tooltip:"Sends a notification. Target is a notify service such as notify.mobile_app_my_phone, or persistent_notification for the Home Assistant sidebar." },
    { type:"rb_ha_speak", message0:"say %1 on %2", args0:[{ type:"input_value", name:"TEXT" }, { type:"input_value", name:"PLAYER" }],
      previousStatement:null, nextStatement:null, style:"ha", inputsInline:true, tooltip:"Speaks the text on a media player, using Home Assistant's text-to-speech." }
  ]);
  /* What always asks: SAFETY in python/second_thought/core.py, copied into the page by tools/sync.py, so the page and
     exported programs ask before the same things. Home Assistant actions that unlock, open or disarm ask even with
     'control devices (no asking)', and so do the things a fooled agent could do with a tool that doesn't normally ask. */
  const SAFETY = JSON.parse(document.getElementById("safety").textContent);
  const HA_SENSITIVE = SAFETY.ha_sensitive.map(p => new RegExp(p));
  const haIsSensitive = (svc, entity) => { svc = str(svc).trim();
    return HA_SENSITIVE.some(r => r.test(svc)) || (new RegExp(SAFETY.ha_generic).test(svc)
      && str(entity).trim().split(/[\s,]+/).some(e => new RegExp(SAFETY.ha_sensitive_entity).test(e))); };
  const AGENT_PRIVATE = new Set(SAFETY.agent_private);
  const AGENT_HA_INDIRECT = SAFETY.agent_ha_indirect.map(p => new RegExp(p));
  function agentMustAsk(tool, inp, seen, isPrivate){
    if (tool === "call_service" && AGENT_HA_INDIRECT.some(r => r.test(str(inp.service).trim()))) return "scripts, scenes, automations and buttons always ask, since they could do anything";
    if (tool === "run_homey_flow") return "flows always ask, since they could do anything";
    if (tool === "publish_mqtt" && new RegExp(SAFETY.mqtt_unlock, "i").test(str(inp.topic) + " " + str(inp.message))) return "unlocking, opening and disarming always ask";
    const url = str(inp.url || "").trim();
    if ((tool === "read_page" || tool === "read_feed") && url && isPrivate && !seen.includes(url) && !seen.includes(url.replace(/\/+$/, "")))
      return "the agent made this address up, and it can see private things that an address could carry away";
    return "";
  }
  // For the tests: the page's answers to the same questions the runtime answers (tests/e2e/safety.py).
  window.__safety = cases => cases.map(c => c.kind === "ha" ? haIsSensitive(c.service, c.entity)
    : c.kind === "homey" ? HOMEY_SENSITIVE.some(([cap, v]) => cap === c.capability && v === c.value)
    : c.kind === "asks" ? AGENT_ASKS.has(c.tool) : c.kind === "private" ? AGENT_PRIVATE.has(c.tool)
    : agentMustAsk(c.tool, c.input || {}, c.seen || "", !!c.private));

  const haVal = v => isNumLike(v) ? num(v) : v;
  function haEnt(id){
    const e = HA.states.get(String(id == null ? "" : id).trim());
    if (!e) fail(tr("The sample house has no entity called “{id}”. Open the Home Assistant panel to see the ones it has.", { id:str(id).trim() }));
    return e;
  }
  function haRecord(e){ const a = e.attributes || {}; return { entity:e.entity_id, name:a.friendly_name || e.entity_id, state:haVal(e.state), unit:a.unit_of_measurement || "", area:a.area || "" }; }
  function haMatch(text){
    const words = str(text).toLowerCase().split(/[\s,]+/).filter(Boolean);
    return [...HA.states.values()].filter(e => {
      if (!words.length || words.includes("*")) return true;
      const a = e.attributes || {};
      const hay = [e.entity_id, a.friendly_name, a.area, e.state, a.device_class, a.unit_of_measurement].join(" ").toLowerCase();
      return words.every(w => hay.includes(w));
    }).slice(0, 150);
  }
  function haLine(e){
    const a = e.attributes || {};
    const extra = Object.keys(a).filter(k => !["friendly_name", "area", "unit_of_measurement", "device_class"].includes(k)).map(k => "; " + k.replace(/_/g, " ") + ": " + a[k]).join("");
    return (a.friendly_name || e.entity_id) + " (" + e.entity_id + "): " + e.state + (a.unit_of_measurement ? " " + a.unit_of_measurement : "") + (a.area ? " [" + a.area + "]" : "") + extra;
  }
  function haNote(){
    if (run.haNoted) return; run.haNoted = true;
    addStep("Home Assistant", { mono:true, text:tr("This page uses a sample house, so nothing real is read or switched. Export to Python to use your own Home Assistant.") }).done("sample", "warn");
  }
  function haHistory(e, hours){
    hours = Math.max(1, Math.min(168, num(hours) || 24));
    let seed = 0; for (const ch of e.entity_id) seed = (seed * 31 + ch.charCodeAt(0)) >>> 0;
    const rnd = () => { seed = (seed * 1103515245 + 12345) >>> 0; return seed / 4294967296; };
    const n = Math.min(24, Math.max(6, Math.round(hours))), now = Date.now(), out = [];
    const cur = e.state, numeric = isNumLike(cur);
    const label = t => { const d = new Date(t); return ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"][d.getDay()] + " " + pad2(d.getHours()) + ":" + pad2(d.getMinutes()); };
    const pair = { on:"off", off:"on", open:"closed", closed:"open", locked:"unlocked", unlocked:"locked", home:"not_home", not_home:"home" };
    for (let i = n; i >= 0; i--) {
      const t = now - i * hours * 3600000 / n;
      let v;
      if (numeric) { const b = num(cur), amp = Math.abs(b) * 0.08 + 0.5; v = i === 0 ? b : Math.round((b + amp * Math.sin(i * 0.7 + rnd() * 2)) * 10) / 10; }
      else v = i === 0 || !pair[cur] ? cur : (rnd() < 0.25 ? pair[cur] : cur);
      if (!out.length || out[out.length - 1].state !== v || numeric) out.push({ time:label(t), state:v });
    }
    return out;
  }
  function haApply(svc, e, data){
    const [domain, action] = svc.split(".");
    const set = v => { e.state = v; };
    if (/^(light|switch|fan|input_boolean|media_player)$/.test(domain)) {
      if (action === "turn_on") set("on"); else if (action === "turn_off") set("off"); else if (action === "toggle") set(e.state === "on" ? "off" : "on");
    } else if (domain === "lock") { if (action === "lock") set("locked"); else if (action === "unlock" || action === "open") set("unlocked"); }
    else if (domain === "cover") { if (/^open/.test(action)) set("open"); else if (/^close/.test(action)) set("closed"); }
    else if (domain === "alarm_control_panel") { if (action === "alarm_disarm") set("disarmed"); else if (/^alarm_arm_/.test(action)) set("armed_" + action.slice(10)); }
    else if (domain === "climate") {
      if (action === "set_temperature" && data && data.temperature !== undefined) e.attributes.temperature = num(data.temperature);
      if (action === "turn_off") set("off"); if (action === "turn_on") set("heat");
      if (action === "set_hvac_mode" && data && data.hvac_mode) set(String(data.hvac_mode));
    }
  }
  function haChanged(id, from, to, byPerson){
    if (from === to) return;
    renderHaPanel();
    const hats = ws.getTopBlocks(false).filter(b => b.type === "rb_ha_when" && (!b.isEnabled || b.isEnabled()) && b.getNextBlock() &&
      String(b.getFieldValue("ENTITY") || "").trim() === id &&
      ["", "anything"].concat([String(to).toLowerCase()]).includes(String(b.getFieldValue("STATE") || "").trim().toLowerCase()));
    if (!hats.length) return;
    if (!byPerson && !(run && run.active)) return;
    const e = HA.states.get(id);
    hats.forEach(b => fire(b, { entity:id, name:(e && e.attributes.friendly_name) || id, from:haVal(from), to:haVal(to) }));
  }
  async function haCall(svc, id, dataText, tc){
    svc = str(svc).trim(); id = str(id).trim();
    if (!/^[a-z_]+\.[a-z0-9_]+$/.test(svc)) fail(tr("“{svc}” isn't a service name. Use domain.service, for example light.turn_off.", { svc }));
    let data = {};
    const dt = str(dataText).trim();
    if (dt) { try { data = JSON.parse(dt); } catch(e) { fail(tr("The data for {svc} isn't valid JSON. Use something like {\"temperature\": 20}.", { svc })); } }
    const e = id ? haEnt(id) : null;
    if (!haIsSensitive(svc, id) && !(await allowed(["ha"], svc.replace(".", ": ").replace(/_/g, " ") + (id ? " on " + id : "")))) return false;
    if (haIsSensitive(svc, id)) {
      const ok = await waitForYou("Allow this?", tr(id ? "The program wants to {action} on {entity}. This is a safety check: unlocking, opening and disarming always ask first." : "The program wants to {action}. This is a safety check: unlocking, opening and disarming always ask first.", { action:svc.replace(".", ": ").replace(/_/g, " "), entity:id }), (box, done) => {
        const row = document.createElement("div"); row.className = "row";
        const yes = document.createElement("button"); yes.type = "button"; yes.className = "primary"; yes.textContent = tr("Allow");
        const no = document.createElement("button"); no.type = "button"; no.textContent = tr("Don't");
        yes.onclick = () => done(true, "allowed"); no.onclick = () => done(false, "refused");
        row.append(yes, no); box.appendChild(row);
      });
      if (!ok) { addStep("Not done", { mono:true, text:tr(id ? "{service} on {entity} was refused, so nothing happened." : "{service} was refused, so nothing happened.", { service:svc, entity:id }) }).done("refused", "warn"); return false; }
    }
    haNote();
    const before = e ? e.state : null;
    if (e) haApply(svc, e, data);
    addStep(tr("Home Assistant: {service}", { service:svc }), { mono:true, text:(id || tr("(no entity)")) + (dt ? " " + tr("with {data}", { data:dt }) : "") + (e && e.state !== before ? "\n" + before + " → " + e.state : "") }).done("sample house", "ok");
    if (e && e.state !== before) haChanged(id, before, e.state, false);
    return true;
  }
  async function haValue(b, tc){
    haNote();
    switch (b.type) {
      case "rb_ha_state": return haVal(haEnt(await input(b, tc, "ENTITY")).state);
      case "rb_ha_attr": {
        const a = str(await input(b, tc, "ATTR")).trim(), e = haEnt(await input(b, tc, "ENTITY"));
        return a in e.attributes ? haVal(e.attributes[a]) : (a === "state" ? haVal(e.state) : "");
      }
      case "rb_ha_find": return haMatch(await input(b, tc, "TEXT")).map(haRecord);
      case "rb_ha_summary": { const m = haMatch(await input(b, tc, "TEXT")); return m.length ? m.map(haLine).join("\n") : "(no matching entities)"; }
      case "rb_ha_history": return haHistory(haEnt(await input(b, tc, "ENTITY")), await input(b, tc, "HOURS", 24));
      case "rb_ha_snapshot": {
        const id = str(await input(b, tc, "CAMERA")).trim();
        const svg = HA.sample.cameras[id];
        if (!svg) fail(tr("The sample house has no camera called “{id}”. Try camera.front_door, camera.driveway, camera.garden, camera.garage or camera.pet.", { id }));
        const pic = await svgImage(cleanSvg(svg), id.replace("camera.", "") + "-snapshot");
        const st = addStep(tr("Snapshot: {entity}", { entity:id }), { text:"" }); showPictureIn(st, pic); st.done("sample house", "ok");
        return pic;
      }
      case "rb_ha_trigger": return tc.payload && typeof tc.payload === "object" ? tc.payload : { entity:"", name:"", from:"", to:"" };
    }
  }
  /* Home Assistant panel: shows the sample house and lets you change it to try 'when … changes' scripts. */
  function renderHaPanel(){
    const list = document.getElementById("ha-list");
    if (!list || document.getElementById("ha").hidden) return;
    const q = (document.getElementById("ha-filter").value || "").trim();
    const items = haMatch(q || "*");
    list.innerHTML = "";
    items.forEach(e => {
      const row = document.createElement("div"); row.className = "ha-row";
      const n = document.createElement("div"); n.className = "mem-name"; n.textContent = e.attributes.friendly_name || e.entity_id;
      const id = document.createElement("div"); id.className = "mem-val"; id.textContent = e.entity_id + (e.attributes.area ? " · " + e.attributes.area : "");
      const inp = document.createElement("input"); inp.type = "text"; inp.value = e.state; inp.setAttribute("aria-label", "State of " + e.entity_id); inp.className = "ha-state";
      const apply = () => { const before = e.state, v = inp.value.trim(); if (!v || v === before) return; e.state = v; haChanged(e.entity_id, before, v, true); };
      inp.addEventListener("change", apply);
      inp.addEventListener("keydown", ev => { if (ev.key === "Enter") { ev.preventDefault(); apply(); } });
      row.append(n, id, inp); list.appendChild(row);
    });
  }
  function toggleHaPanel(){
    const el = document.getElementById("ha"), open = el.hidden;
    el.hidden = !open; document.getElementById("ha-toggle").setAttribute("aria-expanded", String(open));
    if (open) renderHaPanel();
    setTimeout(() => Blockly.svgResize(ws), 0);
  }

