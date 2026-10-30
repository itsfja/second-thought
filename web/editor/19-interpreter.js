  // 19-interpreter.js: Running blocks: structured replies, asking you, values and statements, results.
  /* ---------- Structured replies ----------
     Each block that wants JSON names the shape it expects (the same shapes as SCHEMAS in the Python runtime).
     A reply that can't be read, or doesn't fit, is sent back once with the problem; a second miss stops the step. */
  const ANY = { anyOf:[{ type:"string" }, { type:"number" }, { type:"boolean" }] };
  const obj = (properties, required) => ({ type:"object", properties, required:required || [], additionalProperties:false });
  const SCHEMAS = {
    yesno:obj({ answer:{ type:"boolean" } }, ["answer"]),
    number:obj({ number:{ type:"number" } }, ["number"]),
    list:obj({ items:{ type:"array", items:{ type:"string" } } }, ["items"]),
    score:obj({ score:{ type:"number" } }, ["score"]),
    pick:obj({ pick:{ type:"integer", enum:[1, 2] }, reason:{ type:"string" } }, ["pick"]),
    review:obj({ approved:{ type:"boolean" }, problems:{ type:"array", items:{ type:"string" } } }, ["approved"]),
    agent:obj({ tool:{ type:"string" }, input:{ type:"object" }, why:{ type:"string" }, done:{ type:"boolean" }, answer:{ type:"string" },
                plan:{ type:"array", items:{ type:"string" } } })
  };
  function recordSchema(fields, many){
    const one = obj(Object.fromEntries(fields.map(f => [f, ANY])));
    return many ? obj({ items:{ type:"array", items:one } }, ["items"]) : one;
  }
  function shapeProblem(v, sc, where){
    where = where || "the reply";
    if (sc.anyOf) return sc.anyOf.some(o => !shapeProblem(v, o, where)) ? null : where + " has the wrong kind of value";
    const t = sc.type;
    if (t === "object") {
      if (!v || typeof v !== "object" || Array.isArray(v)) return where + " should be a JSON object";
      for (const k of sc.required || []) if (!(k in v)) return where + ' is missing "' + k + '"';
      for (const [k, sub] of Object.entries(sc.properties || {})) if (k in v) { const bad = shapeProblem(v[k], sub, '"' + k + '"'); if (bad) return bad; }
      return null;
    }
    if (t === "array") {
      if (!Array.isArray(v)) return where + " should be a list";
      for (let i = 0; i < v.length; i++) { const bad = shapeProblem(v[i], sc.items || {}, "item " + (i + 1) + " of " + where); if (bad) return bad; }
      return null;
    }
    if (t === "boolean" && typeof v !== "boolean") return where + " should be true or false";
    if ((t === "number" || t === "integer") && (typeof v === "boolean" || !isNumLike(v))) return where + " should be a number";
    if (t === "string" && typeof v !== "string") return where + " should be text";
    if (sc.enum && !sc.enum.includes(t === "number" || t === "integer" ? num(v) : v)) return where + " should be one of " + sc.enum.map(e => JSON.stringify(e)).join(", ");
    return null;
  }
  function fitShape(v, sc){
    const keys = Object.keys(sc.properties || {});
    if (Array.isArray(v) && keys.length === 1 && keys[0] === "items") return { items:v };
    if (Array.isArray(v) && v.length === 1 && v[0] && typeof v[0] === "object" && !Array.isArray(v[0]) && sc.type === "object") return v[0];
    return v;
  }
  /* send(prompt) makes the JSON call (so pictures can ride along); returns the reply, checked against the schema. */
  async function askChecked(send, prompt, schema){
    let v, raw = "", problem = null;
    try { v = await send(prompt); }
    catch(e) { if (!(e && e.code === "invalid_json")) throw e; raw = e.text || ""; problem = "it wasn't readable JSON"; }
    if (!problem) { v = fitShape(v, schema); problem = shapeProblem(v, schema); if (problem) raw = JSON.stringify(v); }
    if (!problem) return v;
    addStep("Unreadable reply", { mono:true, text:tr("The reply didn't have the expected shape: {problem}.\nAsking once more for a corrected reply.", { problem }) }).done("repair", "warn");
    const again = prompt + "\n\nYour previous reply couldn't be used: the reply didn't have the expected shape: " + problem + ".\nPrevious reply:\n" + short(raw, 2000) +
      "\n\nReply again with only the corrected JSON.";
    try { v = await send(again); }
    catch(e) { if (e && e.code === "invalid_json") throw { code:"invalid_json", shape:true, message:"Claude's reply still couldn't be read after a second try. Run again, or put the block inside 'retry'." }; throw e; }
    v = fitShape(v, schema);
    const still = shapeProblem(v, schema);
    if (still) throw { code:"invalid_json", shape:true, message:"Claude's reply still didn't have the expected shape after a second try: " + still + ". Run again, or put the block inside 'retry'." };
    return v;
  }
  async function askJSON(label, prompt, show, schema){
    const s = addStep(label);
    const out = await askChecked(q => ask(q, s, "json"), prompt, schema);
    s.text(show(out)); s.done("done", "ok");
    return out;
  }

  /* Waits for the person in the log. render(resolve, reject) builds the controls. */
  // What the person answers during a run is kept (run.inputs), so a good run can become a test case; a test run
  // (run.replay) gives the same answers back instead of asking. Pictures aren't kept: they're too big.
  const INPUT_KINDS = { "Question for you":"answer", "Allow this?":"allow", "Do you approve this?":"approve", "Choose one":"choose",
    "Choose a file":"file", "Choose a picture":"picture", "Paused":"pause" };
  async function waitForYou(title, text, build){
    const kind = INPUT_KINDS[title];
    if (run && run.replay && kind) {
      if (kind === "picture") fail(tr("Test cases don't keep pictures, so a test can't choose one. Test this part by running the program."));
      if (kind === "pause") return true;
      const q = run.replay[kind] || [];
      if (!q.length) {
        if (kind === "allow") return true;
        fail(tr("The test case has no answer for this step ({what}). Save it again from a run that gets this far.", { what:short(String(text || tr(title)), 80) }));
      }
      const v = q.shift();
      addStep(tr("Test answer"), { text:(text ? text + "\n\n" : "") + (kind === "file" ? str(v && v.name) : str(v)) }).done(tr("replayed"), "ok");
      return v;
    }
    const v = await waitForYouLive(title, text, build);
    if (run && run.inputs && kind && kind !== "picture") {
      const keep = kind === "file" ? { name:v && v.name, text:v && v.text } : v;
      let size = 0; try { size = JSON.stringify(keep).length; } catch(e) { size = Infinity; }
      if (size < 200000) (run.inputs[kind] = run.inputs[kind] || []).push(keep);
      else run.inputsIncomplete = true;
    }
    return v;
  }
  function waitForYouLive(title, text, build){
    return new Promise((resolve, reject) => {
      const s = addStep(tr(title), { human:true, text });
      s.done("waiting for you", "warn");
      setStatus("waiting for you");
      const box = document.createElement("div"); box.className = "ask"; s.el.appendChild(box);
      const stopper = () => { run.stoppers.delete(stopper); box.remove(); s.done(run.stopped ? tr("stopped") : tr("ended"), run.stopped ? "bad" : "warn"); reject(new Halt()); };
      const finish = (v, label) => { run.stoppers.delete(stopper); box.remove(); s.done(label || tr("answered"), "ok"); if (!run.stoppers.size) setStatus("running"); resolve(v); };
      run.stoppers.add(stopper);
      build(box, finish, s);
      const f = box.querySelector("textarea,button"); if (f) f.focus();
    });
  }

  function fmtLeft(ms){
    const t = Math.max(0, Math.ceil(ms / 1000)), h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), sec = t % 60;
    return h ? h + "h " + m + "m" : m ? m + "m " + sec + "s" : sec + "s";
  }
  const pad2 = n => String(n).padStart(2, "0");
  const hhmm = d => pad2(d.getHours()) + ":" + pad2(d.getMinutes());
  async function sleepUntil(t, step, label){
    let last = 0;
    while (true) {
      if (halting()) throw new Halt();
      const left = t - Date.now();
      if (left <= 0) break;
      if (step && Date.now() - last >= 1000) { step.text(tr("{label} ({left} left)", { label, left:fmtLeft(left) })); last = Date.now(); }
      await new Promise(r => setTimeout(r, Math.min(500, left)));
    }
  }
  const AI_TYPES = new Set(["rb_ask","rb_ask_yesno","rb_ask_number","rb_ask_list","rb_rewrite","rb_extract","rb_score","rb_better","procedures_callreturn"]);
  const usesClaude = b => b.getDescendants(false).some(d => AI_TYPES.has(d.type));
  function checkStuck(){
    setTimeout(() => {
      if (!run || !run.active || run.ending || sched.armed) return;
      if (run.msgWaiting > 0 && run.msgWaiting >= run.threads.size) {
        const names = [...run.msgNames.values()].map(n => "\u201c" + n + "\u201d").join(", ");
        run.ending = true;
        run.error = { code:"user", message:"Every script is waiting for " + names + ", but nothing running can send it. Add a broadcast for it, or turn Schedules on if a scheduled script sends it." };
        endAll();
      }
    }, 50);
  }

  function varId(block){ return block.getFieldValue("VAR"); }
  function getVar(id){ return run.vars.has(id) ? run.vars.get(id) : 0; }

  async function input(block, tc, name, dflt){
    const t = block.getInputTargetBlock(name);
    if (!t) return dflt === undefined ? "" : dflt;
    return evalv(t, tc);
  }

  async function evalv(b, tc){
    await tick();
    switch (b.type) {
      case "math_number": return num(b.getFieldValue("NUM"));
      case "text": return b.getFieldValue("TEXT");
      case "rb_longtext": return b.getFieldValue("TEXT");
      case "logic_boolean": return b.getFieldValue("BOOL") === "TRUE";
      case "variables_get": return getVar(varId(b));
      case "logic_negate": return !bool(await input(b, tc, "BOOL", false));
      case "logic_operation": {
        const op = b.getFieldValue("OP"), a = bool(await input(b, tc, "A", false));
        if (op === "AND") return a ? bool(await input(b, tc, "B", false)) : false;
        return a ? true : bool(await input(b, tc, "B", false));
      }
      case "logic_compare": {
        const a = await input(b, tc, "A"), c = await input(b, tc, "B"), op = b.getFieldValue("OP");
        let x = a, y = c;
        if (isNumLike(a) && isNumLike(c)) { x = num(a); y = num(c); }
        else { x = str(a).toLowerCase(); y = str(c).toLowerCase(); }
        return { EQ:x === y, NEQ:x !== y, LT:x < y, LTE:x <= y, GT:x > y, GTE:x >= y }[op];
      }
      case "logic_ternary": return bool(await input(b, tc, "IF", false)) ? input(b, tc, "THEN") : input(b, tc, "ELSE");
      case "math_arithmetic": {
        const a = num(await input(b, tc, "A", 0)), c = num(await input(b, tc, "B", 0));
        return { ADD:a + c, MINUS:a - c, MULTIPLY:a * c, DIVIDE:c === 0 ? fail(tr("Can't divide by zero.")) : a / c, POWER:Math.pow(a, c) }[b.getFieldValue("OP")];
      }
      case "math_random_int": {
        let a = Math.round(num(await input(b, tc, "FROM", 1))), c = Math.round(num(await input(b, tc, "TO", 10)));
        if (a > c) [a, c] = [c, a];
        return a + Math.floor(Math.random() * (c - a + 1));
      }
      case "math_round": {
        const n = num(await input(b, tc, "NUM", 0));
        return { ROUND:Math.round(n), ROUNDUP:Math.ceil(n), ROUNDDOWN:Math.floor(n) }[b.getFieldValue("OP")];
      }
      case "math_modulo": { const d = num(await input(b, tc, "DIVISOR", 1)); if (d === 0) fail(tr("Can't divide by zero.")); return num(await input(b, tc, "DIVIDEND", 0)) % d; }
      case "text_join": {
        let out = ""; for (let i = 0; i < (b.itemCount_ || 0); i++) out += str(await input(b, tc, "ADD" + i));
        return out;
      }
      case "text_length": { const v = await input(b, tc, "VALUE"); return Array.isArray(v) ? v.length : str(v).length; }
      case "text_isEmpty": return str(await input(b, tc, "VALUE")).length === 0;
      case "text_changeCase": {
        const t = str(await input(b, tc, "TEXT")), m = b.getFieldValue("CASE");
        return m === "UPPERCASE" ? t.toUpperCase() : m === "LOWERCASE" ? t.toLowerCase() : t.replace(/\S+/g, w => w[0].toUpperCase() + w.slice(1).toLowerCase());
      }
      case "rb_contains": return str(await input(b, tc, "A")).toLowerCase().includes(str(await input(b, tc, "B")).toLowerCase());
      case "rb_word_count": { const t = str(await input(b, tc, "TEXT")).trim(); return t ? t.split(/\s+/).length : 0; }
      case "lists_create_empty": return [];
      case "lists_create_with": { const out = []; for (let i = 0; i < (b.itemCount_ || 0); i++) { const t = b.getInputTargetBlock("ADD" + i); if (t) out.push(await evalv(t, tc)); } return out; }
      case "lists_length": return list(await input(b, tc, "VALUE", [])).length;
      case "lists_isEmpty": return list(await input(b, tc, "VALUE", [])).length === 0;
      case "lists_getIndex": return listGet(b, tc);
      case "procedures_callreturn": return callProc(b, tc);
      /* Draft */
      case "rb_draft": return run.draft;
      case "rb_task_get": return run.task;
      /* Ask Claude */
      case "rb_ask": {
        const p = str(await input(b, tc, "TEXT")); if (!p.trim()) fail(tr("An 'ask Claude' block is empty. Type a question into it."));
        return askStep(tr("Ask Claude: {request}", { request:short(p, 60) }), "Answer the request below. Reply with only the answer, no preamble.\n\n" + p);
      }
      case "rb_ask_yesno": {
        const p = str(await input(b, tc, "TEXT")); if (!p.trim()) fail(tr("A yes/no block is empty."));
        const r = await askJSON(tr("Yes or no: {question}", { question:short(p, 60) }), 'Answer the question. Reply with only JSON: {"answer": true} or {"answer": false}.\n\nQuestion:\n' + p, o => o.answer === true ? "Yes" : "No", SCHEMAS.yesno);
        return r.answer === true;
      }
      case "rb_ask_number": {
        const p = str(await input(b, tc, "TEXT")); if (!p.trim()) fail(tr("An 'ask for a number' block is empty."));
        const r = await askJSON(tr("Number: {request}", { request:short(p, 60) }), 'Reply with only JSON: {"number": <a single number>}.\n\nRequest:\n' + p, o => String(num(o.number)), SCHEMAS.number);
        return num(r.number);
      }
      case "rb_ask_list": {
        const p = str(await input(b, tc, "TEXT")); if (!p.trim()) fail(tr("An 'ask for a list' block is empty."));
        const s = addStep(tr("List: {request}", { request:short(p, 60) }));
        const r = await askChecked(q => ask(q, s, "json"), 'Reply with only JSON: {"items": [<short strings>]}, no other text.\n\nRequest:\n' + p, SCHEMAS.list);
        const items = r.items.map(str).filter(Boolean);
        s.list(items.length ? items : ["(empty list)"]); s.done(tr("{n} items", { n:items.length }), "ok");
        return items;
      }
      case "rb_rewrite": {
        const t = str(await input(b, tc, "TEXT")), how = str(await input(b, tc, "HOW"));
        if (!t.trim()) fail(tr("A 'rewrite' block has nothing to rewrite."));
        return askStep(tr("Rewrite: {how}", { how:short(how, 60) }), "Rewrite the text below. Instruction: " + how + "\nReply with only the rewritten text.\n\nText:\n" + t);
      }
      case "rb_extract": {
        const what = str(await input(b, tc, "WHAT")), t = str(await input(b, tc, "TEXT"));
        if (!t.trim()) fail(tr("An 'extract' block has no text to read."));
        return askStep(tr("Extract: {what}", { what:short(what, 60) }), "From the text below, extract: " + what + "\nReply with only what you extracted, nothing else.\n\nText:\n" + t);
      }
      /* Review */
      case "rb_passed": return run.approved === true;
      case "rb_problems": return run.problems.slice();
      case "rb_score": {
        const t = str(await input(b, tc, "TEXT")), c = str(await input(b, tc, "CRITERIA"));
        const r = await askJSON(tr("Score: {text}", { text:short(t, 50) }), 'Score the text from 1 to 10 against these criteria: ' + c +
          '\nBe strict and consistent. Reply with only JSON: {"score": <1-10>}.\n\nText:\n' + t, o => num(o.score) + "/10", SCHEMAS.score);
        return Math.max(0, Math.min(10, num(r.score)));
      }
      case "rb_better": {
        const a = str(await input(b, tc, "A")), c = str(await input(b, tc, "B")), cr = str(await input(b, tc, "CRITERIA"));
        const r = await askJSON("Pick the better one", 'Which text is better for: ' + cr + '?\nReply with only JSON: {"pick": 1 or 2, "reason": "<one sentence>"}.\n\nText 1:\n' + a + "\n\nText 2:\n" + c,
          o => "Picked " + (num(o.pick) === 2 ? "the second" : "the first") + (o.reason ? ". " + o.reason : ""), SCHEMAS.pick);
        return num(r.pick) === 2 ? c : a;
      }
      /* You */
      case "rb_answer": return run.answer;
      case "rb_msg_value": return tc.payload;
      case "rb_ha_state": case "rb_ha_attr": case "rb_ha_find": case "rb_ha_summary":
      case "rb_ha_history": case "rb_ha_snapshot": case "rb_ha_trigger": return haValue(b, tc);
      case "rb_event": {
        const key = str(b.getFieldValue("KEY")).trim(), v = tc.payload;
        if (!v || typeof v !== "object" || Array.isArray(v)) return ["", "text", "all"].includes(key) ? (v == null ? "" : v) : "";
        return key === "" || key === "all" ? Object.assign({}, v) : (key in v ? v[key] : "");
      }
      case "rb_homey_value": return homeyValue(await input(b, tc, "CAPABILITY"), await input(b, tc, "DEVICE"));
      case "rb_homey_find": {
        const t = str(await input(b, tc, "TEXT", "*")) || "*", recs = homeyFind(t);
        addStep("Homey: " + short(t, 50), { mono:true, text:homeyMatch(t).map(homeyLine).join("\n") || tr("(nothing)") }).done(tr("{n} devices", { n:recs.length }), "ok");
        return recs;
      }
      case "rb_homey_variable": return homeyVar(await input(b, tc, "NAME")).value;
      case "rb_mqtt_read": {
        const topic = mqttTopic(await input(b, tc, "TOPIC")), got = mqttRead(topic);
        if (!/[+#]/.test(topic)) { const v = got[topic] || ""; addStep("MQTT " + topic, { mono:true, text:v || tr("(no message yet: only messages the broker keeps show up straight away)") }).done("read", "ok"); return v; }
        addStep("MQTT " + topic, { mono:true, text:Object.keys(got).sort().map(k => k + ": " + short(got[k], 80)).join("\n") || tr("(nothing)") }).done(tr("{n} topics", { n:Object.keys(got).length }), "ok");
        return got;
      }
      case "rb_tg_message": {
        const m = tc.payload && typeof tc.payload === "object" && "text" in tc.payload ? tc.payload : null;
        if (!m) return "";
        return { text:m.text, sender:m.sender || "", chat:m.chat || "" }[b.getFieldValue("PART") || "text"];
      }
      case "rb_feed_news": {
        const url = str(await input(b, tc, "URL")).trim();
        const items = sampleFeedItems(url, 10);
        const recs = items.map(i => ({ feed:i.feed, title:i.title, link:i.link, date:whenText(i.date), summary:i.summary }));
        addStep(tr("News: {feed}", { feed:short(url, 60) || tr("your feeds") }), { mono:true, text:recs.slice(0, 12).map(r => r.date + "  " + r.title).join("\n") || tr("(nothing)") }).done(tr("{n} items", { n:recs.length }), "ok");
        return recs;
      }
      case "rb_calendar": {
        const days = Math.max(1, Math.min(62, Math.floor(num(await input(b, tc, "DAYS", 7)) + 0.5) || 7)), start = parseDay("today");
        const recs = sampleEvents(start, new Date(start.getTime() + days * 86400000)).map(e => ({ day:dayText(e.start), start:e.all_day ? "" : pad2(e.start.getHours()) + ":" + pad2(e.start.getMinutes()),
          end:e.all_day ? "" : pad2(e.end.getHours()) + ":" + pad2(e.end.getMinutes()), title:e.title, location:e.location }));
        addStep("Calendar", { mono:true, text:recs.map(r => r.day + " " + (r.start || tr("all day")) + "  " + r.title).join("\n") || tr("(nothing)") }).done(tr("{n} events", { n:recs.length }), "ok");
        return recs;
      }
      case "rb_rec_new": return {};
      case "rb_rec_get": { const r = await input(b, tc, "REC"), k = str(await input(b, tc, "KEY")).trim(); if (!isRec(r)) fail(tr("'{k} of' needs a record in its second slot.", { k })); return k in r ? r[k] : ""; }
      case "rb_rec_has": { const r = await input(b, tc, "REC"), k = str(await input(b, tc, "KEY")).trim(); return isRec(r) && k in r; }
      case "rb_rec_keys": { const r = await input(b, tc, "REC"); return isRec(r) ? Object.keys(r) : []; }
      case "rb_ask_record":
      case "rb_ask_records": {
        const fields = fieldList(await input(b, tc, "FIELDS")), p = str(await input(b, tc, "TEXT")).trim();
        if (!fields.length) fail(tr("Give the record's fields, separated by commas."));
        if (!p) fail(tr("The 'ask Claude for a record' block has no request."));
        const many = b.type === "rb_ask_records";
        const shape = "{" + fields.map(f => JSON.stringify(f) + ": ...").join(", ") + "}";
        const s = addStep(tr(many ? "Records: {request}" : "Record: {request}", { request:short(p, 55) }));
        const r = await askChecked(q => ask(q, s, "json"), (many ? 'Reply with only JSON: {"items": [<objects, each shaped like ' + shape + '>]}' : "Reply with only one JSON object shaped like " + shape) +
          ". Use these exact field names. Numbers as numbers.\n\nRequest:\n" + p, recordSchema(fields, many));
        if (many) {
          const arr = r.items.map(o => toRecord(o, fields));
          s.text(arr.map(x => fields.map(f => f + ": " + short(str(x[f]), 40)).join(" \u00b7 ")).join("\n") || tr("(no records)")); s.done(tr("{n} records", { n:arr.length }), "ok");
          return arr;
        }
        const rec = toRecord(r, fields);
        s.text(str(rec)); s.done("done", "ok");
        return rec;
      }
      case "rb_sort": {
        const items = list(await input(b, tc, "LIST", [])).slice(), k = str(await input(b, tc, "KEY")).trim(), desc = b.getFieldValue("ORDER") !== "asc";
        const keyOf = it => k ? (isRec(it) ? it[k] : "") : it;
        items.sort((x, y) => {
          const a = keyOf(x), c = keyOf(y);
          const r = (isNumLike(a) && isNumLike(c)) ? num(a) - num(c) : str(a).toLowerCase().localeCompare(str(c).toLowerCase());
          return desc ? -r : r;
        });
        return items;
      }
      case "rb_chat": {
        const name = str(await input(b, tc, "NAME")).trim() || "chat", msg = str(await input(b, tc, "TEXT")).trim();
        if (!msg) fail(tr("The 'chat' block has no message."));
        const key = name.toLowerCase();
        const hist = run.chats.get(key) || [];
        const s = addStep(tr("Chat {name}: {message}", { name, message:short(msg, 50) }));
        const reply = await ask(hist.concat([{ role:"user", content:msg }]), s);
        hist.push({ role:"user", content:msg }, { role:"assistant", content:reply });
        while (hist.length > 40) hist.splice(0, 2);
        run.chats.set(key, hist);
        s.done(tr("turn {n}", { n:hist.length / 2 }), "ok");
        return reply;
      }
      case "rb_web_search": {
        const q = str(await input(b, tc, "TEXT")).trim();
        if (!q) fail(tr("The 'search the web' block is empty."));
        const s = addStep(tr("Search (from Claude's knowledge): {query}", { query:short(q, 45) }));
        const out = await ask("Answer this as if summarising a web search, from your own knowledge. You cannot browse, so say plainly when something may be out of date and give no made-up links.\n\nQuery: " + q, s);
        s.done("not live", "warn");
        return out;
      }
      case "rb_prompt": {
        const name = String(b.getFieldValue("NAME") || "").trim(), e = lib.prompt.get(name.toLowerCase());
        if (!e) fail(tr("There's no prompt called \u201c{name}\u201d in your prompt library. Open Programs to add it.", { name }));
        return e.text;
      }
      case "rb_file_choose": { const f = await chooseTextFile(); run.lastFile = f.name; return f.text; }
      case "rb_result_text": return finalText();
      case "rb_error": return run.lastError || "";
      case "rb_mem_get": { const e = memLive(memKey(str(await input(b, tc, "NAME")))); return e ? (Array.isArray(e.value) ? e.value.slice() : e.value) : ""; }
      case "rb_mem_has": return !!memLive(memKey(str(await input(b, tc, "NAME"))));
      case "rb_mem_names": {
        const now = Date.now(), names = [];
        mem.transient.forEach(e => names.push(e.name));
        mem.saved.forEach((e, k) => { if (!mem.transient.has(k) && !(e.expires && e.expires <= now)) names.push(e.name); });
        return names.sort();
      }
      case "rb_img_choose": {
        return choosePicture();
      }
      case "rb_img_draw": {
        const d = str(await input(b, tc, "TEXT")).trim();
        if (!d) fail(tr("The 'draw a picture' block has no description."));
        return drawSvg("Draw this as a single SVG illustration: " + d + "\n" + DRAW_RULES, tr("Draw: {what}", { what:short(d, 60) }));
      }
      case "rb_img_change": {
        const pic = needImg(await input(b, tc, "IMG"), "change picture");
        const how = str(await input(b, tc, "TEXT")).trim();
        if (!how) fail(tr("The 'change picture' block has no change in it."));
        if (pic.svg) return drawSvg("Here is an SVG illustration:\n" + pic.svg + "\n\nRedraw it with these changes: " + how + "\nKeep everything else the same. " + DRAW_RULES, tr("Change picture: {how}", { how:short(how, 60) }));
        return drawSvg("Draw a new SVG illustration of the attached picture, with these changes: " + how + "\n" + DRAW_RULES, tr("Redraw as illustration: {how}", { how:short(how, 50) }), pic);
      }
      case "rb_img_ask": {
        const q = str(await input(b, tc, "TEXT")).trim();
        const pic = needImg(await input(b, tc, "IMG"), "ask Claude about picture");
        if (!q) fail(tr("The 'ask Claude about picture' block has no question."));
        const s = addStep(tr("Look at picture: {question}", { question:short(q, 55) }));
        const out = await askWithPicture("Look at the attached picture and answer. Reply with only the answer, no preamble.\n\n" + q, pic, s);
        s.done("done", "ok");
        return out;
      }
      case "rb_img_score": {
        const pic = needImg(await input(b, tc, "IMG"), "score picture");
        const c = str(await input(b, tc, "CRITERIA"));
        const s = addStep(tr("Score picture: {criteria}", { criteria:short(c, 55) }));
        const r = await askChecked(q => askWithPicture(q, pic, s, "json"), "Score the attached picture from 1 to 10 against these criteria: " + c + '\nBe strict and consistent. Reply with only JSON: {"score": <1-10>}.', SCHEMAS.score);
        const n = Math.max(0, Math.min(10, num(r.score)));
        s.text(n + "/10"); s.done("done", "ok");
        return n;
      }
      case "rb_timer": return Math.round((Date.now() - run.timerStart) / 100) / 10;
      case "rb_now": {
        const d = new Date(), part = b.getFieldValue("PART");
        const date = d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate());
        return { time:hhmm(d), date, datetime:date + " " + hhmm(d), hour:d.getHours(), minute:d.getMinutes(),
                 weekday:["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"][d.getDay()] }[part];
      }
      case "rb_tokens_used": return tokensUsed();
      case "rb_setup_check": return tr("The setup check only runs in exported Python: export this program and run it there to see the report.");
      case "rb_folder_files": {
        const folder = str(await input(b, tc, "FOLDER", "")).trim() || "inbox", match = str(await input(b, tc, "MATCH", "")).trim() || "*";
        const re = new RegExp("^" + match.toLowerCase().replace(/[.+^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*").replace(/\?/g, ".") + "$");
        const two = n => String(n).padStart(2, "0"), stamp = d => d.getFullYear() + "-" + two(d.getMonth() + 1) + "-" + two(d.getDate()) + " " + two(d.getHours()) + ":" + two(d.getMinutes());
        return ((CONN.folder || {}).files || []).filter(f => re.test(f.name.toLowerCase())).sort((a, c) => a.days_ago - c.days_ago)
          .map(f => ({ name:f.name, path:folder + "/" + f.name, modified:stamp(new Date(Date.now() - f.days_ago * 86400000)), size:f.size }));
      }
      case "rb_agent_steps": return run.agentTrace.map(r => Object.assign({}, r));
      case "rb_run_program": return runProgram(b.getFieldValue("NAME"), await input(b, tc, "VALUE", ""), tc);
      case "rb_approve": {
        const t = str(await input(b, tc, "TEXT"));
        return waitForYou("Do you approve this?", t, (box, done) => {
          const row = document.createElement("div"); row.className = "row";
          const yes = document.createElement("button"); yes.type = "button"; yes.className = "primary"; yes.textContent = tr("Approve");
          const no = document.createElement("button"); no.type = "button"; no.textContent = tr("Send back");
          yes.onclick = () => done(true, "approved"); no.onclick = () => done(false, "sent back");
          row.append(yes, no); box.appendChild(row);
        });
      }
      case "rb_choose": {
        const items = list(await input(b, tc, "LIST", []));
        if (!items.length) fail(tr("'let me choose from' got an empty list."));
        return waitForYou("Choose one", "", (box, done) => {
          const row = document.createElement("div"); row.className = "row";
          items.forEach(it => { const btn = document.createElement("button"); btn.type = "button"; btn.textContent = short(it, 80); btn.onclick = () => done(it, "chosen"); row.appendChild(btn); });
          box.appendChild(row);
        });
      }
      default:
        fail(tr("The block '{type}' can't be used as a value here.", { type:b.type }));
    }
  }

  async function listGet(b, tc){
    const lst = list(await input(b, tc, "VALUE", []));
    const where = b.getFieldValue("WHERE"), mode = b.getFieldValue("MODE");
    let i;
    if (where === "FIRST") i = 0; else if (where === "LAST") i = lst.length - 1;
    else if (where === "RANDOM") i = Math.floor(Math.random() * lst.length);
    else if (where === "FROM_START") i = Math.round(num(await input(b, tc, "AT", 1))) - 1;
    else i = lst.length - Math.round(num(await input(b, tc, "AT", 1)));
    if (i < 0 || i >= lst.length) fail(tr("A list block asked for item {n} but the list has {length} items.", { n:(i + 1), length:lst.length }));
    const v = lst[i];
    if (mode !== "GET") {
      lst.splice(i, 1);
      const src = b.getInputTargetBlock("VALUE");
      if (src && src.type === "variables_get") run.vars.set(varId(src), lst);
    }
    return v;
  }
  async function listSet(b, tc){
    const src = b.getInputTargetBlock("LIST");
    let lst = list(await input(b, tc, "LIST", []));
    lst = lst.slice();
    const where = b.getFieldValue("WHERE"), mode = b.getFieldValue("MODE"), to = await input(b, tc, "TO");
    let i;
    if (where === "FIRST") i = 0; else if (where === "LAST") i = mode === "INSERT" ? lst.length : lst.length - 1;
    else if (where === "RANDOM") i = Math.floor(Math.random() * Math.max(1, lst.length));
    else if (where === "FROM_START") i = Math.round(num(await input(b, tc, "AT", 1))) - 1;
    else i = lst.length - Math.round(num(await input(b, tc, "AT", 1))) + (mode === "INSERT" ? 1 : 0);
    if (mode === "INSERT") lst.splice(Math.max(0, Math.min(i, lst.length)), 0, to);
    else { if (i < 0 || i >= lst.length) fail(tr("A list 'set' block points past the end of the list.")); lst[i] = to; }
    if (src && src.type === "variables_get") run.vars.set(varId(src), lst);
    else fail(tr("To change a list, put a list variable in the 'in list' slot."));
  }

  async function callProc(b, tc){
    const name = b.getProcedureCall();
    const def = Blockly.Procedures.getDefinition(name, b.workspace || ws);
    if (!def) fail(tr("There's no definition for the block '{name}'.", { name }));
    if (run.depth >= MAX_DEPTH) fail(tr("'{name}' called itself too many times.", { name }));
    const params = def.getVarModels ? def.getVarModels() : [];
    const args = [];
    for (let i = 0; i < params.length; i++) args.push(await input(b, tc, "ARG" + i));
    const saved = params.map(p => [p.getId(), run.vars.get(p.getId())]);
    params.forEach((p, i) => run.vars.set(p.getId(), args[i]));
    run.depth++;
    try {
      try { await runChain(def.getInputTargetBlock("STACK"), tc); }
      catch(e) { if (e instanceof ReturnSig) return e.value; throw e; }
      return def.getInput("RETURN") ? await input(def, tc, "RETURN") : undefined;
    } finally {
      run.depth--;
      saved.forEach(([id, v]) => v === undefined ? run.vars.delete(id) : run.vars.set(id, v));
    }
  }

  async function body(b, name, tc){
    try { await runChain(b.getInputTargetBlock(name), tc); return null; }
    catch(e) { if (e instanceof BreakSig) return "break"; if (e instanceof ContinueSig) return "continue"; throw e; }
  }
  const needTask = () => { if (!run.task) fail(tr("Add a 'set task to' block before this step.")); };
  const needDraft = () => { if (!run.draft) fail(tr("There's no draft yet. Put a 'write a first draft' or 'set draft to' block before this step.")); };

  async function reviewOnce(criteria, label, inLoop){
    const s = addStep(label);
    const loop = inLoop ? run.reflect : null;
    const earlier = loop && loop.earlier.length ? "\n\nEarlier rounds of this review found the problems below. Check each one is still fixed, and list it again if it has come back:\n" +
      loop.earlier.map(e => "- " + e).join("\n") : "";
    const v = await askChecked(q => ask(q, s, "json"), "You are a strict reviewer. Judge the draft ONLY against these criteria (separated by semicolons):\n" + criteria +
      "\n\nTask:\n" + (run.task || "(none given)") + "\n\nDraft:\n" + run.draft + earlier +
      '\n\nReply with only JSON like {"approved": false, "problems": ["specific fixable problem"]}. ' +
      "approved is true only if every criterion is met; problems is empty when approved.", SCHEMAS.review);
    const approved = v.approved === true;
    const problems = Array.isArray(v.problems) ? v.problems.map(str).filter(Boolean) : [];
    run.approved = approved;
    run.problems = approved ? [] : (problems.length ? problems : ["Does not yet meet the criteria."]);
    if (loop) {
      loop.round++;
      if (!loop.best || run.problems.length <= loop.best.n)  // a tie goes to the newer draft
        loop.best = { draft:run.draft, problems:run.problems.slice(), n:run.problems.length, round:loop.round };
      run.problems.forEach(p => { if (!loop.earlier.includes(p)) loop.earlier.push(p); });
      loop.earlier = loop.earlier.slice(-12);
    }
    if (approved) { s.text(tr("Meets every criterion.")); s.done("approved", "ok"); }
    else { s.list(run.problems); s.done("needs work", "warn"); }
    return { approved, step:s };
  }

  async function exec(b, tc){
    await tick(); mark(b);
    switch (b.type) {
      case "variables_set": run.vars.set(varId(b), await input(b, tc, "VALUE")); break;
      case "math_change": { const id = varId(b); run.vars.set(id, num(getVar(id)) + num(await input(b, tc, "DELTA", 1))); break; }
      case "text_append": { const id = varId(b); run.vars.set(id, str(getVar(id)) + str(await input(b, tc, "TEXT"))); break; }
      case "controls_repeat_ext": {
        const n = Math.max(0, Math.floor(num(await input(b, tc, "TIMES", 0))));
        for (let i = 0; i < n; i++) { if ((await body(b, "DO", tc)) === "break") break; }
        break;
      }
      case "controls_whileUntil": {
        const until = b.getFieldValue("MODE") === "UNTIL";
        while (true) {
          const c = bool(await input(b, tc, "BOOL", false));
          if (until ? c : !c) break;
          if ((await body(b, "DO", tc)) === "break") break;
          mark(b);
        }
        break;
      }
      case "controls_if": {
        const n = (b.elseifCount_ || 0) + 1;
        let done = false;
        for (let i = 0; i < n && !done; i++) {
          if (bool(await input(b, tc, "IF" + i, false))) { await runChain(b.getInputTargetBlock("DO" + i), tc); done = true; }
        }
        if (!done && b.getInput("ELSE")) await runChain(b.getInputTargetBlock("ELSE"), tc);
        break;
      }
      case "controls_forEach": {
        const id = varId(b), items = list(await input(b, tc, "LIST", []));
        for (const it of items) { run.vars.set(id, it); if ((await body(b, "DO", tc)) === "break") break; mark(b); }
        break;
      }
      case "controls_for": {
        const id = varId(b);
        const from = num(await input(b, tc, "FROM", 1)), to = num(await input(b, tc, "TO", 1));
        let by = Math.abs(num(await input(b, tc, "BY", 1))) || 1;
        if (from > to) by = -by;
        for (let i = from; by > 0 ? i <= to : i >= to; i += by) { run.vars.set(id, i); if ((await body(b, "DO", tc)) === "break") break; }
        break;
      }
      case "controls_flow_statements": throw (b.getFieldValue("FLOW") === "BREAK" ? new BreakSig() : new ContinueSig());
      case "procedures_callnoreturn": await callProc(b, tc); break;
      case "procedures_ifreturn": {
        if (bool(await input(b, tc, "CONDITION", false))) throw new ReturnSig(b.hasReturnValue_ ? await input(b, tc, "VALUE") : undefined);
        break;
      }
      case "lists_setIndex": await listSet(b, tc); break;
      case "lists_getIndex": await listGet(b, tc); break;
      case "rb_wait": {
        const unit = b.getFieldValue("UNIT") || "s", mult = { s:1, m:60, h:3600 }[unit] || 1;
        const amount = Math.max(0, num(await input(b, tc, "SECS", 1)));
        const secs = Math.min(86400, amount * mult);
        const label = tr("Waiting {time}", { time:secs >= 60 ? fmtLeft(secs * 1000) : secs + "s" });
        const st = secs >= 5 ? addStep("Wait", { mono:true, text:label }) : null;
        if (st) st.done("waiting", "");
        await sleepUntil(Date.now() + secs * 1000, st, label);
        if (st) { st.text(label.replace("Waiting", "Waited")); st.done("done", "ok"); }
        break;
      }
      case "rb_wait_time": {
        const h = Math.max(0, Math.min(23, Math.round(num(b.getFieldValue("HOUR"))))), m = Math.max(0, Math.min(59, Math.round(num(b.getFieldValue("MINUTE")))));
        const t = new Date(); t.setHours(h, m, 0, 0);
        if (t.getTime() <= Date.now()) t.setDate(t.getDate() + 1);
        const label = tr(t.getDate() !== new Date().getDate() ? "Waiting until {time} tomorrow" : "Waiting until {time}", { time:pad2(h) + ":" + pad2(m) });
        const st = addStep("Wait until a time", { mono:true, text:label }); st.done("waiting", "");
        await sleepUntil(t.getTime(), st, label);
        st.text(tr("Reached {time}", { time:pad2(h) + ":" + pad2(m) })); st.done("done", "ok"); mark(b);
        break;
      }
      case "rb_wait_until": {
        if (bool(await input(b, tc, "COND", false))) break;
        const target = b.getInputTargetBlock("COND");
        if (!target) fail(tr("A 'wait until' block has no condition in its slot."));
        const slow = usesClaude(target), every = slow ? 10000 : 500;
        const st = addStep("Wait until a condition", { mono:true, text:tr(slow ? "Checking every 10 seconds (it asks Claude)." : "Checking every half second.") });
        st.done("waiting", "");
        while (true) {
          await sleepUntil(Date.now() + every);
          mark(b);
          if (bool(await input(b, tc, "COND", false))) break;
        }
        st.text(tr("Condition became true.")); st.done("done", "ok");
        break;
      }
      case "rb_wait_msg": {
        const name = String(b.getFieldValue("MSG") || "").trim();
        if (!name) fail(tr("A 'wait until I receive' block has no message name."));
        const key = name.toLowerCase();
        const st = addStep(tr("Waiting for \u201c{message}\u201d", { message:name }), { mono:true, text:tr("Carries on when another script broadcasts this message.") });
        st.done("waiting", "");
        tc.payload = await new Promise((resolve, reject) => {
          const w = { resolve:(v) => { cleanup(); resolve(v === undefined ? "" : v); } };
          const stopper = () => { cleanup(); reject(new Halt()); };
          function cleanup(){
            run.stoppers.delete(stopper);
            const set = run.msgWaiters.get(key);
            if (set) { set.delete(w); if (!set.size) { run.msgWaiters.delete(key); run.msgNames.delete(key); } }
            run.msgWaiting--;
          }
          if (!run.msgWaiters.has(key)) run.msgWaiters.set(key, new Set());
          run.msgWaiters.get(key).add(w); run.msgNames.set(key, name);
          run.msgWaiting++; run.stoppers.add(stopper);
          checkStuck();
        });
        st.text(tr("Received \u201c{name}\u201d.", { name })); st.done("received", "ok"); mark(b);
        break;
      }
      case "rb_pause": {
        const note = str(await input(b, tc, "TEXT"));
        await waitForYou("Paused", note || tr("Paused."), (box, done) => {
          const row = document.createElement("div"); row.className = "row";
          const go = document.createElement("button"); go.type = "button"; go.className = "primary"; go.textContent = tr("Continue");
          go.onclick = () => done(true, "continued");
          row.appendChild(go); box.appendChild(row);
        });
        break;
      }
      case "rb_reset_timer": run.timerStart = Date.now(); break;
      case "rb_budget": {
        run.budget = Math.max(0, Math.round(num(await input(b, tc, "TOKENS", 0))));
        addStep("Budget", { mono:true, text:run.budget ? tr("This run stops before a Claude call once it has used about {budget} tokens (about {used} so far).", { budget:run.budget.toLocaleString(), used:tokensUsed().toLocaleString() }) : tr("No token budget for this run.") }).done("set", "ok");
        break;
      }
      case "rb_ask_first": {
        const what = b.getFieldValue("WHAT") || "all";
        (what === "all" ? ["ha", "messages", "files"] : [what]).forEach(k => run.askFirst.add(k));
        addStep("Ask first", { mono:true, text:tr("From now on, the program asks you before {what}.", { what:tr({ ha:"any smart home action (Home Assistant, Homey or MQTT)", messages:"sending messages and announcements", files:"saving files", all:"smart home actions, messages and saving files" }[what]) }) +
          (what === "files" || what === "all" ? "\n" + tr("On this page the browser already asks before every download.") : "") }).done("set", "ok");
        break;
      }
      case "rb_stop": throw new FinishSig();
      case "rb_broadcast":
      case "rb_broadcast_wait":
      case "rb_broadcast_with":
      case "rb_broadcast_with_wait": {
        const msg = str(await input(b, tc, "MSG")).trim();
        const payload = b.type.startsWith("rb_broadcast_with") ? await input(b, tc, "VALUE") : "";
        if (!msg) fail(tr("A broadcast block has no message name."));
        const key = msg.toLowerCase();
        const receivers = ws.getTopBlocks(true).filter(r => r.type === "rb_receive" && (!r.isEnabled || r.isEnabled()) &&
          String(r.getFieldValue("MSG") || "").trim().toLowerCase() === key);
        const wait = b.type === "rb_broadcast_wait" || b.type === "rb_broadcast_with_wait";
        const waiters = run.msgWaiters.has(key) ? [...run.msgWaiters.get(key)] : [];
        waiters.forEach(w => w.resolve(payload));
        if (!receivers.length && waiters.length) {
          run.broadcasts++;
          if (run.broadcasts <= 25) addStep(tr("Broadcast \u201c{message}\u201d", { message:msg }), { mono:true, text:tr(waiters.length === 1 ? "Woke {n} waiting script." : "Woke {n} waiting scripts.", { n:waiters.length }) }).done("sent", "ok");
          break;
        }
        if (!receivers.length) { addStep(tr("Broadcast \u201c{message}\u201d", { message:msg }), { mono:true, text:tr("No 'when I receive {msg}' script is listening, so nothing happened.", { msg }) }).done("no listeners", "warn"); break; }
        run.started += receivers.length;
        if (run.started > MAX_SCRIPTS) fail(tr("Stopped after starting {n} scripts. A message may be broadcasting itself in a loop.", { n:MAX_SCRIPTS }));
        if (run.threads.size + receivers.length > MAX_LIVE) fail(tr("Too many scripts running at once (over {n}). Use 'broadcast and wait' inside loops.", { n:MAX_LIVE }));
        run.broadcasts++;
        let st = null;
        if (run.broadcasts <= 25) {
          st = addStep(tr("Broadcast \u201c{message}\u201d", { message:msg }), { mono:true, text:tr(receivers.length === 1 ? (wait ? "{n} script started, waiting for it to finish" : "{n} script started") : (wait ? "{n} scripts started, waiting for them to finish" : "{n} scripts started"), { n:receivers.length }) });
          st.done(wait ? tr("waiting") : tr("sent"), wait ? "" : "ok");
        } else if (run.broadcasts === 26) {
          addStep("Broadcasts", { mono:true, text:tr("More broadcasts are running. They won't be listed one by one.") }).done("quiet", "warn");
        }
        const ps = receivers.map(r => startScript(r.getNextBlock(), payload));
        if (wait) {
          await Promise.all(ps);
          if (halting()) throw new Halt();
          if (st) st.done("all finished", "ok");
          mark(b);
        }
        break;
      }
      case "rb_use_model": run.tier = b.getFieldValue("TIER"); addStep("Model", { mono:true, text:tr("Using {model}", { model:tierLabel(run.tier) }) }).done("set", "ok"); break;
      case "rb_with_model": case "rb_with_any_model": {
        const before = run.tier;
        run.tier = b.type === "rb_with_any_model" ? "openrouter:" + (String(b.getFieldValue("MODEL") || "").trim() || "openrouter/auto") : b.getFieldValue("TIER");
        addStep("Model", { mono:true, text:tr("Using {model} for the blocks inside", { model:tierLabel(run.tier) }) }).done("set", "ok");
        try { await runChain(b.getInputTargetBlock("DO"), tc); }
        finally { run.tier = before; }
        break;
      }
      case "rb_task": {
        run.task = str(await input(b, tc, "TEXT")).trim();
        if (!run.task) fail(tr("The task is empty. Type what you want into 'set task to'."));
        addStep("Task set", { mono:true, text:run.task }).done("set", "ok");
        break;
      }
      case "rb_generate": {
        needTask();
        run.draft = await askStep("Write a first draft", "Complete the task below. Reply with only the finished piece, no preamble.\n\nTask:\n" + run.task);
        run.problems = []; run.approved = undefined;
        break;
      }
      case "rb_rework": {
        needDraft();
        const instr = str(await input(b, tc, "TEXT")).trim();
        if (!instr) fail(tr("The 'rework the draft' block has no instruction."));
        run.draft = await askStep(tr("Rework: {how}", { how:short(instr, 60) }), "Rewrite the draft below following this instruction: " + instr +
          "\nKeep it true to the original task. Reply with only the rewritten piece.\n\nTask:\n" + (run.task || "(none given)") + "\n\nDraft:\n" + run.draft);
        break;
      }
      case "rb_revise": {
        needDraft();
        if (!run.problems.length) { addStep("Revise", { text:tr("No review problems recorded, so nothing to fix.") }).done("skipped", "warn"); break; }
        const s = addStep("Revise to fix the problems");
        const fixed = run.reflect ? run.reflect.earlier.filter(e => !run.problems.includes(e)) : [];
        const keep = fixed.length ? "\n\nThese problems were fixed in earlier rounds. Don't bring them back:\n" + fixed.map(e => "- " + e).join("\n") : "";
        run.draft = await ask("Revise the draft so it fixes every problem listed. Change nothing else that works. Reply with only the improved piece.\n\nTask:\n" +
          (run.task || "(none given)") + "\n\nProblems:\n" + run.problems.map(p => "- " + p).join("\n") + keep + "\n\nDraft:\n" + run.draft, s);
        s.done("revised", "ok");
        break;
      }
      case "rb_set_draft": run.draft = str(await input(b, tc, "TEXT")); break;
      case "rb_checkpoint_save": {
        const name = String(b.getFieldValue("NAME") || "").trim();
        if (!name) fail(tr("The 'save checkpoint' block needs a name."));
        const snap = {}; CHECKPOINT_STATE.forEach(k => snap[k] = cloneState(run[k]));
        run.checkpoints.set(name.toLowerCase(), snap);
        addStep(tr("Checkpoint \u201c{name}\u201d", { name }), { text:run.draft ? tr("Saved the task, draft, review, result and variables. Draft: {draft}", { draft:short(run.draft, 80) }) : tr("Saved the task, draft, review, result and variables.") }).done("saved", "ok");
        break;
      }
      case "rb_checkpoint_restore": {
        const name = String(b.getFieldValue("NAME") || "").trim(), snap = run.checkpoints.get(name.toLowerCase());
        if (!snap) fail(tr("There's no checkpoint called \u201c{name}\u201d in this run. Put a 'save checkpoint' block before this one.", { name }));
        CHECKPOINT_STATE.forEach(k => run[k] = cloneState(snap[k]));
        addStep(tr("Back to checkpoint \u201c{name}\u201d", { name }), { text:run.draft ? tr("Restored the task, draft, review, result and variables. Draft: {draft}", { draft:short(run.draft, 80) }) : tr("Restored the task, draft, review, result and variables.") }).done("restored", "ok");
        break;
      }
      case "rb_review": { needDraft(); await reviewOnce(str(await input(b, tc, "CRITERIA")), tr("Review")); break; }
      case "rb_reflect": {
        needDraft();
        const criteria = str(await input(b, tc, "CRITERIA"));
        const max = Math.max(1, Math.min(6, Math.round(num(await input(b, tc, "ROUNDS", 3))) || 3));
        const before = run.reflect;
        run.reflect = { earlier:[], best:null, round:0 };
        try {
          for (let round = 1; round <= max + 1; round++) {
            mark(b);
            const { approved, step } = await reviewOnce(criteria, tr("Review, round {n}", { n:round }), true);
            if (approved) break;
            if (round > max) {
              step.done("failed, out of rounds", "bad"); run.outOfRounds = true;
              const best = run.reflect.best;
              if (best && best.round !== run.reflect.round) {
                run.draft = best.draft; run.problems = best.problems.slice(); run.approved = false;
                addStep("Kept the best draft", { text:tr("Went back to the draft from round {round}: it had the fewest problems ({n}). The rounds after it didn't improve on it.", { round:best.round, n:best.n }) }).done("best draft", "warn");
              }
              break;
            }
            if ((await body(b, "FIX", tc)) === "break") break;
          }
        } finally { run.reflect = before; }
        break;
      }
      case "rb_ask_me": { run.answer = await askPerson(str(await input(b, tc, "TEXT"))); break; }
      case "rb_agent_tool": case "rb_agent_builtin": case "rb_agent_mcp": break;  // only used inside an agent block
      case "rb_agent": await runAgent(b, tc); break;
      case "rb_say": {
        const v = await input(b, tc, "TEXT");
        const st = addStep("Note", { text:str(v) });
        if (isImg(v)) showPictureIn(st, v);
        st.done("say", "ok"); break;
      }
      case "rb_ha_call": await haCall(await input(b, tc, "SERVICE"), await input(b, tc, "ENTITY"), await input(b, tc, "DATA"), tc); break;
      case "rb_ha_notify": {
        const target = str(await input(b, tc, "TARGET")).trim() || "persistent_notification", text = str(await input(b, tc, "TEXT"));
        if (!text.trim()) fail(tr("The 'notify' block has no message."));
        if (!(await allowed(["ha", "messages"], "send a notification to " + target + ": " + short(text, 120)))) break;
        haNote(); addStep(tr("Notification → {target}", { target }), { text }).done("sample house", "ok"); break;
      }
      case "rb_tg_send": await tgSend(await input(b, tc, "TEXT"), false); break;
      case "rb_discord_send": case "rb_slack_send": await chatSend(b.type === "rb_discord_send" ? "discord" : "slack", await input(b, tc, "TEXT"), false); break;
      case "rb_homey_set": await homeySet(await input(b, tc, "DEVICE"), await input(b, tc, "CAPABILITY"), await input(b, tc, "VALUE"), false); break;
      case "rb_homey_flow": await homeyRunFlow(await input(b, tc, "NAME"), false); break;
      case "rb_homey_set_variable": await homeySetVariable(await input(b, tc, "NAME"), await input(b, tc, "VALUE"), false); break;
      case "rb_mqtt_publish": await mqttPublish(await input(b, tc, "TOPIC"), await input(b, tc, "TEXT"), b.getFieldValue("RETAIN") === "TRUE", false); break;
      case "rb_email_send": await emailSend(await input(b, tc, "TO"), await input(b, tc, "SUBJECT"), await input(b, tc, "TEXT"), false); break;
      case "rb_ha_speak": {
        const text = str(await input(b, tc, "TEXT")), player = str(await input(b, tc, "PLAYER")).trim();
        if (!text.trim()) fail(tr("The 'say' block has nothing to say."));
        if (!(await allowed(["ha", "messages"], "say on " + (player || "a speaker") + ": " + short(text, 120)))) break;
        haNote(); addStep(tr("Spoken on {player}", { player:player || tr("a speaker") }), { text }).done("sample house", "ok"); break;
      }
      case "rb_set_instructions": {
        run.instructions = str(await input(b, tc, "TEXT")).trim();
        addStep("Instructions for Claude", { text:run.instructions || tr("(cleared)") }).done("set", "ok"); break;
      }
      case "rb_clear_instructions": run.instructions = ""; addStep("Instructions for Claude", { mono:true, text:tr("Cleared.") }).done("cleared", "ok"); break;
      case "rb_chat_reset": { const n = str(await input(b, tc, "NAME")).trim(); run.chats.delete(n.toLowerCase()); addStep(tr("Conversation {name}", { name:n }), { mono:true, text:tr("Starting afresh.") }).done("reset", "ok"); break; }
      case "rb_rec_set": {
        const k = str(await input(b, tc, "KEY")).trim(), r = await input(b, tc, "REC"), v = await input(b, tc, "VALUE");
        if (!k) fail(tr("The 'set … of record' block needs a field name."));
        if (!isRec(r)) fail(tr("The 'set {k} of' block needs a record in its middle slot, such as a variable holding 'new record'.", { k }));
        r[k] = v; break;
      }
      case "rb_file_save": {
        const v = await input(b, tc, "VALUE"), name = str(await input(b, tc, "NAME")).trim() || "output", ext = b.getFieldValue("EXT") || "md";
        const st = addStep("Save file", { mono:true, text:tr("Waiting for you to confirm the download…") }); st.done("waiting", "");
        const msg = await saveTextFile(v, name, ext);
        st.text(msg); st.done(/^Saved/.test(msg) ? tr("saved") : tr("skipped"), /^Saved/.test(msg) ? "ok" : "warn");
        break;
      }
      case "rb_try": {
        const startIdx = stepsEl.children.length;
        try { await runChain(b.getInputTargetBlock("DO"), tc); }
        catch(e) {
          if (isControlSignal(e) || halting()) throw e;
          markFailedSince(startIdx);
          run.lastError = errText(e);
          addStep("Something failed, so the 'if it fails' part ran", { text:run.lastError }).done("handled", "warn");
          mark(b);
          await runChain(b.getInputTargetBlock("FAIL"), tc);
        }
        break;
      }
      case "rb_retry": {
        const max = Math.max(1, Math.min(10, Math.round(num(await input(b, tc, "TIMES", 3))) || 1));
        for (let attempt = 1; ; attempt++) {
          const startIdx = stepsEl.children.length;
          try { await runChain(b.getInputTargetBlock("DO"), tc); break; }
          catch(e) {
            if (isControlSignal(e) || halting()) throw e;
            markFailedSince(startIdx);
            run.lastError = errText(e);
            const code = e instanceof Error ? null : e && e.code;
            if (!RETRYABLE.has(code)) throw e;
            if (attempt >= max) { addStep(tr("Gave up after {n} tries", { n:attempt }), { text:run.lastError }).done("failed", "bad"); throw e; }
            const wait = 2000 * attempt;
            const st = addStep("Retrying", { mono:true, text:tr("Try {attempt} of {max} failed: {lastError}\nTrying again in {seconds}s.", { attempt, max, lastError:run.lastError, seconds:(wait / 1000) }) });
            st.done(tr("retry {n}", { n:attempt + 1 }), "warn");
            await sleepUntil(Date.now() + wait);
            mark(b);
          }
        }
        break;
      }
      case "rb_mem_set": {
        const v = await input(b, tc, "VALUE"), name = str(await input(b, tc, "NAME"));
        const kind = await memWrite(name, v, b.getFieldValue("KIND") || "transient");
        addStep(tr("Remembered \u201c{name}\u201d", { name:name.trim() }), { mono:true, text:memPreview(isImg(v) ? str(v) : v) + "  \u00b7  " + (kind === "transient" ? tr("while page is open") : tr("forever")) }).done("saved", "ok");
        break;
      }
      case "rb_mem_set_for": {
        const v = await input(b, tc, "VALUE"), name = str(await input(b, tc, "NAME"));
        const unit = b.getFieldValue("UNIT") || "d", n = Math.max(0, num(await input(b, tc, "N", 1)));
        const ms = Math.min(365 * 86400000, n * { m:60000, h:3600000, d:86400000 }[unit]);
        if (!ms) fail(tr("A 'remember for' block needs a time above zero."));
        const kind = await memWrite(name, v, "permanent", Date.now() + ms);
        addStep(tr("Remembered \u201c{name}\u201d", { name:name.trim() }), { mono:true, text:memPreview(v) + "  \u00b7  " + (kind === "transient" ? tr("while page is open") : tr("until {when}", { when:new Date(Date.now() + ms).toLocaleString(document.documentElement.lang || [], { weekday:"short", hour:"2-digit", minute:"2-digit", day:"numeric", month:"short" }) })) }).done("saved", "ok");
        break;
      }
      case "rb_mem_add": {
        const v = await input(b, tc, "VALUE"), name = str(await input(b, tc, "NAME")), key = memKey(name);
        const cur = memLive(key);
        const items = cur ? (Array.isArray(cur.value) ? cur.value.slice() : (cur.value === "" ? [] : [cur.value])) : [];
        items.push(v);
        const kind = cur ? (mem.transient.has(key) ? "transient" : "permanent") : (b.getFieldValue("KIND") || "transient");
        await memWrite(name, items, kind, cur && !mem.transient.has(key) ? cur.expires : null);
        addStep(tr("Added to \u201c{name}\u201d", { name:name.trim() }), { mono:true, text:memPreview(items) }).done("saved", "ok");
        break;
      }
      case "rb_mem_forget": { const name = str(await input(b, tc, "NAME")); await memRemove(memKey(name)); addStep(tr("Forgot \u201c{name}\u201d", { name:name.trim() }), { mono:true, text:"" }).done("forgotten", "ok"); break; }
      case "rb_img_show": { const pic = needImg(await input(b, tc, "IMG"), "show picture"); const st = addStep("Picture", { text:"" }); showPictureIn(st, pic); st.done("shown", "ok"); break; }
      case "rb_img_save": {
        const pic = needImg(await input(b, tc, "IMG"), "save picture");
        const st = addStep("Save picture", { mono:true, text:tr("Waiting for you to confirm the download…") }); st.done("waiting", "");
        const msg = await savePicture(pic, b.getFieldValue("FORMAT") || "png");
        st.text(msg); st.done(/^Saved/.test(msg) ? tr("saved") : tr("skipped"), /^Saved/.test(msg) ? "ok" : "warn"); break;
      }
      case "rb_show": addStep("Current draft", { text:run.draft || tr("(no draft yet)") }).done("shown", "ok"); break;
      case "rb_add_result": {
        const v = await input(b, tc, "TEXT");
        const st = addStep("Added to result", { text:str(v) });
        if (isImg(v)) { run.result.push(v); showPictureIn(st, v); }
        else run.result.push(str(v));
        st.done("added", "ok"); break;
      }
      case "rb_result": throw new FinishSig();
      case "rb_finish_with": { const v = await input(b, tc, "TEXT"); run.result = [isImg(v) ? v : str(v)]; throw new FinishSig(); }
      default:
        if (b.outputConnection) { await evalv(b, tc); break; }
        fail(tr("The block '{type}' isn't supported yet.", { type:b.type }));
    }
  }

  async function runChain(first, tc){
    for (let b = first; b; b = b.getNextBlock()) {
      if (b.isEnabled && !b.isEnabled()) continue;
      if (stepper.on) await stepGate(b);
      await exec(b, tc);
    }
  }

  function resultItems(){ return run.result.length ? run.result : (run.draft ? [run.draft] : []); }
  function finalText(){ return resultItems().filter(x => !isImg(x)).join("\n\n"); }
  function showResult(note){
    const items = resultItems();
    if (!items.length) { addStep("Finished", { text:tr("The program ended without a result. Add 'add … to the result' or 'write a first draft'.") }).done("no output", "warn"); return; }
    const text = finalText(), pics = items.filter(isImg);
    const el = document.createElement("div"); el.className = "result";
    el.innerHTML = '<div class="step-top"><span class="step-name"></span><span class="pill ok"></span></div><div class="step-body"></div>' +
      '<div class="result-actions"></div>';
    el.querySelector(".step-name").textContent = tr("Result");
    el.querySelector(".pill").textContent = tr(note || (run.outOfRounds ? "best effort" : "finished"));
    const body = el.querySelector(".step-body"), actions = el.querySelector(".result-actions");
    items.forEach((it, i) => {
      if (isImg(it)) { const im = document.createElement("img"); im.src = it.url; im.alt = it.name; im.className = "pic"; body.appendChild(im); }
      else { const p = document.createElement("div"); p.className = "result-text"; p.textContent = it; body.appendChild(p); }
    });
    if (text) {
      const copy = document.createElement("button"); copy.type = "button"; copy.textContent = pics.length ? "Copy text" : "Copy result";
      copy.onclick = async () => {
        try { await navigator.clipboard.writeText(text); copy.textContent = tr("Copied"); }
        catch(e) { const r = document.createRange(); r.selectNodeContents(body); const sel = getSelection(); sel.removeAllRanges(); sel.addRange(r); copy.textContent = tr("Selected, press Ctrl+C"); }
      };
      actions.appendChild(copy);
    }
    if (pics.length && downloads) pics.forEach((pic, i) => {
      const sv = document.createElement("button"); sv.type = "button"; sv.textContent = pics.length > 1 ? "Save picture " + (i + 1) + " (PNG)" : "Save picture (PNG)";
      sv.onclick = async () => {
        sv.disabled = true;
        try { const blob = pic.type === "image/png" ? pic.blob : await toPng(pic, 2048); await downloads.save({ filename:slug(pic.name) + ".png", data:blob }); sv.textContent = tr("Saved"); }
        catch(e) { sv.textContent = e && e.code === "declined" ? "Save cancelled" : "Couldn't save"; }
        finally { sv.disabled = false; }
      };
      actions.appendChild(sv);
    });
    if (!run.replay && run.reason === "manual" && !note) actions.appendChild(saveTestButton(el));
    const use = usageLine();
    if (use) { const u = document.createElement("div"); u.className = "result-usage"; u.textContent = use; el.appendChild(u); }
    stepsEl.appendChild(el); el.scrollIntoView({ block:"nearest" });
  }

