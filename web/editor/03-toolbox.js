  // 03-toolbox.js: The block palette (toolbox) and its categories.
  /* ---------- Toolbox ---------- */
  // The words already in the palette's blocks are in the page's language ("starters" in i18n/<language>.json). K() is
  // for text that must stay as it is: entity ids, topics, message names, and the sample home's own device names.
  const STARTERS = new Set();
  const starter = t => { STARTERS.add(t); return (window.ST_I18N && I18N.starters && I18N.starters[t]) || t; };
  const T = t => ({ shadow:{ type:"text", fields:{ TEXT:t ? starter(t) : t } } });
  const L = t => ({ shadow:{ type:"rb_longtext", fields:{ TEXT:t ? starter(t) : t } } });
  const K = t => ({ shadow:{ type:"text", fields:{ TEXT:t } } });
  window.__starters = () => [...STARTERS];
  const N = n => ({ shadow:{ type:"math_number", fields:{ NUM:n } } });
  const B = (type, inputs, extra) => Object.assign({ kind:"block", type }, inputs ? { inputs } : {}, extra || {});
  const toolbox = { kind:"categoryToolbox", contents:[
    { kind:"category", name:"Events", categorystyle:"events", contents:[
      B("rb_start"), B("rb_when_time"), B("rb_every"),
      B("rb_receive"), B("rb_broadcast", { MSG:K("message1") }), B("rb_broadcast_wait", { MSG:K("message1") }),
      B("rb_broadcast_with", { MSG:K("message1"), VALUE:T("hello") }), B("rb_broadcast_with_wait", { MSG:K("message1"), VALUE:T("hello") }), B("rb_msg_value")
    ]},
    { kind:"category", name:"Control", categorystyle:"control", contents:[
      B("controls_repeat_ext", { TIMES:N(3) }), B("controls_whileUntil"), B("controls_if"),
      B("controls_if", null, { extraState:{ hasElse:true } }),
      B("controls_forEach"), B("controls_for", { FROM:N(1), TO:N(5), BY:N(1) }), B("controls_flow_statements"),
      B("rb_wait", { SECS:N(1) }), B("rb_wait_until"), B("rb_try"), B("rb_retry", { TIMES:N(3) }), B("rb_error"), B("rb_budget", { TOKENS:N(50000) }), B("rb_tokens_used"), B("rb_setup_check"), B("rb_use_model"), B("rb_with_model", null, { fields:{ TIER:"gemini-default" } }), B("rb_with_any_model"), B("rb_stop")
    ]},
    { kind:"category", name:"Wait & time", categorystyle:"time", contents:[
      B("rb_wait", { SECS:N(5) }, { fields:{ UNIT:"m" } }), B("rb_wait_until"), B("rb_wait_time"), B("rb_wait_msg"),
      B("rb_pause", { TEXT:T("Check the draft, then continue") }), B("rb_timer"), B("rb_reset_timer"), B("rb_now")
    ]},
    { kind:"category", name:"Operators", categorystyle:"operators", contents:[
      B("math_arithmetic", { A:N(1), B:N(1) }), B("math_random_int", { FROM:N(1), TO:N(10) }), B("math_round", { NUM:N(3.1) }),
      B("math_modulo", { DIVIDEND:N(10), DIVISOR:N(3) }), B("math_number"),
      B("logic_compare"), B("logic_operation"), B("logic_negate"), B("logic_boolean"), B("logic_ternary"),
      B("rb_contains", { A:T("sourdough"), B:T("dough") })
    ]},
    { kind:"category", name:"Text", categorystyle:"text", contents:[
      B("text"), B("rb_longtext", null, { fields:{ TEXT:"Long text.\nPress Enter for a new line." } }), B("text_join"), B("text_length", { VALUE:K("abc") }), B("text_isEmpty"),
      B("text_changeCase", { TEXT:K("abc") }), B("rb_word_count", { TEXT:T("one two three") })
    ]},
    { kind:"category", name:"Variables", categorystyle:"variables", custom:"VARIABLE" },
    { kind:"category", name:"Lists", categorystyle:"lists", contents:[
      B("lists_create_empty"), B("lists_create_with"), B("lists_length"), B("lists_isEmpty"),
      B("lists_getIndex"), B("lists_setIndex", null, { fields:{ MODE:"INSERT", WHERE:"LAST" } })
    ]},
    { kind:"category", name:"My Blocks", categorystyle:"procedures", custom:"PROCEDURE" },
    { kind:"category", name:"Programs", categorystyle:"procedures", contents:[
      B("rb_run_program", { VALUE:T("") }), B("rb_msg_value")
    ]},
    { kind:"category", name:"Search results", categorystyle:"search", custom:"SEARCH" },
    { kind:"sep" },
    { kind:"category", name:"Draft", categorystyle:"draft", contents:[
      B("rb_task", { TEXT:L("Describe the job here") }), B("rb_generate"), B("rb_rework", { TEXT:L("make it friendlier") }),
      B("rb_revise"), B("rb_set_draft", { TEXT:T("") }), B("rb_draft"), B("rb_task_get"),
      B("rb_checkpoint_save"), B("rb_checkpoint_restore")
    ]},
    { kind:"category", name:"Ask Claude", categorystyle:"claude", contents:[
      B("rb_ask", { TEXT:L("Suggest a name for a sourdough starter") }),
      B("rb_ask_yesno", { TEXT:T("Is rye flour gluten free?") }),
      B("rb_ask_number", { TEXT:T("Typical hydration % for a beginner loaf") }),
      B("rb_ask_list", { TEXT:T("5 common sourdough mistakes") }),
      B("rb_rewrite", { HOW:T("make it shorter") }), B("rb_extract", { WHAT:T("the key steps") }),
      { kind:"sep", gap:"24" },
      B("rb_set_instructions", { TEXT:L("You write for home bakers: warm, practical, British spelling.") }), B("rb_clear_instructions"),
      B("rb_chat", { NAME:T("editor"), TEXT:L("Here is my draft. What should I fix first?") }), B("rb_chat_reset", { NAME:T("editor") }),
      B("rb_prompt"), B("rb_web_search", { TEXT:T("current price of rye flour in the UK") })
    ]},
    { kind:"category", name:"Review", categorystyle:"review", contents:[
      B("rb_reflect", { CRITERIA:L("accurate; clear; under 200 words"), ROUNDS:N(3) }),
      B("rb_review", { CRITERIA:L("accurate; clear") }), B("rb_passed"), B("rb_problems"),
      B("rb_score", { CRITERIA:T("clear and accurate") }), B("rb_better", { CRITERIA:T("clarity") })
    ]},
    { kind:"category", name:"Agent", categorystyle:"agent", contents:[
      B("rb_agent", { GOAL:L("Plan a bake for this weekend that suits what I have in"), STEPS:N(6),
        TOOLS:{ block:{ type:"rb_agent_builtin", fields:{ KIND:"ask" }, next:{ block:{ type:"rb_agent_builtin", fields:{ KIND:"memory" } } } } } }, { fields:{ PLAN:true } }),
      B("rb_agent_steps")
    ]},
    { kind:"category", name:"Tools", categorystyle:"tools", contents:[
      { kind:"label", text:"Tools for the agent: drop them inside an agent block" },
      ...AGENT_TOOL_KINDS.map(([, kind]) => B("rb_agent_builtin", null, { fields:{ KIND:kind } })),
      B("rb_agent_mcp"),
      B("rb_agent_tool", { DESC:L("Gives the oven temperature in °C for a bread type.") })
    ]},
    { kind:"category", name:"Connections", categorystyle:"conn", contents:[
      { kind:"label", text:"Listeners: they run while the exported program runs on schedule" },
      B("rb_tg_when"), B("rb_discord_when"), B("rb_slack_when"), B("rb_mqtt_when"), B("rb_webhook_when"), B("rb_email_when"), B("rb_feed_when"), B("rb_folder_when"), B("rb_gh_when"), B("rb_gh_issue_when"), B("rb_gh_release_when"), B("rb_cal_when"), B("rb_page_when"),
      B("rb_event"), B("rb_tg_message"),
      { kind:"label", text:"Read and send" },
      B("rb_mqtt_read", { TOPIC:K("home/kitchen/temperature") }), B("rb_mqtt_publish", { TEXT:K("ON"), TOPIC:K("zigbee2mqtt/oven_plug/set") }),
      B("rb_tg_send", { TEXT:L("Your loaf is ready to come out.") }),
      B("rb_discord_send", { TEXT:L("The bake-along starts in 10 minutes.") }), B("rb_slack_send", { TEXT:L("The oven's free now.") }),
      B("rb_feed_news", { URL:T("") }), B("rb_calendar", { DAYS:N(7) }), B("rb_folder_files", { FOLDER:K("inbox"), MATCH:K("*.pdf") }),
      B("rb_email_send", { TO:K("someone@example.com"), SUBJECT:T("Bake plan"), TEXT:L("Here's the plan for Saturday.") })
    ]},
    { kind:"category", name:"You", categorystyle:"you", contents:[
      B("rb_ask_me", { TEXT:T("What should I write about?") }), B("rb_answer"), B("rb_approve"), B("rb_choose"), B("rb_ask_first")
    ]},
    { kind:"category", name:"Records", categorystyle:"records", contents:[
      B("rb_rec_new"), B("rb_rec_set", { KEY:T("score"), VALUE:N(0) }), B("rb_rec_get", { KEY:T("score") }), B("rb_rec_has", { KEY:T("score") }), B("rb_rec_keys"),
      B("rb_ask_record", { FIELDS:T("name, hydration, notes"), TEXT:L("A beginner sourdough recipe") }),
      B("rb_ask_records", { FIELDS:T("title, score, why"), TEXT:L("5 blog post ideas about rye bread, scored 1-10 for search interest") }),
      B("rb_sort", { KEY:T("score") })
    ]},
    { kind:"category", name:"Files", categorystyle:"files", contents:[
      B("rb_file_choose"), B("rb_file_save", { NAME:T("summary") }), B("rb_result_text")
    ]},
    { kind:"category", name:"Memory", categorystyle:"memory", contents:[
      B("rb_mem_set", { NAME:T("note") }), B("rb_mem_set_for", { NAME:T("today's draft"), N:N(1) }, { fields:{ UNIT:"d" } }),
      B("rb_mem_add", { NAME:T("used headlines") }, { fields:{ KIND:"permanent" } }),
      B("rb_mem_get", { NAME:T("note") }), B("rb_mem_has", { NAME:T("note") }), B("rb_mem_forget", { NAME:T("note") }), B("rb_mem_names")
    ]},
    { kind:"category", name:"Pictures", categorystyle:"pictures", contents:[
      B("rb_img_choose"),
      B("rb_img_draw", { TEXT:L("a sourdough loaf with a crisp ear, flat illustration") }),
      B("rb_img_change", { TEXT:L("make the crust darker") }),
      B("rb_img_ask", { TEXT:L("Describe this picture in one sentence.") }),
      B("rb_img_score", { CRITERIA:L("clear, appealing, easy to read at small size") }),
      B("rb_img_show"), B("rb_img_save")
    ]},
    { kind:"category", name:"Home Assistant", categorystyle:"ha", contents:[
      B("rb_ha_when"), B("rb_ha_trigger"), B("rb_ha_event_when"), B("rb_event"),
      B("rb_ha_state", { ENTITY:K("sensor.living_room_temperature") }), B("rb_ha_attr", { ATTR:K("current_temperature"), ENTITY:K("climate.living_room") }),
      B("rb_ha_summary", { TEXT:K("temperature") }), B("rb_ha_find", { TEXT:K("light") }),
      B("rb_ha_history", { ENTITY:K("sensor.bathroom_humidity"), HOURS:N(24) }), B("rb_ha_snapshot", { CAMERA:K("camera.front_door") }),
      B("rb_ha_call", { SERVICE:K("light.turn_off"), ENTITY:K("light.kitchen"), DATA:T("") }),
      B("rb_ha_notify", { TARGET:K("persistent_notification"), TEXT:L("The back door is still open.") }),
      B("rb_ha_speak", { TEXT:L("Good morning!"), PLAYER:K("media_player.kitchen_speaker") })
    ]},
    { kind:"category", name:"Homey", categorystyle:"homey", contents:[
      B("rb_homey_when"), B("rb_event"),
      B("rb_homey_find", { TEXT:K("light") }), B("rb_homey_value", { CAPABILITY:K("measure_temperature"), DEVICE:K("Proofing box") }),
      B("rb_homey_set", { DEVICE:K("Kitchen light"), CAPABILITY:K("onoff"), VALUE:K("off") }), B("rb_homey_flow", { NAME:K("Good night") }),
      B("rb_homey_variable", { NAME:K("Loaves this week") }), B("rb_homey_set_variable", { NAME:K("Loaves this week"), VALUE:N(4) })
    ]},
    { kind:"category", name:"Output", categorystyle:"output", contents:[
      B("rb_say", { TEXT:T("Hello") }), B("rb_show"), B("rb_add_result"), B("rb_result"), B("rb_finish_with")
    ]}
  ]};

