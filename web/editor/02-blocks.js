  // 02-blocks.js: Every block's definition, and the long-text field.
  /* ---------- Custom blocks ---------- */
  // Every Second Thought block is defined through here, so its words can be shown in another language (I18N, below).
  const BLOCK_DEFS = [];
  function defineBlocks(defs){
    defs.forEach(d => BLOCK_DEFS.push(JSON.parse(JSON.stringify(d, (k, v) => typeof v === "function" ? undefined : v))));
    Blockly.defineBlocksWithJsonArray(defs.map(localizeBlock));
  }
  // The block's words in the page's language (i18n/<language>.json): its messages, tooltip and dropdown labels.
  // Dropdown values never change, so a program made in one language opens the same in any other.
  const I18N = window.ST_I18N || { blocks:{}, options:{}, categories:{}, labels:{} };
  function localizeBlock(d){
    if (!window.ST_I18N) return d;
    const t = I18N.blocks[d.type] || {}, out = Object.assign({}, d);
    Object.keys(t).forEach(k => { if (/^message\d+$/.test(k) || k === "tooltip") out[k] = t[k]; });
    Object.keys(d).filter(k => /^args\d+$/.test(k)).forEach(k => {
      out[k] = d[k].map(a => {
        const labels = I18N.options[d.type + "." + a.name];
        return a.type === "field_dropdown" && Array.isArray(a.options) && labels ?
          Object.assign({}, a, { options:a.options.map(([label, value]) => [typeof label === "string" && labels[value] ? labels[value] : label, value]) }) : a;
      });
    });
    return out;
  }
  const catName = name => (window.ST_I18N && I18N.categories[name]) || name;
  const tLabel = text => (window.ST_I18N && I18N.labels[text]) || text;
  // The page's own words in that language: "page" in i18n/<language>.json maps English text to its translation.
  // The text written in the page is swapped once, here; text the page sets later goes through tr(), and the tests
  // check every text given to tr has a translation.
  const PAGE_T = (window.ST_I18N && I18N.page) || {};
  function tr(s, vars){
    const t = PAGE_T[s] || s;
    return vars ? t.replace(/\{(\w+)\}/g, (m, k) => k in vars ? String(vars[k]) : m) : t;
  }
  const PAGE_ROOTS = "header.bar, #gallery, #lib, #ha, #mem, #bk, #io, #describe, main.main";
  const PAGE_LATER = "script, style, select, textarea, #blockly, #gal-body, #ex-desc, #status, #lib-where, #mem-where";  // filled in by code
  const PAGE_ATTRS = ["title", "placeholder", "aria-label"];
  const RICH = new Set(["B", "I", "EM", "STRONG", "CODE"]);
  const squash = t => String(t).replace(/\s+/g, " ").trim();
  // Every English text in the page's sections (and, with apply, swapped for its translation). A paragraph with bold
  // words in it is one text, as HTML, so it can be translated as a whole sentence.
  function pageTexts(apply){
    const keys = [];
    const swap = key => { keys.push(key); return apply && PAGE_T[key]; };
    const visit = el => {
      if (el.matches(PAGE_LATER)) return;
      PAGE_ATTRS.forEach(a => { const v = el.getAttribute(a); if (v && /[A-Za-z]/.test(v)) { const t = swap(squash(v)); if (t) el.setAttribute(a, t); } });
      const kids = [...el.childNodes];
      if (kids.some(n => n.nodeType === 1) && kids.every(n => n.nodeType === 3 || (n.nodeType === 1 && RICH.has(n.tagName)))) {
        const t = swap(squash(el.innerHTML)); if (t) el.innerHTML = t; return;
      }
      kids.forEach(n => {
        if (n.nodeType === 1) visit(n);
        else if (n.nodeType === 3 && /[A-Za-z]/.test(n.nodeValue)) {
          const t = swap(squash(n.nodeValue));
          if (t) n.nodeValue = n.nodeValue.match(/^\s*/)[0] + t + n.nodeValue.match(/\s*$/)[0];
        }
      });
    };
    document.querySelectorAll(PAGE_ROOTS).forEach(visit);
    return keys;
  }
  const PAGE_KEYS = pageTexts(!!window.ST_I18N);
  if (window.ST_I18N) document.documentElement.lang = window.ST_LANG;
  window.__pageI18n = () => ({ lang:window.ST_LANG || "en", keys:[...new Set(PAGE_KEYS)], missing:[...new Set(PAGE_KEYS)].filter(k => !PAGE_T[k]),
    categories:[...new Set(EXAMPLE_CATEGORIES.concat(window.__galleryGroups || []))] });
  function localizeToolbox(tb){
    if (!window.ST_I18N) return tb;
    const walk = items => items.map(it => Object.assign({}, it, it.kind === "category" ? { name:catName(it.name) } : {}, it.kind === "label" ? { text:tLabel(it.text) } : {},
      Array.isArray(it.contents) ? { contents:walk(it.contents) } : {}));
    return Object.assign({}, tb, { contents:walk(tb.contents) });
  }
  window.__i18n = () => {
    const cats = [], labels = ["Type in 'Find a block' above the canvas.", "No blocks match"];
    const walk = items => items.forEach(it => { if (it.kind === "category") cats.push(it.name); if (it.kind === "label") labels.push(it.text); if (Array.isArray(it.contents)) walk(it.contents); });
    walk(toolbox.contents);
    return { lang:window.ST_LANG, langs:JSON.parse(document.getElementById("i18n").textContent || "{}"), loaded:window.ST_I18N || null,
             missing:window.ST_I18N_MISSING || null, defs:BLOCK_DEFS, categories:cats, labels };
  };
  window.__blockDefs = () => BLOCK_DEFS;
  const S = (type, msg, args, extra) => Object.assign({ type, message0:msg, args0:args || [], previousStatement:null, nextStatement:null }, extra);
  const V = (type, msg, args, output, extra) => Object.assign({ type, message0:msg, args0:args || [], output }, extra);
  const val = name => ({ type:"input_value", name });
  /* The ready-made agent tools, in the order the Tools category shows them. */
  const AGENT_TOOL_KINDS = [["search the web and read pages","web"],["ask me a question","ask"],["remember and recall notes","memory"],
    ["work out sums","calc"],["clock times and dates","time"],["read a file I choose","file"],["check text against criteria","review"],
    ["news feeds","feeds"],["search LinkedIn (public pages)","linkedin"],["calendar: events and free time","calendar"],
    ["email: search and read","email"],["email: send (asks me first)","email_send"],
    ["GitHub: projects and pull requests","github"],["GitHub: comment, open and label issues (asks me first)","github_act"],
    ["Telegram: search my messages","telegram"],["Telegram: send (asks me first)","telegram_send"],["Telegram: send (no asking)","telegram_send_free"],
    ["Discord: search my channels","discord"],["Discord: send (asks me first)","discord_send"],["Discord: send (no asking)","discord_send_free"],
    ["Slack: search my channels","slack"],["Slack: send (asks me first)","slack_send"],["Slack: send (no asking)","slack_send_free"],
    ["MQTT: read topics","mqtt"],["MQTT: publish (asks me first)","mqtt_act"],["MQTT: publish (no asking)","mqtt_act_free"],
    ["Homey: look at devices, flows and variables","homey_read"],["Homey: control devices and start flows (asks me first)","homey_act"],["Homey: control devices and start flows (no asking)","homey_act_free"],
    ["Home Assistant: look at devices","ha_read"],["Home Assistant: control devices","ha_act"],["Home Assistant: control devices (no asking)","ha_act_free"]];
  // The model services come from SERVICES in python/second_thought/providers.py (tools/sync.py copies them in).
  const SERVICES = JSON.parse(document.getElementById("services").textContent);
  const SIZES = ["quick", "default", "complex"];
  // A service's tiers in the menus. A quick or complex tier whose model is the default's is left out: it's the same choice.
  const menuSizes = s => SIZES.filter(k => s.tiers[k] && (k === "default" || s.tiers[k][0] !== s.tiers.default[0]));
  const TIERS = SERVICES.flatMap(s => menuSizes(s).map(k => [s.tiers[k][1], s.prefix + k]));
  // The service a tier belongs to, or null for Claude (its tiers are plain quick, default and complex).
  const serviceOf = t => { t = String(t || ""); return SERVICES.find(s => s.prefix && (t.startsWith(s.prefix) || (s.any_model && t.startsWith(s.any_model)))) || null; };
  const serviceNamed = name => SERVICES.find(s => s.name === name);
  const isElsewhere = t => !!serviceOf(t);
  (function fillTierMenu(){
    const sel = $("tier");
    SERVICES.forEach(s => {
      const g = document.createElement("optgroup");
      g.label = s.menu + (s.api === "anthropic" ? "" : " (runs in exported Python)");
      menuSizes(s).forEach(k => {
        const o = document.createElement("option");
        o.value = s.prefix + k; o.textContent = s.tiers[k][2] || s.tiers[k][1];
        if (o.value === "default") o.selected = true;
        g.appendChild(o);
      });
      sel.appendChild(g);
    });
  })();
  const tierLabel = t => String(t || "").startsWith("openrouter:") ? "OpenRouter: " + t.slice(11) : (TIERS.find(x => x[1] === t) || [t])[0];
  // What a program can do (CAPABILITIES in python/second_thought/core.py, copied in by tools/sync.py), worked out from
  // its blocks. Every block is listed here or in NO_CAPABILITY; a test checks that, so a new block can't be missed.
  const CAPABILITIES = JSON.parse(document.getElementById("capabilities").textContent);  // [id, what it does, acts]
  const keeps = b => (b.getFieldValue("KIND") || "transient") === "permanent" ? "memory" : null;
  const CAP_BLOCKS = {
    rb_email_send:"email_send", rb_email_when:"email_read", rb_tg_send:"telegram_send", rb_tg_when:"telegram_read", rb_tg_message:"telegram_read",
    rb_discord_send:"discord_send", rb_discord_when:"discord_read", rb_slack_send:"slack_send", rb_slack_when:"slack_read", rb_gh_when:"github_read", rb_gh_issue_when:"github_read", rb_gh_release_when:"github_read",
    rb_ha_call:"ha_act", rb_ha_notify:"ha_act", rb_ha_speak:"ha_act", rb_ha_attr:"ha_read", rb_ha_event_when:"ha_read", rb_ha_find:"ha_read",
    rb_ha_history:"ha_read", rb_ha_snapshot:"ha_read", rb_ha_state:"ha_read", rb_ha_summary:"ha_read", rb_ha_trigger:"ha_read", rb_ha_when:"ha_read",
    rb_homey_flow:"homey_act", rb_homey_set:"homey_act", rb_homey_set_variable:"homey_act", rb_homey_find:"homey_read", rb_homey_value:"homey_read",
    rb_homey_variable:"homey_read", rb_homey_when:"homey_read", rb_mqtt_publish:"mqtt_publish", rb_mqtt_read:"mqtt_read", rb_mqtt_when:"mqtt_read",
    rb_webhook_when:"webhook", rb_web_search:"web", rb_page_when:"web", rb_calendar:"calendar", rb_cal_when:"calendar", rb_feed_news:"feeds",
    rb_feed_when:"feeds", rb_folder_when:"folder", rb_folder_files:"folder", rb_file_choose:"files_read", rb_img_choose:"files_read", rb_file_save:"files_save",
    rb_img_save:"files_save", rb_mem_set:keeps, rb_mem_add:keeps, rb_mem_set_for:"memory", rb_mem_get:"memory", rb_mem_has:"memory",
    rb_mem_names:"memory", rb_mem_forget:"memory", rb_agent_mcp:"mcp" };
  const NO_CAPABILITY = ("rb_add_result rb_agent rb_agent_steps rb_agent_tool rb_answer rb_approve rb_ask rb_ask_first rb_ask_list rb_ask_me " +
    "rb_ask_number rb_ask_record rb_ask_records rb_ask_yesno rb_better rb_broadcast rb_broadcast_wait rb_broadcast_with rb_broadcast_with_wait " +
    "rb_budget rb_chat rb_chat_reset rb_checkpoint_restore rb_checkpoint_save rb_choose rb_clear_instructions rb_contains rb_draft rb_error " +
    "rb_event rb_every rb_extract rb_finish_with rb_generate rb_img_ask rb_img_change rb_img_draw rb_img_score rb_img_show rb_longtext " +
    "rb_msg_value rb_now rb_passed rb_pause rb_problems rb_prompt rb_rec_get rb_rec_has rb_rec_keys rb_rec_new rb_rec_set rb_receive " +
    "rb_reflect rb_reset_timer rb_result rb_result_text rb_retry rb_review rb_revise rb_rework rb_rewrite rb_run_program rb_say rb_score " +
    "rb_set_draft rb_set_instructions rb_show rb_sort rb_start rb_stop rb_task rb_task_get rb_setup_check rb_timer rb_tokens_used rb_try rb_use_model " +
    "rb_wait rb_wait_msg rb_wait_time rb_wait_until rb_when_time rb_with_any_model rb_with_model rb_word_count").split(" ");
  // The agent's built-in tools (rb_agent_builtin's KIND). Every kind in AGENT_TOOL_KINDS is listed; null means nothing to declare.
  const CAP_KINDS = { web:"web", linkedin:"web", file:"files_read", memory:"memory", feeds:"feeds", calendar:"calendar",
    email:"email_read", email_send:"email_send", github:"github_read", github_act:"github_comment",
    telegram:"telegram_read", telegram_send:"telegram_send", telegram_send_free:"telegram_send",
    discord:"discord_read", discord_send:"discord_send", discord_send_free:"discord_send",
    slack:"slack_read", slack_send:"slack_send", slack_send_free:"slack_send",
    mqtt:"mqtt_read", mqtt_act:"mqtt_publish", mqtt_act_free:"mqtt_publish",
    homey_read:"homey_read", homey_act:"homey_act", homey_act_free:"homey_act", ha_read:"ha_read", ha_act:"ha_act", ha_act_free:"ha_act",
    ask:null, calc:null, time:null, review:null };
  function blockCapability(b){
    const c = b.type === "rb_agent_builtin" ? CAP_KINDS[b.getFieldValue("KIND")] : CAP_BLOCKS[b.type];
    return typeof c === "function" ? c(b) : (c || null);
  }
  // [[id, what it does, acts], ...] in CAPABILITIES order, for this program and the saved programs it runs.
  function programCapabilities(){
    const got = new Set(allProgramBlocks().map(blockCapability).filter(Boolean));
    return CAPABILITIES.filter(c => got.has(c[0]));
  }
  const andList = xs => xs.length < 2 ? xs.join("") : tr("{list} and {last}", { list:xs.slice(0, -1).join(", "), last:xs[xs.length - 1] });
  // "It can send email and control your Home Assistant devices. It can also read your calendars." for the import message.
  function capabilitySentence(caps){
    const acts = caps.filter(c => c[2]).map(c => tr(c[1])), reads = caps.filter(c => !c[2]).map(c => tr(c[1]));
    if (!acts.length && !reads.length) return "";
    return acts.length ? tr("It can {things}.", { things:andList(acts) }) + (reads.length ? " " + tr("It can also {things}.", { things:andList(reads) }) : "") +
      " " + tr("Exported to Python, it asks you before its first run.") : tr("It can {things}.", { things:andList(reads) });
  }
  window.__capabilityCheck = () => ({ blocks:Object.keys(CAP_BLOCKS), none:NO_CAPABILITY, kinds:Object.keys(CAP_KINDS),
    agentKinds:AGENT_TOOL_KINDS.map(k => k[1]), ids:CAPABILITIES.map(c => c[0]),
    used:[...new Set(Object.values(CAP_BLOCKS).concat(Object.values(CAP_KINDS)).map(c => typeof c === "function" ? "memory" : c).filter(Boolean))],
    program:programCapabilities().map(c => c[0]) });
  /* ---------- Long text field: wraps at 80 characters, any number of lines ---------- */
  const WRAP = 80;
  function wrapText(text, width){
    const out = [];
    String(text).split("\n").forEach(para => {
      if (!para.length) { out.push(""); return; }
      let line = "";
      para.split(/(\s+)/).forEach(tok => {
        if (!tok) return;
        while (tok.length > width) {
          if (line.trim()) { out.push(line.replace(/\s+$/, "")); line = ""; }
          out.push(tok.slice(0, width)); tok = tok.slice(width);
        }
        if ((line + tok).length > width && line.trim()) { out.push(line.replace(/\s+$/, "")); line = /^\s+$/.test(tok) ? "" : tok; }
        else line += tok;
      });
      out.push(line.replace(/\s+$/, ""));
    });
    return out;
  }
  let LongTextField;
  if (window.FieldMultilineInput) {
    LongTextField = class extends window.FieldMultilineInput {
      constructor(value, validator, config){ super(value, validator, config); this.maxLines_ = Infinity; this.maxDisplayLength = WRAP + 2; }
      static fromJson(options){ return new this(Blockly.utils.parsing.replaceMessageReferences(options.text), undefined, options); }
      getDisplayText_(){
        const t = this.getText();
        if (!t) return Blockly.Field.NBSP;
        let shown = wrapText(t, WRAP).map(l => l.replace(/\s/g, Blockly.Field.NBSP)).join("\n");
        const src = this.getSourceBlock();
        if (src && src.RTL) shown += "\u200F";
        return shown;
      }
    };
  } else {
    LongTextField = class extends Blockly.FieldTextInput {
      static fromJson(options){ return new this(Blockly.utils.parsing.replaceMessageReferences(options.text), undefined, options); }
    };
  }
  Blockly.fieldRegistry.register("field_longtext", LongTextField);

  defineBlocks([
    { type:"rb_longtext", message0:"%1", args0:[{ type:"field_longtext", name:"TEXT", text:"" }], output:"String", style:"text",
      tooltip:"Long text. Press Enter for a new line; lines wrap at 80 characters." },
    /* Events */
    { type:"rb_start", message0:"when Run is clicked", nextStatement:null, style:"events_hat",
      tooltip:"Every program starts here. Blocks below it run top to bottom. Several of these run side by side." },
    { type:"rb_receive", message0:"when I receive %1", args0:[{ type:"field_input", name:"MSG", text:"message1" }], nextStatement:null, style:"events_hat",
      tooltip:"Runs the blocks below whenever this message is broadcast. Several scripts can listen for the same message." },
    { type:"rb_when_time", message0:"when it's %1 : %2 %3",
      args0:[{ type:"field_number", name:"HOUR", value:9, min:0, max:23, precision:1 }, { type:"field_number", name:"MINUTE", value:0, min:0, max:59, precision:1 },
             { type:"field_dropdown", name:"DAYS", options:[["every day","every"],["on weekdays","weekdays"],["at weekends","weekends"]] }],
      nextStatement:null, style:"events_hat", tooltip:"Runs at this time (24-hour clock) while Schedules is on and this page is open." },
    { type:"rb_every", message0:"every %1 %2",
      args0:[{ type:"field_number", name:"N", value:30, min:1, max:1440, precision:1 }, { type:"field_dropdown", name:"UNIT", options:[["minutes","m"],["hours","h"]] }],
      nextStatement:null, style:"events_hat", tooltip:"Runs repeatedly while Schedules is on and this page is open. The first run is one interval after you turn Schedules on." },
    S("rb_broadcast", "broadcast %1", [val("MSG")], { style:"events", inputsInline:true, tooltip:"Starts every 'when I receive' script for this message, then carries straight on." }),
    S("rb_broadcast_wait", "broadcast %1 and wait", [val("MSG")], { style:"events", inputsInline:true, tooltip:"Starts every 'when I receive' script for this message and waits until they have all finished." }),
    /* Control extras */
    S("rb_wait", "wait %1 %2", [val("SECS"), { type:"field_dropdown", name:"UNIT", options:[["seconds","s"],["minutes","m"],["hours","h"]] }],
      { style:"control", inputsInline:true, tooltip:"Pause this script (up to 24 hours)." }),
    S("rb_wait_until", "wait until %1", [{ type:"input_value", name:"COND", check:"Boolean" }],
      { style:"control", inputsInline:true, tooltip:"Pause until the condition is true. Checked twice a second, or every 10 seconds if it asks Claude." }),
    { type:"rb_stop", message0:"stop the run", previousStatement:null, style:"control", tooltip:"End the run here. Anything already in the result is shown." },
    S("rb_use_model", "use model %1", [{ type:"field_dropdown", name:"TIER", options:TIERS }], { style:"control",
      tooltip:"Switch model for the AI blocks after this one. Models other than Claude run in exported Python; in this page Claude stands in for them." }),
    { type:"rb_with_model", message0:"with model %1", args0:[{ type:"field_dropdown", name:"TIER", options:TIERS }],
      message1:"%1", args1:[{ type:"input_statement", name:"DO" }], previousStatement:null, nextStatement:null, style:"control",
      tooltip:"Runs just the blocks inside on this model, then goes back to the model before. Models other than Claude run in exported Python; in this page Claude stands in for them." },
    { type:"rb_with_any_model", message0:"with OpenRouter model %1", args0:[{ type:"field_input", name:"MODEL", text:"openrouter/auto" }],
      message1:"%1", args1:[{ type:"input_statement", name:"DO" }], previousStatement:null, nextStatement:null, style:"control",
      tooltip:"Runs just the blocks inside on any model OpenRouter offers. Type its name from openrouter.ai/models, for example mistralai/mistral-small or google/gemma-4-31b-it. openrouter/auto picks one for you. Runs in exported Python (needs OPENROUTER_API_KEY); in this page Claude stands in." },
    /* Operators extras */
    V("rb_contains", "%1 contains %2", [val("A"), val("B")], "Boolean", { style:"operators", inputsInline:true, tooltip:"True if the first text includes the second (ignores case)." }),
    V("rb_word_count", "word count of %1", [val("TEXT")], "Number", { style:"text", inputsInline:true }),
    /* Wait & time */
    S("rb_wait_time", "wait until %1 : %2", [{ type:"field_number", name:"HOUR", value:9, min:0, max:23, precision:1 }, { type:"field_number", name:"MINUTE", value:0, min:0, max:59, precision:1 }],
      { style:"time", tooltip:"Pause until this time (24-hour clock). If it has passed today, waits until tomorrow." }),
    S("rb_wait_msg", "wait until I receive %1", [{ type:"field_input", name:"MSG", text:"message1" }],
      { style:"time", tooltip:"Pause this script until another script broadcasts the message." }),
    S("rb_pause", "pause until I click Continue: %1", [val("TEXT")], { style:"time", inputsInline:true, tooltip:"A checkpoint. Shows the note in the log and waits for you." }),
    V("rb_timer", "timer", [], "Number", { style:"time", tooltip:"Seconds since the run started or the timer was reset." }),
    S("rb_reset_timer", "reset timer", [], { style:"time" }),
    V("rb_now", "current %1", [{ type:"field_dropdown", name:"PART", options:[["time","time"],["date","date"],["date and time","datetime"],["hour","hour"],["minute","minute"],["day of week","weekday"]] }],
      null, { style:"time" }),
    /* Draft */
    S("rb_task", "set task to %1", [val("TEXT")], { style:"draft", tooltip:"Sets what the AI should produce." }),
    S("rb_generate", "write a first draft", [], { style:"draft", tooltip:"Claude writes a draft that completes the task." }),
    S("rb_rework", "rework the draft: %1", [val("TEXT")], { style:"draft", tooltip:"Claude rewrites the draft following your instruction." }),
    S("rb_revise", "revise to fix the review's problems", [], { style:"draft", tooltip:"Claude fixes the problems the last review found." }),
    S("rb_set_draft", "set draft to %1", [val("TEXT")], { style:"draft" }),
    V("rb_draft", "draft", [], "String", { style:"draft" }),
    S("rb_checkpoint_save", "save checkpoint %1", [{ type:"field_input", name:"NAME", text:"good draft" }], { style:"draft",
      tooltip:"Remembers the task, draft, review, result and variables as they are now, under this name, for the rest of the run." }),
    S("rb_checkpoint_restore", "go back to checkpoint %1", [{ type:"field_input", name:"NAME", text:"good draft" }], { style:"draft",
      tooltip:"Puts the task, draft, review, result and variables back as they were at 'save checkpoint'. Memory, files and messages already sent aren't undone." }),
    V("rb_task_get", "task", [], "String", { style:"draft" }),
    /* Ask Claude */
    V("rb_ask", "ask Claude %1", [val("TEXT")], "String", { style:"claude", inputsInline:true, tooltip:"Claude answers in text." }),
    V("rb_ask_yesno", "Claude says yes to %1", [val("TEXT")], "Boolean", { style:"claude", inputsInline:true, tooltip:"Claude answers a yes/no question." }),
    V("rb_ask_number", "ask Claude for a number: %1", [val("TEXT")], "Number", { style:"claude", inputsInline:true }),
    V("rb_ask_list", "ask Claude for a list: %1", [val("TEXT")], "Array", { style:"claude", inputsInline:true, tooltip:"Claude replies with a list you can loop over." }),
    V("rb_rewrite", "rewrite %1 to %2", [val("TEXT"), val("HOW")], "String", { style:"claude", inputsInline:true, tooltip:"For example: rewrite (draft) to (translate into French)." }),
    V("rb_extract", "extract %1 from %2", [val("WHAT"), val("TEXT")], "String", { style:"claude", inputsInline:true }),
    /* Review */
    { type:"rb_reflect",
      message0:"review the draft against %1", args0:[val("CRITERIA")],
      message1:"up to %1 rounds; when it fails, do", args1:[val("ROUNDS")],
      message2:"%1", args2:[{ type:"input_statement", name:"FIX" }],
      previousStatement:null, nextStatement:null, style:"review",
      tooltip:"Claude critiques the draft. If it fails, the blocks inside run, then it critiques again. Each round the reviewer also checks that earlier problems haven't come back. If the rounds run out, the draft with the fewest problems is kept, not just the last one." },
    S("rb_review", "review the draft against %1", [val("CRITERIA")], { style:"review", tooltip:"One review. Use 'draft passed review' and 'review problems' afterwards." }),
    V("rb_passed", "draft passed review", [], "Boolean", { style:"review" }),
    V("rb_problems", "review problems", [], "Array", { style:"review" }),
    V("rb_score", "score %1 out of 10 for %2", [val("TEXT"), val("CRITERIA")], "Number", { style:"review", inputsInline:true }),
    V("rb_better", "better of %1 and %2 for %3", [val("A"), val("B"), val("CRITERIA")], "String", { style:"review", inputsInline:true }),
    /* You */
    S("rb_ask_me", "ask me %1 and wait", [val("TEXT")], { style:"you", inputsInline:true, tooltip:"Pauses the run until you type an answer in the log." }),
    V("rb_answer", "answer", [], "String", { style:"you" }),
    V("rb_approve", "I approve %1", [val("TEXT")], "Boolean", { style:"you", inputsInline:true, tooltip:"Shows the text and waits for you to approve or send it back." }),
    V("rb_choose", "let me choose from %1", [val("LIST")], "String", { style:"you", inputsInline:true }),
    /* Output */
    S("rb_say", "say %1", [val("TEXT")], { style:"output", inputsInline:true, tooltip:"Writes a note in the run log." }),
    S("rb_show", "show the draft in the log", [], { style:"output" }),
    S("rb_add_result", "add %1 to the result", [val("TEXT")], { style:"output", inputsInline:true }),
    { type:"rb_result", message0:"finish and show the result", previousStatement:null, style:"output",
      tooltip:"Ends the run. Shows what you added to the result, or the draft if you added nothing." },
    { type:"rb_finish_with", message0:"finish with %1", args0:[val("TEXT")], previousStatement:null, style:"output", inputsInline:true },
    /* Conversations */
    S("rb_set_instructions", "set instructions for Claude to %1", [val("TEXT")], { style:"claude", tooltip:"Sent with every Claude call after this block, for example a role, tone or house style." }),
    S("rb_clear_instructions", "clear instructions for Claude", [], { style:"claude" }),
    V("rb_chat", "chat %1 : %2", [val("NAME"), val("TEXT")], "String", { style:"claude", inputsInline:true,
      tooltip:"Sends a message in a named conversation. Claude sees the earlier turns of that conversation." }),
    S("rb_chat_reset", "start conversation %1 afresh", [val("NAME")], { style:"claude", inputsInline:true }),
    V("rb_web_search", "search the web for %1", [val("TEXT")], "String", { style:"claude", inputsInline:true,
      tooltip:"In exported Python this searches the live web. In this page Claude can't browse, so it answers from its own knowledge and the log says so." }),
    /* Records */
    V("rb_rec_new", "new record", [], "Record", { style:"records" }),
    S("rb_rec_set", "set %1 of %2 to %3", [val("KEY"), val("REC"), val("VALUE")], { style:"records", inputsInline:true, tooltip:"Changes one field of a record (usually a record variable)." }),
    V("rb_rec_get", "%1 of %2", [val("KEY"), val("REC")], null, { style:"records", inputsInline:true }),
    V("rb_rec_has", "%1 has field %2", [val("REC"), val("KEY")], "Boolean", { style:"records", inputsInline:true }),
    V("rb_rec_keys", "fields of %1", [val("REC")], "Array", { style:"records", inputsInline:true }),
    V("rb_ask_record", "ask Claude for a record with fields %1 : %2", [val("FIELDS"), val("TEXT")], "Record", { style:"records", inputsInline:true,
      tooltip:"Fields separated by commas, for example: title, score, notes." }),
    V("rb_ask_records", "ask Claude for a list of records with fields %1 : %2", [val("FIELDS"), val("TEXT")], "Array", { style:"records", inputsInline:true }),
    V("rb_sort", "sort %1 by %2 %3", [val("LIST"), val("KEY"), { type:"field_dropdown", name:"ORDER", options:[["highest first","desc"],["lowest first","asc"]] }], "Array",
      { style:"records", inputsInline:true, tooltip:"Sorts a list of records by a field. Leave the field empty to sort plain items." }),
    /* Message payloads */
    S("rb_broadcast_with", "broadcast %1 with %2", [val("MSG"), val("VALUE")], { style:"events", inputsInline:true, tooltip:"Starts every 'when I receive' script for the message. Each one gets the value as its 'message value'." }),
    S("rb_broadcast_with_wait", "broadcast %1 with %2 and wait", [val("MSG"), val("VALUE")], { style:"events", inputsInline:true }),
    V("rb_msg_value", "message value", [], null, { style:"events", tooltip:"The value sent with the broadcast that started this script (or woke this 'wait until I receive'). In a program run by 'run program', the value it was given." }),
    /* Prompt library */
    V("rb_prompt", "prompt %1", [{ type:"field_input", name:"NAME", text:"my prompt" }], "String", { style:"claude", tooltip:"Text from your prompt library (open Programs to add prompts)." }),
    /* Files and errors */
    V("rb_file_choose", "text of a file I choose", [], "String", { style:"files", tooltip:"Pauses the run so you can pick a PDF, a Word .docx, or a text file. Gives back the file's text." }),
    S("rb_file_save", "save %1 as file %2 . %3", [val("VALUE"), val("NAME"), { type:"field_dropdown", name:"EXT", options:[["md","md"],["txt","txt"],["csv","csv"],["json","json"],["html","html"]] }],
      { style:"files", inputsInline:true, tooltip:"Offers the text as a download. The browser asks you to confirm." }),
    V("rb_result_text", "the result so far", [], "String", { style:"files", tooltip:"Everything added to the result, as text." }),
    { type:"rb_try", message0:"try", message1:"%1", args1:[{ type:"input_statement", name:"DO" }],
      message2:"if it fails", message3:"%1", args3:[{ type:"input_statement", name:"FAIL" }],
      previousStatement:null, nextStatement:null, style:"control", tooltip:"Runs the first part. If anything in it fails, runs the second part instead of stopping the run." },
    { type:"rb_retry", message0:"retry up to %1 times", args0:[val("TIMES")], message1:"%1", args1:[{ type:"input_statement", name:"DO" }],
      previousStatement:null, nextStatement:null, style:"control",
      tooltip:"If something inside fails in a way a second try could fix (a dropped connection, a garbled reply), waits a little and runs it again." },
    V("rb_error", "the error", [], "String", { style:"control", tooltip:"What went wrong in the most recent failure." }),
    /* Budget and asking first */
    S("rb_budget", "limit this run to %1 tokens", [val("TOKENS")], { style:"control", inputsInline:true,
      tooltip:"Before each model call, checks how many tokens this run has used. Once it reaches this number, the run stops. 0 means no limit. On this page the count is an estimate; exported Python uses the exact counts." }),
    V("rb_tokens_used", "tokens used so far", [], "Number", { style:"control",
      tooltip:"Tokens this run has used: sent plus received. An estimate on this page, exact in exported Python." }),
    V("rb_setup_check", "this program's setup check", [], "String", { style:"control",
      tooltip:"The same checks as running the program with --doctor, as text: each key, package and connection it uses, with ok, FAIL or NOTE. It only reads: nothing is sent, switched or charged. Only in exported Python; on this page it says so." }),
    S("rb_ask_first", "ask me before %1", [{ type:"field_dropdown", name:"WHAT", options:[["any smart home action (Home Assistant, Homey, MQTT)","ha"],["sending messages and announcements","messages"],["saving files","files"],["all of these","all"]] }],
      { style:"you", tooltip:"From here on, the program shows what it's about to do and waits for you to allow it. If you say no, it skips that step and carries on. Exported Python asks in the terminal; a scheduled run with nobody there skips it." }),
    /* Agent */
    { type:"rb_agent",
      message0:"agent: work toward %1", args0:[val("GOAL")],
      message1:"up to %1 steps, using these tools:", args1:[val("STEPS")],
      message2:"%1", args2:[{ type:"input_statement", name:"TOOLS", check:"AgentTool" }],
      message3:"make a plan first, and change it as it goes %1", args3:[{ type:"field_checkbox", name:"PLAN", checked:false }],
      previousStatement:null, nextStatement:null, style:"agent",
      tooltip:"Claude decides what to do next: each step it picks one of the tools inside, sees what happened, and carries on until the goal is met or the steps run out. Its final answer goes in the draft. Each step is one model call. With 'make a plan first' ticked, it writes a short plan with its first step and keeps it up to date, at no extra cost." },
    V("rb_agent_steps", "agent's steps", [], "Array", { style:"agent",
      tooltip:"What the most recent agent in this run did: a list of records with step, tool, input, result and status (done, bad input, tool error, refused, repeat, not a tool, unreadable, empty answer, stopped, answer)." }),
    { type:"rb_agent_tool",
      message0:"tool: My Block %1", args0:[{ type:"field_input", name:"NAME", text:"my block" }],
      message1:"what it does %1", args1:[val("DESC")],
      message2:"input types %1", args2:[{ type:"field_input", name:"INPUTS", text:"" }],
      message3:"ask me before each use %1", args3:[{ type:"field_checkbox", name:"ASK", checked:true }],
      previousStatement:"AgentTool", nextStatement:"AgentTool", style:"tools",
      tooltip:"Lets the agent run one of your My Blocks. Its inputs become the tool's inputs, and what it returns is the result the agent sees. Describe it clearly: the description is all the agent knows about it. Input types, for example 'flour grams: number; water grams: number - grams of water', say what each input must be: text, number, yes/no, list or any. The agent's input is checked before the block runs. 'Ask me before each use' starts ticked, because what the agent reads (a web page, a note) could try to steer it: untick it for blocks that only work things out and change nothing." },
    { type:"rb_agent_builtin",
      message0:"tool: %1", args0:[{ type:"field_dropdown", name:"KIND", options:AGENT_TOOL_KINDS }],
      previousStatement:"AgentTool", nextStatement:"AgentTool", style:"tools",
      tooltip:"A ready-made tool for the agent. 'Work out sums' and 'clock times' get numbers and times exactly right, instead of the model guessing. 'Check text' has a separate reviewer judge the agent's work. On this page, feeds, GitHub, Telegram, email and the calendar use sample data; exported Python uses your own (put the keys in second-thought.ini), and reads web pages for real. Sending, commenting and 'control devices' ask you before each one, because what the agent reads (a web page, a note) could try to steer it. Choose 'no asking' only if you trust everything it reads. Unlocking, opening and disarming always ask." },
    { type:"rb_agent_mcp",
      message0:"tools from MCP server %1 %2", args0:[{ type:"field_input", name:"SERVER", text:"files" },
        { type:"field_dropdown", name:"ASK", options:[["(asks me before tools that change things)","changes"],["(asks me before every tool)","every"],["(no asking)","never"]] }],
      previousStatement:"AgentTool", nextStatement:"AgentTool", style:"tools",
      tooltip:"Gives the agent every tool an MCP server offers: files, GitHub, databases, calendars and much more, from the whole MCP ecosystem. " +
        "Set the server up in second-thought.ini as MCP_<NAME> = the command that starts it (like npx -y @modelcontextprotocol/server-filesystem ~/recipes) " +
        "or its https:// address. Only in exported Python: on this page the agent works without these tools." },
    /* Connections */
    { type:"rb_tg_when", message0:"when a Telegram message arrives containing %1", args0:[{ type:"field_input", name:"CONTAINS", text:"anything" }],
      nextStatement:null, style:"conn_hat",
      tooltip:"Runs the blocks below when your bot gets a message (type 'anything', or words the message must contain). Only messages from your own chats count (TELEGRAM_CHAT_ID). In exported Python it listens all the time; on this page, right-click it and choose 'Run this script' to try it with a sample message." },
    V("rb_tg_message", "Telegram message %1", [{ type:"field_dropdown", name:"PART", options:[["text","text"],["sender","sender"],["chat","chat"]] }], "String",
      { style:"conn", tooltip:"The Telegram message that started this script: its words, who sent it, or the chat. Empty outside a Telegram script." }),
    S("rb_tg_send", "send Telegram message %1", [val("TEXT")], { style:"conn", inputsInline:true,
      tooltip:"Sends a message from your bot: back to the chat a message came from, or to TELEGRAM_CHAT_ID. 'Ask me before sending messages' makes it ask first. On this page it's only shown." }),
    { type:"rb_discord_when", message0:"when a Discord message arrives containing %1", args0:[{ type:"field_input", name:"CONTAINS", text:"anything" }],
      nextStatement:null, style:"conn_hat",
      tooltip:"Runs the blocks below when someone posts in one of your Discord channels (type 'anything', or words the message must contain). Only the channels in DISCORD_CHANNEL_ID count, and the bot's own messages never do. Checked every 10 seconds. 'What arrived' gives text, sender and channel. On this page, right-click it and choose 'Run this script' to try it with a sample message." },
    { type:"rb_slack_when", message0:"when a Slack message arrives containing %1", args0:[{ type:"field_input", name:"CONTAINS", text:"anything" }],
      nextStatement:null, style:"conn_hat",
      tooltip:"Runs the blocks below when someone posts in one of your Slack channels (type 'anything', or words the message must contain). Only the channels in SLACK_CHANNEL_ID count, and bots' messages never do. Checked every 10 seconds. 'What arrived' gives text, sender and channel. On this page, right-click it and choose 'Run this script' to try it with a sample message." },
    S("rb_discord_send", "send Discord message %1", [val("TEXT")], { style:"conn", inputsInline:true,
      tooltip:"Posts in Discord: back in the channel a message came from, or in the first channel in DISCORD_CHANNEL_ID. 'Ask me before sending messages' makes it ask first. On this page it's only shown." }),
    S("rb_slack_send", "send Slack message %1", [val("TEXT")], { style:"conn", inputsInline:true,
      tooltip:"Posts in Slack: back in the channel a message came from, or in the first channel in SLACK_CHANNEL_ID. 'Ask me before sending messages' makes it ask first. On this page it's only shown." }),
    V("rb_feed_news", "news from feed %1", [val("URL")], "Array", { style:"conn", inputsInline:true,
      tooltip:"The latest items from a news feed (RSS or Atom), newest first, as records: feed, title, link, date, summary. Leave it empty for your own feeds (feeds = … in second-thought.ini). On this page it uses sample feeds." }),
    V("rb_folder_files", "files in folder %1 matching %2", [val("FOLDER"), val("MATCH")], "Array", { style:"conn", inputsInline:true,
      tooltip:"The files in a folder, newest first, as records: name, path, modified and size. Matching is a pattern like *.pdf; leave it empty for every file. It only looks: it doesn't read them. Exported Python looks in the folder (next to the program, unless you give a full path); this page uses sample files." }),
    V("rb_calendar", "calendar for the next %1 days", [val("DAYS")], "Array", { style:"conn", inputsInline:true,
      tooltip:"Your calendar's events from today, as records: day, start, end, title, location. Exported Python reads CALENDAR_URL (your calendar's private iCal address); this page uses a sample calendar." }),
    S("rb_email_send", "send email to %1 subject %2 %3", [val("TO"), val("SUBJECT"), val("TEXT")], { style:"conn",
      tooltip:"Sends an email from your address (EMAIL_ADDRESS and an app password in second-thought.ini). 'Ask me before sending messages' makes it ask first. On this page it's only shown." }),
    { type:"rb_mqtt_when", message0:"when an MQTT message arrives on %1", args0:[{ type:"field_input", name:"TOPIC", text:"home/+/temperature" }],
      nextStatement:null, style:"conn_hat",
      tooltip:"Runs the blocks below when a message arrives on this MQTT topic. + stands for one level and # for everything below, like zigbee2mqtt/#. 'What arrived' gives its topic and text, plus the fields of a JSON message." },
    { type:"rb_webhook_when", message0:"when a web request arrives at / %1", args0:[{ type:"field_input", name:"PATH", text:"bake-done" }],
      nextStatement:null, style:"conn_hat",
      tooltip:"Runs the blocks below when something (Home Assistant, IFTTT, a shortcut on your phone) calls http://<this computer>:8765/bake-done?key=<WEBHOOK_SECRET>. Requests without the key are refused. 'What arrived' gives the text sent, and the fields of JSON or of the address." },
    { type:"rb_email_when", message0:"when an email arrives containing %1", args0:[{ type:"field_input", name:"CONTAINS", text:"anything" }],
      nextStatement:null, style:"conn_hat",
      tooltip:"Runs the blocks below when a new email arrives in your inbox (checked every 2 minutes), if its sender, subject or words contain this. 'What arrived' gives from, subject, body and text." },
    { type:"rb_feed_when", message0:"when there's something new in feed %1", args0:[{ type:"field_input", name:"URL", text:"" }],
      nextStatement:null, style:"conn_hat",
      tooltip:"Runs the blocks below for each new item in a news feed (checked every 15 minutes). Leave it empty for your own feeds. 'What arrived' gives feed, title, link, date, summary and text." },
    { type:"rb_folder_when", message0:"when a file appears in folder %1", args0:[{ type:"field_input", name:"FOLDER", text:"inbox" }],
      nextStatement:null, style:"conn_hat",
      tooltip:"Runs the blocks below when a new file lands in this folder (next to the program, unless you give a full path). 'What arrived' gives its name, path, size, and the words in it for a PDF, Word or text file. For a picture, 'picture' gives it to the picture blocks." },
    { type:"rb_gh_when", message0:"when a pull request asks for my review", nextStatement:null, style:"conn_hat",
      tooltip:"Runs the blocks below when someone asks you to review a GitHub pull request (checked every 5 minutes). 'What arrived' gives repo, number, title, user, link and text." },
    { type:"rb_gh_issue_when", message0:"when a new issue is opened in %1", args0:[{ type:"field_input", name:"REPO", text:"owner/name" }], nextStatement:null, style:"conn_hat",
      tooltip:"Runs the blocks below when someone opens an issue in this GitHub project (checked every 5 minutes; pull requests don't count). 'What arrived' gives repo, number, title, body, author, labels, link and text." },
    { type:"rb_gh_release_when", message0:"when a release is published in %1", args0:[{ type:"field_input", name:"REPO", text:"owner/name" }], nextStatement:null, style:"conn_hat",
      tooltip:"Runs the blocks below when this GitHub project publishes a release (checked every 15 minutes). 'What arrived' gives repo, tag, name, previous_tag, notes, link and text." },
    { type:"rb_cal_when", message0:"when a calendar event starts in %1 minutes", args0:[{ type:"field_number", name:"N", value:15, min:0, max:1440 }],
      nextStatement:null, style:"conn_hat",
      tooltip:"Runs the blocks below this many minutes before each event in your calendar (all-day events don't count). 'What arrived' gives title, start, end, location, minutes and text." },
    { type:"rb_page_when", message0:"when the web page %1 changes", args0:[{ type:"field_input", name:"URL", text:"https://example.com/shop/rye-flour" }],
      message1:"only the part containing %1 checked every %2 minutes", args1:[{ type:"field_input", name:"WORDS", text:"" }, { type:"field_number", name:"N", value:60, min:1, max:1440, precision:1 }],
      nextStatement:null, style:"conn_hat",
      tooltip:"Runs the blocks below when the words on a web page change. Leave 'only the part containing' empty to watch the whole page, or type words (like Price) to watch just the lines with them and the two lines after each, so adverts and counters elsewhere on the page don't count. The first check only remembers the page. 'What arrived' gives url, title, before, after, changed (the lines that changed) and text. Pages that need a browser to show their words can't be watched. On this page, right-click it and choose 'Run this script' to try it with a sample page." },
    V("rb_event", "what arrived: %1", [{ type:"field_input", name:"KEY", text:"text" }], null, { style:"conn",
      tooltip:"Inside a 'when … arrives' script: one field of what arrived. Every listener gives 'text', which sums it up; the tooltip on each 'when' block lists its other fields. Leave it empty for the whole record." }),
    V("rb_mqtt_read", "latest MQTT message on %1", [val("TOPIC")], null, { style:"conn", inputsInline:true,
      tooltip:"The latest message on an MQTT topic. Only messages the broker keeps (retained) show up straight away. With + or # in the topic, a record of each topic's latest message. On this page it uses sample topics." }),
    S("rb_mqtt_publish", "publish MQTT %1 to topic %2 keep it %3", [val("TEXT"), val("TOPIC"), { type:"field_checkbox", name:"RETAIN", checked:false }],
      { style:"conn", inputsInline:true, tooltip:"Sends a message to your MQTT broker. 'Keep it' asks the broker to remember it for anyone who listens later. 'Ask me before any Home Assistant action' or 'sending messages' makes it ask first. On this page it's only shown." }),
    /* Homey */
    { type:"rb_homey_when", message0:"when Homey device %1 %2 changes", args0:[{ type:"field_input", name:"DEVICE", text:"Washing machine" }, { type:"field_input", name:"CAPABILITY", text:"measure_power" }],
      nextStatement:null, style:"homey_hat",
      tooltip:"Runs the blocks below when this Homey device's value changes (checked every 10 seconds). Type 'anything' for any of its values. 'What arrived' gives device, zone, capability, from, to and text. On this page, right-click it and choose 'Run this script' to try it." },
    V("rb_homey_value", "%1 of Homey device %2", [val("CAPABILITY"), val("DEVICE")], null, { style:"homey", inputsInline:true,
      tooltip:"One value of a Homey device, by the device's name: onoff (on or off), dim (0 to 1), measure_temperature, measure_power and so on. 'Homey devices matching' shows what each device has." }),
    V("rb_homey_find", "Homey devices matching %1", [val("TEXT")], "Array", { style:"homey", inputsInline:true,
      tooltip:"A list of records, one for each device whose name, zone or kind contains all these words ('*' for every device): name, zone, class, and each of its values." }),
    S("rb_homey_set", "set Homey device %1 %2 to %3", [val("DEVICE"), val("CAPABILITY"), val("VALUE")], { style:"homey", inputsInline:true,
      tooltip:"Sets a value, like onoff to off, dim to 0.5 or target_temperature to 19. 'Ask me before any smart home action' makes it ask first; unlocking, opening and disarming always ask. On this page it changes the sample home." }),
    S("rb_homey_flow", "run Homey flow %1", [val("NAME")], { style:"homey", inputsInline:true,
      tooltip:"Starts one of your Homey flows, by its name. A flow can do anything your Homey can, including sending a Homey notification." }),
    V("rb_homey_variable", "Homey variable %1", [val("NAME")], null, { style:"homey", inputsInline:true, tooltip:"The value of a Homey Logic variable, by its name." }),
    S("rb_homey_set_variable", "set Homey variable %1 to %2", [val("NAME"), val("VALUE")], { style:"homey", inputsInline:true,
      tooltip:"Changes a Homey Logic variable, so your flows can use it." }),
    /* Programs */
    V("rb_run_program", "run program %1 with %2", [{ type:"field_input", name:"NAME", text:"my program" }, val("VALUE")], "String", { style:"procedure_blocks", inputsInline:true,
      tooltip:"Runs a program from your Programs list, as a step. It gets its own draft, result and variables, and gives back its result. Inside it, 'message value' is the value you pass here. Exported Python includes a copy of the program as it was when you exported." }),
    /* Memory */
    S("rb_mem_set", "remember %1 as %2 %3", [val("VALUE"), val("NAME"),
      { type:"field_dropdown", name:"KIND", options:[["while this page is open","transient"],["forever","permanent"]] }],
      { style:"memory", inputsInline:true, tooltip:"While this page is open: kept across runs until you reload or close the page. Forever: saved until you forget it." }),
    S("rb_mem_set_for", "remember %1 as %2 for %3 %4", [val("VALUE"), val("NAME"), val("N"),
      { type:"field_dropdown", name:"UNIT", options:[["minutes","m"],["hours","h"],["days","d"]] }],
      { style:"memory", inputsInline:true, tooltip:"Saved like 'forever', but forgotten automatically after this long (up to 365 days)." }),
    S("rb_mem_add", "add %1 to remembered list %2 %3", [val("VALUE"), val("NAME"),
      { type:"field_dropdown", name:"KIND", options:[["while this page is open","transient"],["forever","permanent"]] }],
      { style:"memory", inputsInline:true, tooltip:"Adds an item to a remembered list. If the list already exists it keeps its own kind and expiry." }),
    S("rb_mem_forget", "forget %1", [val("NAME")], { style:"memory", inputsInline:true }),
    V("rb_mem_get", "recall %1", [val("NAME")], null, { style:"memory", inputsInline:true, tooltip:"The remembered value, or empty text if nothing is remembered under this name." }),
    V("rb_mem_has", "I remember %1", [val("NAME")], "Boolean", { style:"memory", inputsInline:true }),
    V("rb_mem_names", "names I remember", [], "Array", { style:"memory" }),
    /* Pictures */
    V("rb_img_choose", "picture I choose", [], "Picture", { style:"pictures", tooltip:"Pauses the run so you can pick a picture (JPEG, PNG, WebP, GIF or SVG)." }),
    V("rb_img_draw", "draw a picture of %1", [val("TEXT")], "Picture", { style:"pictures", inputsInline:true,
      tooltip:"Claude draws an illustration as SVG (flat shapes, diagrams, icons). It can't make photos." }),
    V("rb_img_change", "change picture %1 : %2", [val("IMG"), val("TEXT")], "Picture", { style:"pictures", inputsInline:true,
      tooltip:"Claude redraws the picture with your change. A photo comes back as a new illustration." }),
    V("rb_img_ask", "ask Claude %1 about picture %2", [val("TEXT"), val("IMG")], "String", { style:"pictures", inputsInline:true, tooltip:"Claude looks at the picture and answers." }),
    V("rb_img_score", "score picture %1 out of 10 for %2", [val("IMG"), val("CRITERIA")], "Number", { style:"pictures", inputsInline:true }),
    S("rb_img_show", "show picture %1", [val("IMG")], { style:"pictures", inputsInline:true }),
    S("rb_img_save", "save picture %1 as %2", [val("IMG"), { type:"field_dropdown", name:"FORMAT", options:[["PNG","png"],["SVG (drawn pictures)","svg"],["original file","orig"]] }],
      { style:"pictures", inputsInline:true, tooltip:"Offers the picture as a download. The browser asks you to confirm." })
  ]);

