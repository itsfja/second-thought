  // 17-agent.js: The agent and its built-in tools.
  /* ---------- Agent ----------
     Each step Claude replies with JSON: a tool to use, or its final answer. Exported Python runs the same protocol
     (Runtime.agent), so a program behaves the same in both places, with any model. */
  const AGENT_BUILTINS = {
    web:[["search_web", "Search the web and get a short answer with sources. Use for facts that change, like prices or opening times.", ["query"]],
         ["read_page", "Read the words on one public web page, from its address (starting http:// or https://). Use it to check a source properly.", ["url"]]],
    ask:[["ask_me", "Ask the person running this program a question and wait for their answer. Use it for things only they know, or to check a decision.", ["question"]]],
    memory:[["remember", "Save a note under a name. It is kept between runs.", ["name", "value"]],
            ["recall", "Get the note saved under a name. Gives nothing if there isn't one.", ["name"]],
            ["list_memory", "List the names of every saved note.", []],
            ["search_memory", "Find saved notes about something, best matches first, by the words in their names and contents. Use it when you don't know a note's exact name, or there are many notes.", ["query"]]],
    ha_read:[["find_devices", "Find Home Assistant devices and sensors matching some words, with their current states.", ["search"]],
             ["device_state", "Get the current state of one Home Assistant entity, by its entity id (like sensor.kitchen_temperature).", ["entity"]],
             ["device_history", "See how one Home Assistant entity changed over the past hours (24 if you don't say; at most 168), as a list of times and states.", ["entity", "hours"]]],
    ha_act:[["call_service", "Call a Home Assistant service, like light.turn_off on light.kitchen. data is optional JSON. The person may be asked first, and may say no.", ["service", "entity", "data"]]],
    calc:[["calculate", "Work out a sum exactly, like (350 / 500) * 100 or round(1000 * 0.02, 1). Use it for every sum instead of working it out yourself. It knows + - * / ^, brackets, pi, and round(x, places), min, max, sqrt, abs, floor, ceil.", ["expression"]]],
    time:[["current_time", "Get the day, date and time now.", []],
          ["time_plus", "Add minutes to a clock time and get the new time, like 09:30 plus 270 gives 14:00. Use a negative number to go back. time is HH:MM, or YYYY-MM-DD HH:MM to get the date and day too. Use it for every clock time instead of working it out yourself.", ["time", "minutes"]]],
    file:[["read_file", "Ask the person to choose a file (a PDF, a Word file or a text file) and get the words in it. Say why you want it.", ["why"]]],
    review:[["review_text", "Have a separate, strict reviewer check some text against criteria (separate them with semicolons). It says whether the text passes, and lists each problem. Use it to check your work before you finish.", ["text", "criteria"]]],
    feeds:[["read_feed", "Get the latest items from a news feed (RSS or Atom) by its address, or from the person's own feeds if you leave url empty. Each item has a title, date, link and summary. limit is items per feed (10 if you don't say).", ["url", "limit"]]],
    linkedin:[["search_linkedin", "Search LinkedIn's public pages (people, companies, posts) through a web search. It only finds what LinkedIn shows to everyone.", ["query"]]],
    github:[["my_pull_requests", "List the GitHub pull requests waiting for the person's review, and their own open ones.", []],
        ["list_pull_requests", "List the pull requests in one GitHub project (owner/name). state is open, closed or all (open if you don't say).", ["repo", "state"]],
        ["read_pull_request", "Read one pull request: its description, the files it changes with the changes themselves, and its comments.", ["repo", "number"]],
        ["list_projects", "List GitHub projects, most recently changed first: the person's own, or another owner's if you give one.", ["owner"]],
        ["search_github", "Search GitHub issues and pull requests, with GitHub's search words, like 'is:open is:issue repo:owner/name label:bug'.", ["query"]],
        ["list_branches", "List one GitHub project's branches, oldest last commit first, each with when and by whom it was last changed, and any open pull request from it.", ["repo"]],
        ["list_commits", "List commits on a GitHub project's main branch, newest first. author is a GitHub login, or me for the person (anyone if you leave it empty); since is today, yesterday, a number of days or YYYY-MM-DD (7 days if you don't say).", ["repo", "author", "since"]],
        ["read_github_file", "Read one file in a GitHub project, like README.md, or list a folder's contents (leave path empty for the top folder). ref is a branch, tag or commit (the main branch if you don't say).", ["repo", "path", "ref"]]],
    github_act:[["comment_on_github", "Post a comment on a GitHub pull request or issue. The person is asked first, and may say no.", ["repo", "number", "text"]],
        ["open_issue", "Open a new issue in a GitHub project. The person is asked first, and may say no.", ["repo", "title", "body"]],
        ["add_labels", "Add labels to a GitHub issue or pull request. Only labels the project already has work; if one doesn't, you're told which it has. The person is asked first, and may say no.", ["repo", "number", "labels"]]],
    telegram:[["search_telegram", "Search the Telegram messages the person has sent to their bot, newest first. Leave text empty for the latest.", ["text"]]],
    telegram_send:[["send_telegram", "Send a Telegram message to the person (or back to the chat a message came from). The person may be asked first, and may say no.", ["text"]]],
    email:[["search_email", "Search the person's email inbox for recent emails containing some words (or all recent ones if you leave query empty). days is how far back (7 if you don't say). Gives each email's id, date, sender, subject and start.", ["query", "days"]],
        ["read_email", "Read one email in full, by its id from search_email.", ["id"]]],
    email_send:[["send_email", "Send an email from the person's address. The person is asked first, and may say no.", ["to", "subject", "body"]]],
    calendar:[["calendar", "List the person's calendar events, from a day (today, tomorrow, a weekday or YYYY-MM-DD) for some days (7 if you don't say).", ["day", "days"]],
        ["free_time", "Find free time on one day, between two times (09:00 and 17:30 if you don't say), at least some minutes long (60 if you don't say).", ["day", "from", "to", "minutes"]]],
    mqtt:[["read_mqtt", "Get the latest MQTT messages on a topic (+ and # wildcards work, like zigbee2mqtt/+). Messages the broker keeps show up straight away; others only if one arrives within 2 seconds.", ["topic"]]],
    mqtt_act:[["publish_mqtt", "Publish a message to an MQTT topic, for example to switch something. retain asks the broker to keep it. The person may be asked first, and may say no.", ["topic", "message", "retain"]]],
    homey_read:[["find_homey_devices", "Find Homey devices whose name, zone or kind contain some words (leave search empty for all), with every value they report, like onoff, dim, measure_temperature or measure_power.", ["search"]],
        ["list_homey_flows", "List the person's Homey flows by name.", []],
        ["homey_variable", "Get the value of one of the person's Homey Logic variables, by name.", ["name"]]],
    homey_act:[["set_homey_device", "Set one value of a Homey device, by the device's name: for example onoff to on, dim to 0.5, or target_temperature to 19. The person may be asked first, and may say no. Unlocking, opening and disarming always ask.", ["device", "capability", "value"]],
        ["run_homey_flow", "Start one of the person's Homey flows, by its name. The person may be asked first, and may say no.", ["flow"]]]
  };
  AGENT_BUILTINS.ha_act_free = AGENT_BUILTINS.ha_act;
  AGENT_BUILTINS.telegram_send_free = AGENT_BUILTINS.telegram_send;
  [["discord", "Discord"], ["slack", "Slack"]].forEach(([svc, name]) => {
    AGENT_BUILTINS[svc] = [["search_" + svc, "Search the recent messages in the person's " + name + " channels, newest first. Leave text empty for the latest.", ["text"]]];
    AGENT_BUILTINS[svc + "_send"] = AGENT_BUILTINS[svc + "_send_free"] = [["send_" + svc, "Send a " + name + " message to the person's channel (or back to the channel a message came from). The person may be asked first, and may say no.", ["text"]]];
  });
  AGENT_BUILTINS.mqtt_act_free = AGENT_BUILTINS.mqtt_act;
  AGENT_BUILTINS.homey_act_free = AGENT_BUILTINS.homey_act;
  const AGENT_ASKS = new Set(SAFETY.agent_asks);  // built-in tools that ask before each use
  const MAX_AGENT_STEPS = 20;
  // The type of each built-in tool's inputs; every input is required unless listed in AGENT_OPTIONAL. Matches the runtime.
  const AGENT_INPUT_TYPES = { search_web:{ query:"text" }, ask_me:{ question:"text" }, remember:{ name:"text", value:"text" }, recall:{ name:"text" },
    list_memory:{}, search_memory:{ query:"text" }, find_devices:{ search:"text" }, device_state:{ entity:"text" }, call_service:{ service:"text", entity:"text", data:"any" },
    read_page:{ url:"text" }, device_history:{ entity:"text", hours:"number" }, calculate:{ expression:"text" }, current_time:{},
    time_plus:{ time:"text", minutes:"number" }, read_file:{ why:"text" }, review_text:{ text:"text", criteria:"text" },
    read_feed:{ url:"text", limit:"number" }, search_linkedin:{ query:"text" }, my_pull_requests:{}, list_pull_requests:{ repo:"text", state:"text" }, read_pull_request:{ repo:"text", number:"number" }, list_projects:{ owner:"text" }, search_github:{ query:"text" }, comment_on_github:{ repo:"text", number:"number", text:"text" }, list_branches:{ repo:"text" }, list_commits:{ repo:"text", author:"text", since:"text" },
    read_github_file:{ repo:"text", path:"text", ref:"text" }, open_issue:{ repo:"text", title:"text", body:"text" }, add_labels:{ repo:"text", number:"number", labels:"list" }, search_telegram:{ text:"text" }, send_telegram:{ text:"text" }, search_discord:{ text:"text" }, send_discord:{ text:"text" }, search_slack:{ text:"text" }, send_slack:{ text:"text" }, search_email:{ query:"text", days:"number" }, read_email:{ id:"text" }, send_email:{ to:"text", subject:"text", body:"text" }, calendar:{ day:"text", days:"number" }, free_time:{ day:"text", "from":"text", to:"text", minutes:"number" },
    read_mqtt:{ topic:"text" }, publish_mqtt:{ topic:"text", message:"text", retain:"yes/no" },
    find_homey_devices:{ search:"text" }, list_homey_flows:{}, homey_variable:{ name:"text" }, set_homey_device:{ device:"text", capability:"text", value:"any" }, run_homey_flow:{ flow:"text" } };
  const AGENT_OPTIONAL = { find_devices:["search"], call_service:["entity", "data"], device_history:["hours"], read_file:["why"],
    read_feed:["limit", "url"], list_pull_requests:["state"], list_projects:["owner"], list_commits:["author", "since"], read_github_file:["path", "ref"], open_issue:["body"], search_telegram:["text"], search_discord:["text"], search_slack:["text"], search_email:["days", "query"], calendar:["day", "days"], free_time:["day", "from", "minutes", "to"], publish_mqtt:["retain"], find_homey_devices:["search"] };
  const MAX_FILE_CHARS = 30000;
  /* Works out a sum like (350 / 500) * 100 exactly, without running any code. Matches the runtime's _Calc. */
  const CALC_FUNCS = ["round", "min", "max", "sqrt", "abs", "floor", "ceil"];
  function calcValue(text){
    const toks = String(text).replace(/\u00d7/g, "*").replace(/\u00f7/g, "/").match(/\d+(?:\.\d*)?|\.\d+|[A-Za-z_]+|\S/g) || [];
    let i = 0;
    const bad = m => { throw new Error(m); };
    const peek = () => i < toks.length ? toks[i] : null;
    const take = want => { const t = peek(); if (t === null) bad("it ends too soon"); if (want !== undefined && t !== want) bad("expected \u201c" + want + "\u201d but found \u201c" + t + "\u201d"); i++; return t; };
    const finite = v => { if (!isFinite(v)) bad("the answer isn't a number"); return v; };
    function expr(){ let v = term(); while (peek() === "+" || peek() === "-") v = take() === "+" ? v + term() : v - term(); return v; }
    function term(){
      let v = unary();
      while (peek() === "*" || peek() === "/") { const op = take(), r = unary(); if (op === "/" && r === 0) bad("it divides by zero"); v = op === "*" ? v * r : v / r; }
      return v;
    }
    function unary(){ if (peek() === "-" || peek() === "+") return take() === "-" ? -unary() : unary(); return power(); }
    function power(){ let v = primary(); if (peek() === "^") { take(); v = finite(Math.pow(v, unary())); } return v; }
    function primary(){
      const t = take();
      if (t === "(") { const v = expr(); take(")"); return v; }
      if (/^[\d.]/.test(t)) return parseFloat(t);
      const name = t.toLowerCase();
      if (name === "pi") return Math.PI;
      if (!CALC_FUNCS.includes(name)) bad("I don't know \u201c" + t + "\u201d (it can use " + CALC_FUNCS.join(", ") + " and pi)");
      take("(");
      const args = [expr()];
      while (peek() === ",") { take(); args.push(expr()); }
      take(")");
      if (name === "min" || name === "max") return Math[name](...args);
      if (name === "round") { const places = args.length > 1 ? Math.max(0, Math.min(10, Math.floor(args[1] + 0.5))) : 0, f = Math.pow(10, places); return Math.floor(args[0] * f + 0.5) / f; }
      if (args.length !== 1) bad(name + " takes one number");
      if (name === "sqrt" && args[0] < 0) bad("it takes the square root of a negative number");
      return Math[name](args[0]);
    }
    if (!toks.length) bad("it's empty");
    const v = expr();
    if (peek() !== null) bad("I don't understand \u201c" + peek() + "\u201d there");
    return finite(v);
  }
  function calcText(expression){
    expression = str(expression).trim();
    let v;
    try { v = calcValue(expression); } catch(e) { fail(tr("calculate couldn't work out \u201c{expression}\u201d: {message}.", { expression:short(expression, 80), message:e.message })); }
    v = Number(v.toPrecision(12));
    return expression + " = " + String(v);
  }
  const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  /* '09:30' plus 270 -> '14:00'; '2026-10-10 22:00' plus 600 -> '2026-10-11 08:00 (Sunday)'. Matches the runtime. */
  function timePlusText(when, minutes){
    const m = /^\s*(?:(\d{4})-(\d{1,2})-(\d{1,2})[ T]+)?(\d{1,2})[:.](\d{2})\s*(am|pm)?\s*$/i.exec(str(when));
    if (!m) fail(tr("time_plus needs a time like 09:30 or 2026-10-10 09:30, not \u201c{when}\u201d.", { when:short(when, 40) }));
    let h = +m[4]; const mi = +m[5], ampm = (m[6] || "").toLowerCase(), shown = str(when).trim();
    if (ampm) { if (h < 1 || h > 12) fail(tr("\u201c{shown}\u201d isn't a time.", { shown })); h = h % 12 + (ampm === "pm" ? 12 : 0); }
    if (h > 23 || mi > 59) fail(tr("\u201c{shown}\u201d isn't a time.", { shown }));
    const add = Math.floor(num(minutes) + 0.5);
    if (m[1]) {
      const y = +m[1], mo = +m[2], d = +m[3], start = new Date(Date.UTC(y, mo - 1, d, h, mi));
      if (start.getUTCFullYear() !== y || start.getUTCMonth() !== mo - 1 || start.getUTCDate() !== d) fail(tr("\u201c{shown}\u201d isn't a real date.", { shown }));
      const t = new Date(start.getTime() + add * 60000);
      return t.getUTCFullYear() + "-" + pad2(t.getUTCMonth() + 1) + "-" + pad2(t.getUTCDate()) + " " + pad2(t.getUTCHours()) + ":" + pad2(t.getUTCMinutes()) +
        " (" + WEEKDAYS[(t.getUTCDay() + 6) % 7] + ")";
    }
    const total = h * 60 + mi + add, days = Math.floor(total / 1440), t = ((total % 1440) + 1440) % 1440;
    const note = days === 0 ? "" : days === 1 ? " (next day)" : days === -1 ? " (the day before)" : days > 0 ? " (" + days + " days later)" : " (" + (-days) + " days earlier)";
    return pad2(Math.floor(t / 60)) + ":" + pad2(t % 60) + note;
  }
