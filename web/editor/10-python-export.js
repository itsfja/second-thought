  // 10-python-export.js: Turning blocks into Python, and the exported settings and launchers.
  /* ---------- Python export ---------- */
  const PY_MARK = "# ---- Second Thought program: lets the block editor import this file again ----";
  // The runtime embedded below (python/runtime.py) says its own version; exports carry it, so imports can compare.
  const RUNTIME_VERSION = (document.getElementById("py-runtime").textContent.match(/^RUNTIME_VERSION = "([^"]+)"/m) || [])[1] || "";
  if (RUNTIME_VERSION) $("io-py-version").textContent = " It comes with runtime " + RUNTIME_VERSION + ".";
  const PY_MARKS = [PY_MARK,"# ---- Reflection Blocks program: lets the block editor import this file again ----"];
  const pyStr = s => JSON.stringify(String(s == null ? "" : s));
  const pyNum = v => { const n = Number(v); return isFinite(n) ? String(n) : "0"; };
  function codeHash(text){
    const t = String(text).replace(/\r\n?/g, "\n").split("\n").map(l => l.replace(/\s+$/, "")).join("\n").replace(/\n+$/, "");
    let h = 0x811c9dc5;
    for (let i = 0; i < t.length; i++) { h ^= t.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
    return h.toString(16).padStart(8, "0");
  }
  function b64encode(str){ const bytes = new TextEncoder().encode(str); let bin = ""; for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]); return btoa(bin); }
  function b64decode(b64){ const bin = atob(b64); const bytes = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i); return new TextDecoder().decode(bytes); }

  /* ----- second-thought.ini: the keys and settings an exported program needs ----- */
  /* Saved programs used by 'run program' blocks, loaded into hidden workspaces (recursively). */
  function savedProgramState(name){
    const e = lib.program.get(memKey(name));
    if (!e) return null;
    try { return migrateProgram(JSON.parse(e.program), e.version).state; } catch(err) { return null; }
  }
  function subProgramProblem(sub){
    const bad = sub.getAllBlocks(false).find(b => ["rb_broadcast","rb_broadcast_wait","rb_broadcast_with","rb_broadcast_with_wait","rb_wait_msg"].includes(b.type));
    if (bad) return "uses broadcasts, which only work in a program run on its own";
    if (!sub.getTopBlocks(false).some(b => b.type === "rb_start")) return "has no 'when Run is clicked' script";
    return null;
  }
  function withSubPrograms(fn){
    // Calls fn(list) with every saved program the canvas runs, directly or through other programs: [{ name, key, ws, problem }].
    const found = new Map(), made = [];
    const visit = w => w.getAllBlocks(false).filter(b => b.type === "rb_run_program").forEach(b => {
      const name = String(b.getFieldValue("NAME") || "").trim(), key = memKey(name);
      if (!key || found.has(key)) return;
      const state = savedProgramState(name);
      if (!state) { found.set(key, { name, key, ws:null, problem:"isn't in your Programs list" }); return; }
      const sub = new Blockly.Workspace(); made.push(sub);
      try { Blockly.serialization.workspaces.load(state, sub); }
      catch(err) { found.set(key, { name, key, ws:null, problem:"couldn't be opened" }); return; }
      found.set(key, { name, key, ws:sub, problem:subProgramProblem(sub) });
      visit(sub);
    });
    try { visit(ws); return fn([...found.values()]); }
    finally { made.forEach(w => { try { w.dispose(); } catch(e) {} }); }
  }
  function allProgramBlocks(){
    return withSubPrograms(subs => ws.getAllBlocks(false).concat(...subs.filter(x => x.ws).map(x => x.ws.getAllBlocks(false))));
  }
  // The Kraken tools block's choice, for --doctor: "live" if any asks for live trading.
  const krakenMode = () => { const k = allProgramBlocks().filter(b => b.type === "rb_agent_kraken");
    return k.length ? (k.some(b => b.getFieldValue("MODE") === "live") ? "live" : "read") : ""; };
  const FR24_COMMANDS = { read:"npx -y @flightradar24/fr24api-mcp" };  // FR24_COMMANDS in mcp.py
  function settingsFor(){
    const keys = servicesUsed().filter(s => s.signup).map(s => [s.key_label || s.name, s.keys[0], s.signup]);
    const blocks = allProgramBlocks();
    const kinds = new Set(blocks.filter(b => b.type === "rb_agent_builtin").map(b => b.getFieldValue("KIND")));
    const has = (types, ks) => blocks.some(b => types.includes(b.type)) || ks.some(k => kinds.has(k));
    return { keys, llama:programUses(serviceNamed("Llama")), ha:has([], ["ha_read", "ha_act", "ha_act_free"]) || blocks.some(b => b.type.startsWith("rb_ha_")),
             github:has(["rb_gh_when", "rb_gh_issue_when", "rb_gh_release_when"], ["github", "github_act"]), telegram:has(["rb_tg_when", "rb_tg_send", "rb_tg_message"], ["telegram", "telegram_send", "telegram_send_free"]),
             discord:has(["rb_discord_when", "rb_discord_send"], ["discord", "discord_send", "discord_send_free"]),
             slack:has(["rb_slack_when", "rb_slack_send"], ["slack", "slack_send", "slack_send_free"]),
             email:has(["rb_email_send", "rb_email_when"], ["email", "email_send"]), calendar:has(["rb_calendar", "rb_cal_when"], ["calendar"]),
             feeds:has(["rb_feed_news", "rb_feed_when"], ["feeds"]), mqtt:has(["rb_mqtt_when", "rb_mqtt_read", "rb_mqtt_publish"], ["mqtt", "mqtt_act", "mqtt_act_free"]),
             webhook:has(["rb_webhook_when"], []), folder:has(["rb_folder_when"], []),
             mcp:[...new Set(blocks.filter(b => b.type === "rb_agent_mcp").map(b => String(b.getFieldValue("SERVER") || "").trim()).filter(Boolean))],
             kraken:blocks.some(b => b.type === "rb_agent_kraken"),
             flightradar24:blocks.some(b => b.type === "rb_agent_fr24"),
             coinbase:blocks.some(b => b.type.startsWith("rb_coinbase_")),
             mikrotik:blocks.some(b => b.type.startsWith("rb_mikrotik_")),
             solax:blocks.some(b => b.type.startsWith("rb_solax_")),
             powerwall:blocks.some(b => b.type.startsWith("rb_powerwall_")),
             unifi:blocks.some(b => b.type.startsWith("rb_unifi_")),
             proxmox:blocks.some(b => b.type.startsWith("rb_proxmox_")),
             docker:blocks.some(b => b.type.startsWith("rb_docker_")),
             sabnzbd:blocks.some(b => b.type.startsWith("rb_sabnzbd_")),
             arr:blocks.some(b => b.type.startsWith("rb_arr_")),
             unraid:blocks.some(b => b.type.startsWith("rb_unraid_")),
             nzbgeek:blocks.some(b => b.type.startsWith("rb_nzbgeek_")),
             homey:blocks.some(b => b.type.startsWith("rb_homey_")) || ["homey_read", "homey_act", "homey_act_free"].some(k => kinds.has(k)),
             pages:has([], ["web"]) };
  }
  function iniText(progName){
    const need = settingsFor(), nl = "\r\n";
    // A setting's note, then the setting: left as a note itself unless `on`, so a ; to take off and nothing to clear.
    const note = (name, example, what, on) => ["; " + name + ": " + what, (on ? "" : "; ") + name + " = " + example];
    const out = [
      "; Settings for " + progName + ". Fill in the keys, then save this file.",
      "; It must stay in the same folder as the program.",
      "; Keep it private: it holds your API keys. Don't email it or put it on GitHub.",
      "; Lines starting with ; are notes and are ignored.",
      "; Settings your programs share, such as email and keys, can go in second-thought.ini in your home folder,",
      "; or in ST_ environment variables (ST_EMAIL_ADDRESS, ST_CURRENCY): every program reads those first, then this file.",
      "",
      "[keys]"
    ];
    need.keys.forEach(([who, env, url]) => { out.push("; " + who + ": get a key at " + url); out.push(env + " = "); });
    out.push("", "[models]",
      "; Your primary model and backups. Leave these as notes to use what was set when you exported.",
      "; primary = " + $("tier").value,
      "; backups = " + (backupTiers().join(", ") || "none"),
      "", "[run]",
      // Every note goes on a line of its own, above its setting: a setting line can't carry one, so taking the ; off a
      // line like "; save_log = yes   write each run's log" would make the note part of the value (#338).
      ...note("budget", "50000", "stop a run before a model call once it has used this many tokens (0 = no limit)"),
      ...note("budget_dollars", "0.50", "or once it has spent this much, in US dollars at the models' list prices (0 = no limit)"),
      ...note("budget_money", "0.40", "the same in the currency below (it wins over budget_dollars)"),
      ...note("currency", currency() === "usd" ? "gbp" : currency(), "show costs and money budgets in usd, gbp, eur, jpy or cny (the European Central Bank's rate of the day)", currency() !== "usd"),
      ...note("exchange_rate", "0.79", "fix one US dollar in that currency, instead of fetching the day's rate"),
      ...note("save_log", "yes", "write each run's log to the logs folder, next to the program"),
      ...note("stream", "yes", "show Claude writing as it goes (yes or no; normally only when you run it in a terminal yourself)"),
      ...note("resume", "yes", "if a run stopped part-way, pick up where it stopped next time (yes or no; normally it asks you)"),
      ...(programCapabilities().some(c => c[2]) ? note("approve", "no", "don't ask before the first run (for a computer with nobody at it). The program's notes list what it can do") : []),
      ...(exportWords() ? note("language", "en", "print in English instead of " + window.ST_I18N.name + " (the run log, questions, errors and --doctor)") : []));
    if (need.mcp.length) out.push("", "[mcp servers]",
      "; Each MCP server the agent uses: the command that starts it, or its https:// address (and MCP_<NAME>_TOKEN = ... if it needs one).",
      "; For example:  MCP_FILES = npx -y @modelcontextprotocol/server-filesystem /home/me/recipes",
      "; A server this program starts gets these settings as its environment, so its own keys can go here too.",
      ...need.mcp.map(n => mcpSetting(n) + " = "));
    if (need.kraken) out.push("", "[kraken]",
      "; Kraken's tools come from kraken-cli (https://docs.kraken.com/home/mcp): install it, then the program starts it itself.",
      "; Prices and paper trading need no key. For your account, make an API key at kraken.com (Settings, API) with the",
      "; fewest permissions it needs: query only, unless the program trades. Never give it withdrawal permission.",
      "KRAKEN_API_KEY = ", "KRAKEN_API_SECRET = ",
      ...note("MCP_KRAKEN", "kraken mcp -s market,account,paper", "to choose Kraken's services yourself (never add --allow-dangerous)"));
    if (need.flightradar24) out.push("", "[flightradar24]",
      "; Flightradar24's tools come from its own MCP server, started with npx (https://github.com/Flightradar24/fr24api-mcp):",
      "; install Node.js, and the program starts the server itself.",
      "; The key is a paid subscription that works on credits, from https://fr24api.flightradar24.com. Each call costs",
      "; credits, so give the program a budget or a step limit to keep a run cheap.",
      "FR24_API_KEY = ",
      ...note("MCP_FLIGHTRADAR24", "npx -y @flightradar24/fr24api-mcp", "to start the server your own way"));
    if (need.docker) out.push("", "[docker]",
      "; Docker's Engine API. Left out, it's the socket on this computer (unix:///var/run/docker.sock), which is root on",
      "; the machine: safer is a socket proxy (tecnativa/docker-socket-proxy with CONTAINERS=1, plus ALLOW_RESTARTS=1 and",
      "; ALLOW_START=1 only if the program restarts, stops or starts containers), and DOCKER_HOST = tcp://that-machine:2375.",
      "; DOCKER_PROTECT lists containers never restarted, stopped or started, like the proxy itself.",
      "; DOCKER_HOST = tcp://docker.local:2375", "DOCKER_PROTECT = ");
    if (need.sabnzbd) out.push("", "[sabnzbd]",
      "; SABnzbd's API: its address and the full API key (in SABnzbd under Config, General, API Key), not the",
      "; NZB key. SABNZBD_CERT_SHA256 pins a certificate this computer doesn't trust, if it needs one.",
      "SABNZBD_URL = ", "SABNZBD_API_KEY = ");
    if (need.arr) out.push("", "[radarr]",
      "; Radarr's Servarr API: its address and API key (Settings, General, API Key). The blocks read the queue, the",
      "; wanted list and disk space; a search asks first, and nothing else is ever sent.",
      "RADARR_URL = ", "RADARR_API_KEY = ", "; RADARR_CERT_SHA256 = ", "", "[sonarr]",
      "; Sonarr, the same: its address and API key (Settings, General, API Key).",
      "SONARR_URL = ", "SONARR_API_KEY = ", "; SONARR_CERT_SHA256 = ");
    if (need.unraid) out.push("", "[unraid]",
      "; Your Unraid server, through its own GraphQL API (built into Unraid 7.2 and later, the Unraid Connect plugin",
      "; before that): its address and an API key (Settings, Management Access, API Keys). The blocks read the array,",
      "; the disks, the shares, the containers and the VMs; start, stop and a parity check ask first, and nothing",
      "; else is ever sent.",
      "UNRAID_URL = ", "UNRAID_API_KEY = ", "; UNRAID_CERT_SHA256 = ");
    if (need.nzbgeek) out.push("", "[nzbgeek]",
      "; NZBGeek, the Usenet indexer, through its Newznab API: its API key (My Account, API key). The search block",
      "; only reads; fetching an NZB asks first, and nothing else is ever sent.",
      "NZBGEEK_API_KEY = ", "; NZBGEEK_URL = ", "; NZBGEEK_CERT_SHA256 = ");
    if (need.proxmox) out.push("", "[proxmox]",
      "; Your Proxmox VE cluster, through its REST API. Make an API token (Datacenter, Permissions, API Tokens) for a user",
      "; with the PVEAuditor role, or one that may also start and stop guests (VM.PowerMgmt) if the program does. Run",
      "; --doctor once: it shows the node's certificate fingerprint to pin. PROXMOX_PROTECT lists VMIDs never started,",
      "; stopped or rebooted, like your Home Assistant or domain controller.",
      "PROXMOX_URL = https://pve.local:8006", "PROXMOX_TOKEN_ID = ", "PROXMOX_TOKEN_SECRET = ", "PROXMOX_CERT_SHA256 = ", "PROXMOX_PROTECT = ");
    if (need.unifi) out.push("", "[unifi]",
      "; Your UniFi console (a Cloud Gateway or Dream Machine), read through its Network API. Make a key in the Network app:",
      "; Settings, Control Plane, Integrations. Run --doctor once: it shows the console's certificate fingerprint to pin.",
      "UNIFI_URL = https://192.168.1.1", "UNIFI_API_KEY = ", "UNIFI_CERT_SHA256 = ");
    if (need.mikrotik) out.push("", "[mikrotik]",
      "; Your MikroTik router or switch, read through RouterOS 7's REST API (turn on the www-ssl service). Make a group with",
      "; only the read, api and rest-api policies, and a user in it for this program. Run --doctor once: it shows the",
      "; router's certificate fingerprint to pin.",
      "MIKROTIK_URL = https://192.168.88.1", "MIKROTIK_USER = ", "MIKROTIK_PASSWORD = ", "MIKROTIK_CERT_SHA256 = ");
    if (need.solax) out.push("", "[solax]",
      "; Your Solax inverter, read from SolaxCloud (the inverter's own local API is gone from newer firmware).",
      "; Make a free token on the API page of SolaxCloud, and find the Registration No. on the dongle's label or in the",
      "; app. The cloud updates about every five minutes, and each read is kept that long, so a run costs few calls.",
      "; SOLAX_API_URL points at another region's cloud, like the EU one.",
      "SOLAX_TOKEN_ID = ", "SOLAX_SN = ",
      ...note("SOLAX_API_URL", "https://www.eu.solaxcloud.com:9443/proxy/api/getRealtimeInfo.do", "to read from another region's SolaxCloud"));
    if (need.powerwall) out.push("", "[powerwall]",
      "; Your Tesla Powerwall (a Powerwall, Powerwall 2 or Powerwall+), read through the gateway's local API. The",
      "; Powerwall 3 has no local web API: use Home Assistant or Teslemetry for one of those.",
      "; The customer password is the last five characters of the one on the gateway's QR sticker, unless you",
      "; changed it. Run --doctor once: it shows the gateway's certificate fingerprint for POWERWALL_CERT_SHA256.",
      "; Setting the backup reserve always asks, and never runs unattended.",
      "POWERWALL_URL = https://192.168.1.50", "POWERWALL_PASSWORD = ",
      ...note("POWERWALL_EMAIL", "you@example.com", "the email the gateway's login form asks for (anything works)"),
      ...note("POWERWALL_CERT_SHA256", "aa:bb:...", "to pin the gateway's own certificate"));
    if (need.coinbase) out.push("", "[coinbase]",
      "; A Coinbase API key: at portal.cdp.coinbase.com, API Keys, Create API key. Choose ECDSA under its advanced settings,",
      "; limit it to one portfolio, and give it View permission only, unless the program places orders (then View and Trade).",
      "; Never give it Transfer. Save the key file it downloads next to the program, and put its name here.",
      "; Values are in the currency set under [run]. Signing needs:  pip install cryptography",
      "COINBASE_KEY_FILE = cdp_api_key.json");
    if (need.ha) out.push("", "[home assistant]",
      "; A long-lived access token: in Home Assistant, open your profile, then the Security tab.",
      "HA_URL = http://homeassistant.local:8123", "HA_TOKEN = ");
    if (need.feeds || need.pages) out.push("", "[feeds and pages]",
      ...(need.feeds ? ["; Your news feeds (RSS or Atom addresses), separated by spaces. 'News from feed' with nothing in it, and the agent, read these.",
                        "feeds = "] : []),
      ...note("local_pages", "yes", "let the agent read pages and feeds on your own network too (normally only public ones)"));
    if (need.github) out.push("", "[github]",
      "; A token from https://github.com/settings/tokens. Fine-grained: read access to contents, issues and pull requests;",
      "; to let the agent comment, pull requests and issues need read and write.",
      "GITHUB_TOKEN = ");
    if (need.telegram) out.push("", "[telegram]",
      "; Make a bot: in Telegram, message @BotFather and send /newbot. It gives you the token.",
      "; Then send your bot a message and run this program: it says your chat id. Put it below.",
      "; The bot only listens to, and searches, the chats listed here (anyone can message a bot).",
      "TELEGRAM_BOT_TOKEN = ", "TELEGRAM_CHAT_ID = ");
    if (need.discord) out.push("", "[discord]",
      "; A bot: Discord Developer Portal (discord.com/developers), New Application, Bot, Reset Token. Turn on 'Message Content Intent'",
      "; on the same page, then invite the bot to your server (OAuth2, URL Generator, bot; Read and Send Messages).",
      "; The channels it reads and posts in: right-click a channel, Copy Channel ID (turn on Developer Mode first).",
      "; Anyone in a server can post, so only these channels count. Several can be separated by spaces.",
      "DISCORD_BOT_TOKEN = ", "DISCORD_CHANNEL_ID = ");
    if (need.slack) out.push("", "[slack]",
      "; A Slack app (api.slack.com/apps): OAuth & Permissions, bot scopes channels:history, groups:history and chat:write,",
      "; then install it and copy the Bot User OAuth Token (xoxb-…). Invite the bot to each channel with /invite.",
      "; The channels it reads and posts in: open the channel's details; the ID is at the bottom. Several can be separated by spaces.",
      "SLACK_BOT_TOKEN = ", "SLACK_CHANNEL_ID = ");
    if (need.email) out.push("", "[email]",
      "; Your address and an app password (not your normal password). Gmail: Google account, Security, App passwords.",
      "; Gmail, iCloud, Yahoo, Fastmail and mailbox.org work out their own servers. For others, fill in the servers too.",
      "EMAIL_ADDRESS = ", "EMAIL_PASSWORD = ", "; EMAIL_IMAP_HOST = ", "; EMAIL_SMTP_HOST = ", "; EMAIL_SMTP_PORT = 465");
    if (need.calendar) out.push("", "[calendar]",
      "; Your calendar's private iCal address. Google Calendar: Settings, your calendar, 'Secret address in iCal format'.",
      "; Outlook: Settings, Calendar, Shared calendars, Publish a calendar, ICS link. Several addresses can go on one line.",
      "CALENDAR_URL = ");
    if (need.homey) out.push("", "[homey]",
      "; Your Homey's address, and an API key: in the Homey Web App (my.homey.app), Settings, API Keys, New API Key.",
      "; Homey Pro: http://homey-XXXXXXX.local or its IP address. Homey Self-Hosted Server: the computer's IP address and :4859,",
      "; like http://192.168.1.20:4859. Devices on a Homey Bridge connected to it show up there too.",
      "; Give the key the permissions the program needs: View devices, Control devices, View and start flows, View and edit Logic.",
      "HOMEY_URL = http://homey-XXXXXXX.local", "HOMEY_API_KEY = ");
    if (need.mqtt) out.push("", "[mqtt]",
      "; Your MQTT broker, for example Mosquitto in Home Assistant (Settings, Add-ons). Add a username and password if it needs them.",
      "MQTT_HOST = homeassistant.local", "; MQTT_PORT = 1883", "; MQTT_USERNAME = ", "; MQTT_PASSWORD = ", "; MQTT_TLS = yes   for an encrypted connection (port 8883)");
    if (need.webhook) out.push("", "[web requests]",
      "; A long password that every web request must carry: http://127.0.0.1:8765/<address>?key=<this password>",
      "; or in an X-Second-Thought-Key header. Requests without it are refused.",
      "; Only this computer can call it, which is enough for Home Assistant on the same machine. For Home Assistant",
      "; on another machine, IFTTT or your phone, uncomment WEBHOOK_HOST = 0.0.0.0 and call http://<this computer>:8765/...",
      "WEBHOOK_SECRET = ", "; WEBHOOK_PORT = 8765", "; WEBHOOK_HOST = 0.0.0.0");
    if (need.llama) out.push("", "[llama]",
      "; Where your Llama server is. This is Ollama on this computer; change it if Llama lives elsewhere.",
      "LLAMA_BASE_URL = http://localhost:11434/v1", "; LLAMA_API_KEY = ");
    return out.join(nl) + nl;
  }
  function runBat(fileBase, schedule){
    const nl = "\r\n";
    return ["@echo off",
      "rem Double-click to run " + fileBase + ". The first run installs what it needs.",
      "cd /d \"%~dp0\"",
      "set PY=python",
      "where py >nul 2>nul && set PY=py",
      "%PY% -m pip install --quiet --disable-pip-version-check -r requirements.txt",
      ...(schedule ? [":again",
        "%PY% " + fileBase + ".py --schedule %*",
        "if errorlevel 1 (",
        "  echo.",
        "  echo It stopped with a problem. Starting again in 30 seconds. Close this window to stop it.",
        "  timeout /t 30 /nobreak >nul",
        "  goto again",
        ")"] : ["%PY% " + fileBase + ".py %*"]),
      "echo.",
      "pause"].join(nl) + nl;
  }
  function installStartupBat(fileBase){
    const nl = "\r\n", entry = "Second Thought - " + fileBase + ".cmd";
    return ["@echo off",
      "rem Makes " + fileBase + " start by itself whenever you log in to Windows. Double-click it once.",
      "rem Fill in second-thought.ini first. No administrator rights needed.",
      "cd /d \"%~dp0\"",
      "set \"STARTUP=%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\"",
      "if not exist \"%STARTUP%\" mkdir \"%STARTUP%\"",
      "set \"ENTRY=%STARTUP%\\" + entry + "\"",
      "> \"%ENTRY%\" echo @echo off",
      ">> \"%ENTRY%\" echo start \"Second Thought: " + fileBase + "\" /min cmd /c \"\"%~dp0run-on-schedule.bat\"\"",
      "if not exist \"%ENTRY%\" (",
      "  echo Couldn't add it to your Startup folder.",
      "  pause",
      "  exit /b 1",
      ")",
      "echo Done. " + fileBase + " will start by itself, in a small window, each time you log in.",
      "echo To start it now, double-click run-on-schedule.bat.",
      "echo To stop it starting by itself: press Windows+R, type shell:startup, and delete",
      "echo \"" + entry + "\".",
      "echo.",
      "pause"].join(nl) + nl;
  }
  function runSh(fileBase, schedule){
    return ["#!/bin/sh",
      "# Run " + fileBase + " on Linux or a Mac:  sh " + (schedule ? "run-on-schedule.sh" : "run.sh"),
      "# The first run makes a private Python folder here (.venv) and installs what the program needs,",
      "# so nothing is installed for the whole computer.",
      "cd \"$(dirname \"$0\")\" || exit 1",
      "if [ ! -x .venv/bin/python ]; then",
      "  echo \"First run: setting things up. This takes a minute.\"",
      "  if ! python3 -m venv .venv; then",
      "    rm -rf .venv",
      "    echo \"Couldn't set up Python here. On Debian or Ubuntu, run:  sudo apt install python3-venv\"",
      "    echo \"then try again. No python3 at all? Install it from your software centre first.\"",
      "    exit 1",
      "  fi",
      "fi",
      "if ! cmp -s requirements.txt .venv/installed.txt; then",
      "  .venv/bin/python -m pip install --quiet --disable-pip-version-check -r requirements.txt || exit 1",
      "  cp requirements.txt .venv/installed.txt",
      "fi",
      "exec .venv/bin/python -u " + fileBase + ".py " + (schedule ? "--schedule " : "") + "\"$@\"",
      ""].join("\n");
  }
  function installServiceSh(fileBase){
    const svc = "second-thought-" + fileBase;
    return ["#!/bin/sh",
      "# Keeps " + fileBase + " running all the time on this computer, and starts it again after a restart.",
      "# Run it once:  sh install-service.sh",
      "# Linux: asks for your password, to install a systemd service. Mac: no password, it uses launchd.",
      "# Fill in second-thought.ini first.",
      "cd \"$(dirname \"$0\")\" || exit 1",
      "here=$(pwd)",
      "name=" + svc,
      "if [ \"$(uname)\" = Darwin ]; then",
      "  label=com.secondthought." + fileBase.replace(/[^A-Za-z0-9.-]/g, "-"),
      "  plist=\"$HOME/Library/LaunchAgents/$label.plist\"",
      "  mkdir -p \"$HOME/Library/LaunchAgents\"",
      "  cat > \"$plist\" <<EOF",
      "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
      "<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">",
      "<plist version=\"1.0\">",
      "<dict>",
      "  <key>Label</key><string>$label</string>",
      "  <key>ProgramArguments</key><array><string>/bin/sh</string><string>$here/run-on-schedule.sh</string></array>",
      "  <key>WorkingDirectory</key><string>$here</string>",
      "  <key>RunAtLoad</key><true/>",
      "  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>",
      "  <key>ThrottleInterval</key><integer>30</integer>",
      "  <key>StandardOutPath</key><string>$here/" + fileBase + ".log</string>",
      "  <key>StandardErrorPath</key><string>$here/" + fileBase + ".log</string>",
      "</dict>",
      "</plist>",
      "EOF",
      "  launchctl bootout \"gui/$(id -u)/$label\" >/dev/null 2>&1",
      "  launchctl bootstrap \"gui/$(id -u)\" \"$plist\" || launchctl load \"$plist\" || exit 1",
      "  echo \"Done. " + fileBase + " is running, and starts again by itself whenever you log in.\"",
      "  echo \"See what it's doing:  tail -f \\\"$here/" + fileBase + ".log\\\"\"",
      "  echo \"Stop it for good:     launchctl bootout gui/$(id -u)/$label && rm \\\"$plist\\\"\"",
      "  exit 0",
      "fi",
      "if ! command -v systemctl >/dev/null 2>&1; then",
      "  echo \"This computer doesn't use systemd. Start run-on-schedule.sh with your own start-up tool instead.\"",
      "  exit 1",
      "fi",
      "unit=$(mktemp)",
      "cat > \"$unit\" <<EOF",
      "[Unit]",
      "Description=Second Thought: " + fileBase,
      "After=network-online.target",
      "Wants=network-online.target",
      "",
      "[Service]",
      "WorkingDirectory=$here",
      "ExecStart=/bin/sh \"$here/run-on-schedule.sh\"",
      "Restart=on-failure",
      "RestartSec=30",
      "User=$(id -un)",
      "",
      "[Install]",
      "WantedBy=multi-user.target",
      "EOF",
      "sudo install -m 644 \"$unit\" \"/etc/systemd/system/$name.service\" || exit 1",
      "rm -f \"$unit\"",
      "sudo systemctl daemon-reload && sudo systemctl enable --now \"$name\" || exit 1",
      "echo \"Done. $name is running, and starts again by itself after a restart.\"",
      "echo \"See what it's doing:  journalctl -u $name -f\"",
      "echo \"Stop it for good:     sudo systemctl disable --now $name\"",
      ""].join("\n");
  }
  // Whether the program uses a service: as its model or a backup, in a "use model" or "with model" block, or (for a
  // service that can name any of its models) in a "with any model" block.
  function programUses(service){
    if (!service) return false;
    if (service.always) return true;
    const has = t => serviceOf(t) === service;
    if ([$("tier").value].concat(backupTiers()).some(has)) return true;
    return allProgramBlocks().some(b => b.type === "rb_with_any_model" ? !!service.any_model :
      (b.type === "rb_use_model" || b.type === "rb_with_model") && has(b.getFieldValue("TIER")));
  }
  const servicesUsed = () => SERVICES.filter(programUses);
  // The export header's list of what the program can do.
  function canHeader(caps, services){
    const acts = caps.some(c => c[2]);
    return ["What this program can do:"].concat(caps.length ? caps.map(c => "  - " + c[1]) : ["  - nothing beyond asking its models"],
      ["It sends what it reads and writes to " + andList(services.map(x => x.name)) + "."],
      acts ? ["Because some of that acts on the world, it lists these and asks you before its first run, and again",
              "if this file changes. On a computer with nobody at it, put approve = no in second-thought.ini."] : [], [""]);
  }
  // The words an exported program prints, in the page's language ("python" in i18n/<language>.json), or null for English.
  function exportWords(){
    const w = window.ST_I18N && I18N.python;
    return w && Object.keys(w).length ? w : null;
  }
  function toPython(progName){
    const used = new Set(["R","V","main","run"]);
    const ident = base => {
      let id = String(base).replace(/[^A-Za-z0-9_]+/g, "_").replace(/^_+|_+$/g, "").toLowerCase() || "x";
      if (/^\d/.test(id)) id = "_" + id;
      let out = id, i = 2;
      while (used.has(out)) out = id + "_" + (i++);
      used.add(out); return out;
    };
    const procIds = new Map();
    let scope = "", scopeTag = "";   // which program's My Blocks are being named: "" for the canvas
    const procId = n => { const k = scope + "\u0000" + n; if (!procIds.has(k)) procIds.set(k, ident("block_" + scopeTag + n)); return procIds.get(k); };
    const programFn = new Map();     // saved program key -> its Python function name
    let tmpN = 0;
    const tmp = p => "_" + p + (++tmpN);
    const vname = b => b.getField("VAR").getText();
    const enabled = b => !b.isEnabled || b.isEnabled();
    const listVar = t => t && t.type === "variables_get" ? pyStr(vname(t)) : "None";

    function inp(b, name, dflt){ const t = b.getInputTargetBlock(name); return t ? expr(t) : dflt; }
    function expr(b){
      const I = (n, d) => inp(b, n, d);
      const F = n => b.getFieldValue(n);
      switch (b.type) {
        case "math_number": return pyNum(F("NUM"));
        case "text": case "rb_longtext": return pyStr(F("TEXT"));
        case "logic_boolean": return F("BOOL") === "TRUE" ? "True" : "False";
        case "variables_get": return "R.get(" + pyStr(vname(b)) + ")";
        case "logic_negate": return "(not to_bool(" + I("BOOL", "False") + "))";
        case "logic_operation": return "(to_bool(" + I("A", "False") + ") " + (F("OP") === "AND" ? "and" : "or") + " to_bool(" + I("B", "False") + "))";
        case "logic_compare": return "compare(" + I("A", '""') + ", " + pyStr(F("OP")) + ", " + I("B", '""') + ")";
        case "logic_ternary": return "(" + I("THEN", '""') + " if to_bool(" + I("IF", "False") + ") else " + I("ELSE", '""') + ")";
        case "math_arithmetic": return "arith(" + I("A", "0") + ", " + pyStr(F("OP")) + ", " + I("B", "0") + ")";
        case "math_random_int": return "random_int(" + I("FROM", "1") + ", " + I("TO", "10") + ")";
        case "math_round": return "round_op(" + I("NUM", "0") + ", " + pyStr(F("OP")) + ")";
        case "math_modulo": return "modulo(" + I("DIVIDEND", "0") + ", " + I("DIVISOR", "1") + ")";
        case "text_join": { const xs = []; for (let i = 0; i < (b.itemCount_ || 0); i++) xs.push(I("ADD" + i, '""')); return "join(" + xs.join(", ") + ")"; }
        case "text_length": return "length(" + I("VALUE", '""') + ")";
        case "text_isEmpty": return "is_empty(" + I("VALUE", '""') + ")";
        case "text_changeCase": return "change_case(" + I("TEXT", '""') + ", " + pyStr(F("CASE")) + ")";
        case "rb_contains": return "contains(" + I("A", '""') + ", " + I("B", '""') + ")";
        case "rb_word_count": return "word_count(" + I("TEXT", '""') + ")";
        case "lists_create_empty": return "[]";
        case "lists_create_with": { const xs = []; for (let i = 0; i < (b.itemCount_ || 0); i++) { const t = b.getInputTargetBlock("ADD" + i); if (t) xs.push(expr(t)); } return "[" + xs.join(", ") + "]"; }
        case "lists_length": return "len(to_list(" + I("VALUE", "[]") + "))";
        case "lists_isEmpty": return "(len(to_list(" + I("VALUE", "[]") + ")) == 0)";
        case "lists_getIndex": return "R.list_get(" + I("VALUE", "[]") + ", " + pyStr(F("MODE")) + ", " + pyStr(F("WHERE")) + ", " + I("AT", "1") + ", " + listVar(b.getInputTargetBlock("VALUE")) + ")";
        case "procedures_callreturn": { const args = (b.arguments_ || []).map((_, i) => I("ARG" + i, '""')); return "(await " + procId(b.getProcedureCall()) + "(" + args.join(", ") + "))"; }
        case "rb_draft": return "R.draft";
        case "rb_task_get": return "R.task";
        case "rb_ask": return "(await R.ask_text(" + I("TEXT", '""') + "))";
        case "rb_ask_yesno": return "(await R.ask_yesno(" + I("TEXT", '""') + "))";
        case "rb_ask_number": return "(await R.ask_number(" + I("TEXT", '""') + "))";
        case "rb_ask_list": return "(await R.ask_list(" + I("TEXT", '""') + "))";
        case "rb_rewrite": return "(await R.rewrite(" + I("TEXT", '""') + ", " + I("HOW", '""') + "))";
        case "rb_extract": return "(await R.extract(" + I("WHAT", '""') + ", " + I("TEXT", '""') + "))";
        case "rb_passed": return "(R.approved is True)";
        case "rb_problems": return "list(R.problems)";
        case "rb_score": return "(await R.score(" + I("TEXT", '""') + ", " + I("CRITERIA", '""') + "))";
        case "rb_better": return "(await R.better(" + I("A", '""') + ", " + I("B", '""') + ", " + I("CRITERIA", '""') + "))";
        case "rb_answer": return "R.answer";
        case "rb_approve": return "(await R.approve(" + I("TEXT", '""') + "))";
        case "rb_tokens_used": return "R.tokens_used()";
        case "rb_setup_check": return "(await R.setup_check())";
        case "rb_folder_files": return "(await R.folder_files(" + I("FOLDER", '""') + ", " + I("MATCH", '""') + "))";
        case "rb_agent_steps": return "R.agent_steps()";
        case "rb_run_program": {
          const name = String(F("NAME") || "").trim();
          return "(await R.run_program(" + pyStr(name) + ", " + (programFn.get(memKey(name)) || "None") + ", " + I("VALUE", '""') + "))";
        }
        case "rb_choose": return "(await R.choose(" + I("LIST", "[]") + "))";
        case "rb_timer": return "R.timer()";
        case "rb_now": return "R.now(" + pyStr(F("PART")) + ")";
        case "rb_img_choose": return "(await R.choose_picture())";
        case "rb_mem_get": return "R.recall(" + I("NAME", '""') + ")";
        case "rb_ha_state": return "(await R.ha_state(" + I("ENTITY", '""') + "))";
        case "rb_ha_attr": return "(await R.ha_attr(" + I("ATTR", '""') + ", " + I("ENTITY", '""') + "))";
        case "rb_ha_find": return "(await R.ha_find(" + I("TEXT", '"*"') + "))";
        case "rb_ha_summary": return "(await R.ha_summary(" + I("TEXT", '"*"') + "))";
        case "rb_ha_history": return "(await R.ha_history(" + I("ENTITY", '""') + ", " + I("HOURS", "24") + "))";
        case "rb_ha_snapshot": return "(await R.ha_snapshot(" + I("CAMERA", '""') + "))";
        case "rb_ha_trigger": return "R.ha_trigger()";
        case "rb_tg_message": return "R.telegram_message(" + pyStr(F("PART") || "text") + ")";
        case "rb_event": return "R.event(" + pyStr(String(F("KEY") || "").trim()) + ")";
        case "rb_homey_value": return "(await R.homey_value(" + I("CAPABILITY", '""') + ", " + I("DEVICE", '""') + "))";
        case "rb_homey_find": return "(await R.homey_find(" + I("TEXT", '"*"') + "))";
        case "rb_homey_variable": return "(await R.homey_variable(" + I("NAME", '""') + "))";
        case "rb_coinbase_balances": return "(await R.coinbase_balances())";
        case "rb_docker_containers": return "(await R.docker_containers())";
        case "rb_docker_stats": return "(await R.docker_stats())";
        case "rb_docker_logs": return "(await R.docker_logs(" + I("NAME", '""') + ", " + I("N", "50") + "))";
        case "rb_sabnzbd_queue": return "(await R.sabnzbd_queue())";
        case "rb_sabnzbd_history": return "(await R.sabnzbd_history(" + I("N", "24") + "))";
        case "rb_sabnzbd_diskspace": return "(await R.sabnzbd_diskspace())";
        case "rb_arr_queue": return "(await R.arr_queue(" + pyStr(b.getFieldValue("WHICH")) + "))";
        case "rb_arr_missing": return "(await R.arr_missing(" + pyStr(b.getFieldValue("WHICH")) + "))";
        case "rb_arr_diskspace": return "(await R.arr_diskspace(" + pyStr(b.getFieldValue("WHICH")) + "))";
        case "rb_unraid_array": return "(await R.unraid_array())";
        case "rb_unraid_disks": return "(await R.unraid_disks())";
        case "rb_unraid_shares": return "(await R.unraid_shares())";
        case "rb_unraid_containers": return "(await R.unraid_containers())";
        case "rb_unraid_vms": return "(await R.unraid_vms())";
        case "rb_nzbgeek_search": return "(await R.nzbgeek_search(" + I("QUERY", "\"\"") + "))";
        case "rb_proxmox_nodes": return "(await R.proxmox_nodes())";
        case "rb_proxmox_guests": return "(await R.proxmox_guests())";
        case "rb_proxmox_storage": return "(await R.proxmox_storage())";
        case "rb_proxmox_tasks": return "(await R.proxmox_tasks(" + I("N", "24") + "))";
        case "rb_unifi_clients": return "(await R.unifi_clients())";
        case "rb_unifi_devices": return "(await R.unifi_devices())";
        case "rb_solax_now": return "(await R.solax_now())";
        case "rb_powerwall_now": return "(await R.powerwall_now())";
        case "rb_mikrotik_ports": return "(await R.mikrotik_ports())";
        case "rb_mikrotik_sfp": return "(await R.mikrotik_sfp())";
        case "rb_mikrotik_health": return "(await R.mikrotik_health())";
        case "rb_mikrotik_log": return "(await R.mikrotik_log(" + I("N", "20") + "))";
        case "rb_coinbase_value": return "(await R.coinbase_value())";
        case "rb_coinbase_price": return "(await R.coinbase_price(" + pyStr(b.getFieldValue("WHAT")) + ", " + I("PRODUCT", '""') + "))";
        case "rb_coinbase_candles": return "(await R.coinbase_candles(" + pyStr(b.getFieldValue("SIZE")) + ", " + I("PRODUCT", '""') + ", " + I("N", "7") + "))";
        case "rb_coinbase_orders": return "(await R.coinbase_orders(" + pyStr(b.getFieldValue("WHICH")) + "))";
        case "rb_coinbase_preview": return "(await R.coinbase_preview(" + pyStr(b.getFieldValue("SIDE")) + ", " + I("AMOUNT", "0") + ", " + I("PRODUCT", '""') + "))";
        case "rb_mqtt_read": return "(await R.mqtt_value(" + I("TOPIC", '""') + "))";
        case "rb_feed_news": return "(await R.feed_records(" + I("URL", '""') + "))";
        case "rb_calendar": return "(await R.calendar_records(" + I("DAYS", "7") + "))";
        case "rb_chat": return "(await R.chat(" + I("NAME", '"chat"') + ", " + I("TEXT", '""') + "))";
        case "rb_web_search": return "(await R.web_search(" + I("TEXT", '""') + "))";
        case "rb_rec_new": return "{}";
        case "rb_rec_get": return "rec_get(" + I("REC", "None") + ", " + I("KEY", '""') + ")";
        case "rb_rec_has": return "rec_has(" + I("REC", "None") + ", " + I("KEY", '""') + ")";
        case "rb_rec_keys": return "rec_keys(" + I("REC", "None") + ")";
        case "rb_ask_record": return "(await R.ask_record(" + I("FIELDS", '""') + ", " + I("TEXT", '""') + "))";
        case "rb_ask_records": return "(await R.ask_record(" + I("FIELDS", '""') + ", " + I("TEXT", '""') + ", True))";
        case "rb_sort": return "sort_by(" + I("LIST", "[]") + ", " + I("KEY", '""') + ", " + pyStr(F("ORDER") || "desc") + ")";
        case "rb_msg_value": return "R.message_value()";
        case "rb_prompt": return "R.prompt(" + pyStr(String(F("NAME") || "").trim()) + ")";
        case "rb_file_choose": return "(await R.choose_file())";
        case "rb_result_text": return "R.result_text()";
        case "rb_error": return "R.last_error";
        case "rb_mem_has": return "R.remembers(" + I("NAME", '""') + ")";
        case "rb_mem_names": return "R.memory_names()";
        case "rb_img_draw": return "(await R.draw_picture(" + I("TEXT", '""') + "))";
        case "rb_img_change": return "(await R.change_picture(" + I("IMG", "None") + ", " + I("TEXT", '""') + "))";
        case "rb_img_ask": return "(await R.ask_picture(" + I("TEXT", '""') + ", " + I("IMG", "None") + "))";
        case "rb_img_score": return "(await R.score_picture(" + I("IMG", "None") + ", " + I("CRITERIA", '""') + "))";
        default: return "R.unsupported(" + pyStr(b.type) + ")";
      }
    }

    function stmts(first, ind, ctx, out){
      const start = out.length;
      const pad = "    ".repeat(ind);
      const E = s => out.push(pad + s);
      for (let b = first; b; b = b.getNextBlock()) {
        if (!enabled(b)) continue;
        const I = (n, d) => inp(b, n, d);
        const F = n => b.getFieldValue(n);
        const body = (name, extra) => {
          const c = Object.assign({}, ctx, { tick:false }, extra || {});
          const before = out.length;
          if (c.tick) out.push(pad + "    R.tick()");
          stmts(b.getInputTargetBlock(name), ind + 1, c, out);
          if (out.length === before) out.push(pad + "    pass");
        };
        switch (b.type) {
          case "variables_set": E("V[" + pyStr(vname(b)) + "] = " + I("VALUE", '""')); break;
          case "math_change": E("V[" + pyStr(vname(b)) + "] = arith(R.get(" + pyStr(vname(b)) + "), \"ADD\", " + I("DELTA", "1") + ")"); break;
          case "text_append": E("V[" + pyStr(vname(b)) + "] = join(R.get(" + pyStr(vname(b)) + "), " + I("TEXT", '""') + ")"); break;
          case "controls_repeat_ext": E("for _ in times(" + I("TIMES", "0") + "):"); body("DO", { loop:true, tick:true }); break;
          case "controls_whileUntil": E("while " + (F("MODE") === "UNTIL" ? "not " : "") + "to_bool(" + I("BOOL", "False") + "):"); body("DO", { loop:true, tick:true }); break;
          case "controls_if": {
            const n = (b.elseifCount_ || 0) + 1;
            for (let i = 0; i < n; i++) { E((i ? "elif " : "if ") + "to_bool(" + I("IF" + i, "False") + "):"); body("DO" + i); }
            if (b.getInput("ELSE")) { E("else:"); body("ELSE"); }
            break;
          }
          case "controls_forEach": E("for V[" + pyStr(vname(b)) + "] in list(to_list(" + I("LIST", "[]") + ")):"); body("DO", { loop:true, tick:true }); break;
          case "controls_for": E("for V[" + pyStr(vname(b)) + "] in count(" + I("FROM", "1") + ", " + I("TO", "1") + ", " + I("BY", "1") + "):"); body("DO", { loop:true, tick:true }); break;
          case "controls_flow_statements":
            if (ctx.loop) E(F("FLOW") === "BREAK" ? "break" : "continue");
            else E("raise RunError(\"A 'break out of loop' block was used outside a loop.\")");
            break;
          case "procedures_callnoreturn": { const args = (b.arguments_ || []).map((_, i) => I("ARG" + i, '""')); E("await " + procId(b.getProcedureCall()) + "(" + args.join(", ") + ")"); break; }
          case "procedures_ifreturn":
            if (ctx.proc) { E("if to_bool(" + I("CONDITION", "False") + "):"); out.push(pad + "    return " + (b.hasReturnValue_ ? I("VALUE", '""') : "None")); }
            else E("raise RunError(\"A 'return' block was used outside a My Blocks definition.\")");
            break;
          case "lists_setIndex": E("R.list_set(" + listVar(b.getInputTargetBlock("LIST")) + ", " + pyStr(F("MODE")) + ", " + pyStr(F("WHERE")) + ", " + I("AT", "1") + ", " + I("TO", '""') + ")"); break;
          case "lists_getIndex": E(expr(b)); break;
          case "rb_wait": E("await R.wait(num(" + I("SECS", "1") + ") * " + ({ s:1, m:60, h:3600 }[F("UNIT") || "s"] || 1) + ")"); break;
          case "rb_wait_until": {
            const fn = tmp("condition"), t = b.getInputTargetBlock("COND");
            const slow = t ? t.getDescendants(false).some(d => /^rb_(ask|rewrite|extract|score|better)/.test(d.type) || d.type === "procedures_callreturn") : false;
            E("async def " + fn + "():"); out.push(pad + "    return " + I("COND", "False"));
            E("await R.wait_until(" + fn + ", " + (slow ? "True" : "False") + ")");
            break;
          }
          case "rb_wait_time": {
            const h = Math.max(0, Math.min(23, Math.round(Number(F("HOUR")) || 0))), m = Math.max(0, Math.min(59, Math.round(Number(F("MINUTE")) || 0)));
            E("await R.wait_until_time(" + h + ", " + m + ")"); break;
          }
          case "rb_wait_msg": E("await R.wait_for_message(" + pyStr(String(F("MSG") || "").trim()) + ")"); break;
          case "rb_pause": E("await R.pause(" + I("TEXT", '""') + ")"); break;
          case "rb_reset_timer": E("R.reset_timer()"); break;
          case "rb_stop": case "rb_result": E("raise Finish()"); break;
          case "rb_finish_with": E("R.finish_with(" + I("TEXT", '""') + ")"); break;
          case "rb_use_model": E("R.use_model(" + pyStr(F("TIER")) + ")"); break;
          case "rb_with_model": case "rb_with_any_model": {
            E("async with R.using_model(" + pyStr(b.type === "rb_with_any_model" ? "openrouter:" + (String(F("MODEL") || "").trim() || "openrouter/auto") : F("TIER")) + "):");
            const before = out.length;
            stmts(b.getInputTargetBlock("DO"), ind + 1, ctx, out);
            if (out.length === before) out.push(pad + "    pass");
            break;
          }
          case "rb_broadcast": E("R.broadcast(" + I("MSG", '""') + ")"); break;
          case "rb_broadcast_wait": E("await R.broadcast_and_wait(" + I("MSG", '""') + ")"); break;
          case "rb_task": E("R.set_task(" + I("TEXT", '""') + ")"); break;
          case "rb_generate": E("await R.generate(" + (F("WEB") === "TRUE" ? "web=True" : "") + ")"); break;
          case "rb_rework": E("await R.rework(" + I("TEXT", '""') + ")"); break;
          case "rb_revise": E("await R.revise(" + (F("WEB") === "TRUE" ? "web=True" : "") + ")"); break;
          case "rb_set_draft": E("R.set_draft(" + I("TEXT", '""') + ")"); break;
          case "rb_checkpoint_save": E("R.save_checkpoint(" + pyStr(F("NAME") || "") + ")"); break;
          case "rb_checkpoint_restore": E("R.restore_checkpoint(" + pyStr(F("NAME") || "") + ")"); break;
          case "rb_review": E("await R.review(" + I("CRITERIA", '""') + ")"); break;
          case "rb_reflect": {
            const crit = tmp("criteria"), max = tmp("max_rounds"), rnd = tmp("round");
            E(crit + " = " + I("CRITERIA", '""'));
            E(max + " = R.rounds(" + I("ROUNDS", "3") + ")");
            E("with R.reviewing():");
            out.push(pad + "    for " + rnd + " in range(1, " + max + " + 2):");
            out.push(pad + "        R.tick()");
            out.push(pad + "        if await R.review(" + crit + ", \"Review, round \" + str(" + rnd + "), in_loop=True):");
            out.push(pad + "            break");
            out.push(pad + "        if " + rnd + " > " + max + ":");
            out.push(pad + "            R.out_of_rounds()");
            out.push(pad + "            break");
            out.push(pad + "        if R.stuck():");
            out.push(pad + "            break");
            stmts(b.getInputTargetBlock("FIX"), ind + 2, Object.assign({}, ctx, { loop:true }), out);
            break;
          }
          case "rb_ask_me": E("await R.ask_me(" + I("TEXT", '""') + ")"); break;
          case "rb_say": E("R.say(" + I("TEXT", '""') + ")"); break;
          case "rb_set_instructions": E("R.set_instructions(" + I("TEXT", '""') + ")"); break;
          case "rb_clear_instructions": E("R.set_instructions(\"\")"); break;
          case "rb_chat_reset": E("R.chat_reset(" + I("NAME", '"chat"') + ")"); break;
          case "rb_rec_set": E("rec_set(" + I("REC", "None") + ", " + I("KEY", '""') + ", " + I("VALUE", '""') + ")"); break;
          case "rb_broadcast_with": E("R.broadcast(" + I("MSG", '""') + ", " + I("VALUE", '""') + ")"); break;
          case "rb_broadcast_with_wait": E("await R.broadcast_and_wait(" + I("MSG", '""') + ", " + I("VALUE", '""') + ")"); break;
          case "rb_ha_call": E("await R.ha_call(" + I("SERVICE", '""') + ", " + I("ENTITY", '""') + ", " + I("DATA", '""') + ")"); break;
          case "rb_ha_notify": E("await R.ha_notify(" + I("TARGET", '"persistent_notification"') + ", " + I("TEXT", '""') + ")"); break;
          case "rb_ha_speak": E("await R.ha_speak(" + I("TEXT", '""') + ", " + I("PLAYER", '""') + ")"); break;
          case "rb_tg_send": E("await R.tg_send(" + I("TEXT", '""') + ")"); break;
          case "rb_discord_send": case "rb_slack_send": E("await R.chat_send(" + pyStr(b.type === "rb_discord_send" ? "discord" : "slack") + ", " + I("TEXT", '""') + ")"); break;
          case "rb_homey_set": E("await R.homey_set(" + I("DEVICE", '""') + ", " + I("CAPABILITY", '""') + ", " + I("VALUE", '""') + ")"); break;
          case "rb_homey_flow": E("await R.homey_run_flow(" + I("NAME", '""') + ")"); break;
          case "rb_homey_set_variable": E("await R.homey_set_variable(" + I("NAME", '""') + ", " + I("VALUE", '""') + ")"); break;
          case "rb_coinbase_order": E("await R.coinbase_order(" + pyStr(b.getFieldValue("SIDE")) + ", " + I("AMOUNT", "0") + ", " + I("PRODUCT", '""') + ")"); break;
          case "rb_coinbase_cancel": E("await R.coinbase_cancel(" + I("ORDER", '""') + ")"); break;
          case "rb_docker_power": E("await R.docker_power(" + pyStr(b.getFieldValue("ACTION")) + ", " + I("NAME", '""') + ")"); break;
          case "rb_sabnzbd_pause": E("await R.sabnzbd_pause(" + pyStr(b.getFieldValue("ACTION")) + ")"); break;
          case "rb_arr_search": E("await R.arr_search(" + pyStr(b.getFieldValue("WHICH")) + ")"); break;
        case "rb_unraid_container_power": E("await R.unraid_power(\"container\", " + pyStr(b.getFieldValue("ACTION")) + ", " + I("NAME", "plex") + ")"); break;
        case "rb_unraid_vm_power": E("await R.unraid_power(\"vm\", " + pyStr(b.getFieldValue("ACTION")) + ", " + I("NAME", "windows") + ")"); break;
        case "rb_unraid_parity": E("await R.unraid_parity()"); break;
        case "rb_nzbgeek_fetch": E("await R.nzbgeek_fetch(" + I("ID", "\"\"") + ")"); break;
          case "rb_proxmox_power": E("await R.proxmox_power(" + pyStr(b.getFieldValue("ACTION")) + ", " + I("VMID", "0") + ")"); break;
          case "rb_powerwall_reserve": E("await R.powerwall_reserve(" + I("N", "100") + ")"); break;
          case "rb_mqtt_publish": E("await R.mqtt_publish(" + I("TOPIC", '""') + ", " + I("TEXT", '""') + ", " + (F("RETAIN") === "TRUE" ? "True" : "False") + ")"); break;
          case "rb_email_send": E("await R.email_send(" + I("TO", '""') + ", " + I("SUBJECT", '""') + ", " + I("TEXT", '""') + ")"); break;
          case "rb_file_save": E("await R.save_file(" + I("VALUE", '""') + ", " + I("NAME", '"output"') + ", " + pyStr(F("EXT") || "md") + ")"); break;
          case "rb_budget": E("R.set_budget(" + I("TOKENS", "0") + (b.getFieldValue("UNIT") && b.getFieldValue("UNIT") !== "tokens" ? ", " + pyStr(b.getFieldValue("UNIT")) : "") + ")"); break;
          case "rb_agent_tool": case "rb_agent_builtin": case "rb_agent_mcp": case "rb_agent_kraken": break;
          case "rb_agent": {
            const tools = [];
            for (let t = b.getInputTargetBlock("TOOLS"); t; t = t.getNextBlock()) {
              if (!enabled(t)) continue;
              if (t.type === "rb_agent_builtin") tools.push('{"kind": ' + pyStr(t.getFieldValue("KIND")) + "}");
              else if (t.type === "rb_agent_kraken") tools.push('{"kind": "mcp", "server": "kraken", "ask": "never", "command": ' + pyStr(KRAKEN_COMMANDS[t.getFieldValue("MODE")] || KRAKEN_COMMANDS.read) + "}");  // money tools ask anyway
              else if (t.type === "rb_agent_fr24") tools.push('{"kind": "mcp", "server": "flightradar24", "ask": "never", "command": ' + pyStr(FR24_COMMANDS.read) + "}");  // a tool we've never seen asks anyway (#364)
              else if (t.type === "rb_agent_mcp") tools.push('{"kind": "mcp", "server": ' + pyStr(String(t.getFieldValue("SERVER") || "").trim()) + ', "ask": ' + pyStr(t.getFieldValue("ASK") || "changes") + "}");
              else if (t.type === "rb_agent_tool") {
                const name = String(t.getFieldValue("NAME") || "").trim();
                const def = Blockly.Procedures.getDefinition(name, t.workspace || ws);
                const params = def && def.getVarModels ? def.getVarModels().map(varName) : [];
                tools.push('{"kind": "block", "name": ' + pyStr(name) + ', "desc": ' + inp(t, "DESC", '""') + ', "inputs": ' + pyStr(t.getFieldValue("INPUTS") || "") + ', "params": [' + params.map(pyStr).join(", ") +
                  '], "fn": ' + (def ? procId(name) : "None") + ', "ask": ' + (t.getFieldValue("ASK") === "TRUE" ? "True" : "False") + "}");
              }
            }
            E("await R.agent(" + I("GOAL", '""') + ", " + I("STEPS", "6") + ", [" + tools.join(", ") + "]" + (F("PLAN") === "TRUE" ? ", plan=True" : "") + (F("SOURCES") === "TRUE" ? ", sources=True" : "") + ")");
            break;
          }
          case "rb_ask_first": E("R.ask_before(" + pyStr(F("WHAT") || "all") + ")"); break;
          case "rb_try": {
            E("try:");
            const before = out.length;
            stmts(b.getInputTargetBlock("DO"), ind + 1, ctx, out);
            if (out.length === before) out.push(pad + "    pass");
            E("except (Finish, asyncio.CancelledError):");
            out.push(pad + "    raise");
            E("except Exception as _err:");
            out.push(pad + "    R.failed(_err)");
            stmts(b.getInputTargetBlock("FAIL"), ind + 1, ctx, out);
            break;
          }
          case "rb_retry": {
            const at = tmp("attempt"), mx = tmp("max_tries");
            E(mx + " = R.attempts(" + I("TIMES", "3") + ")");
            E("for " + at + " in range(1, " + mx + " + 1):");
            out.push(pad + "    try:");
            const before = out.length;
            stmts(b.getInputTargetBlock("DO"), ind + 2, Object.assign({}, ctx, { loop:false }), out);
            if (out.length === before) out.push(pad + "        pass");
            out.push(pad + "        break");
            out.push(pad + "    except (Finish, asyncio.CancelledError):");
            out.push(pad + "        raise");
            out.push(pad + "    except Exception as _err:");
            out.push(pad + "        await R.retry_or_raise(_err, " + at + ", " + mx + ")");
            break;
          }
          case "rb_mem_set": E("R.remember(" + I("VALUE", '""') + ", " + I("NAME", '""') + ", " + pyStr(F("KIND") || "transient") + ")"); break;
          case "rb_mem_set_for": E("R.remember_for(" + I("VALUE", '""') + ", " + I("NAME", '""') + ", " + I("N", "1") + ", " + pyStr(F("UNIT") || "d") + ")"); break;
          case "rb_mem_add": E("R.remember_add(" + I("VALUE", '""') + ", " + I("NAME", '""') + ", " + pyStr(F("KIND") || "transient") + ")"); break;
          case "rb_mem_forget": E("R.forget(" + I("NAME", '""') + ")"); break;
          case "rb_img_show": E("R.show_picture(" + I("IMG", "None") + ")"); break;
          case "rb_img_save": E("await R.save_picture(" + I("IMG", "None") + ", " + pyStr(F("FORMAT") || "png") + ")"); break;
          case "rb_show": E("R.show()"); break;
          case "rb_add_result": E("R.add_result(" + I("TEXT", '""') + ")"); break;
          default:
            if (b.outputConnection) E(expr(b));
            else E("R.unsupported(" + pyStr(b.type) + ")");
        }
      }
      return out.length - start;
    }

    const sections = [], starts = [], receivers = {}, schedules = [], watches = [], telegram = [], listeners = [];
    const LISTEN = { rb_mqtt_when:["mqtt", "TOPIC", "when an MQTT message arrives on"], rb_webhook_when:["webhook", "PATH", "when a web request arrives at /"],
      rb_email_when:["email", "CONTAINS", "when an email arrives containing"], rb_feed_when:["feed", "URL", "when there's something new in feed"],
      rb_folder_when:["folder", "FOLDER", "when a file appears in folder"], rb_gh_when:["github", null, "when a pull request asks for my review"],
      rb_gh_issue_when:["github_issue", "REPO", "when a new issue is opened in"], rb_gh_release_when:["github_release", "REPO", "when a release is published in"],
      rb_cal_when:["calendar", "N", "when a calendar event starts in"], rb_discord_when:["discord", "CONTAINS", "when a Discord message arrives containing"],
      rb_slack_when:["slack", "CONTAINS", "when a Slack message arrives containing"], rb_page_when:["page", "URL|WORDS|N", "when the web page"],
      rb_homey_when:["homey", "DEVICE|CAPABILITY", "when Homey device"],
      rb_ha_event_when:["ha_event", "EVENT|DATA", "when Home Assistant event"] };
    // Saved programs that 'run program' blocks use, each as one function (its 'when Run is clicked' scripts, in order).
    withSubPrograms(subs => {
      subs.forEach(x => programFn.set(x.key, ident("program_" + x.name)));
      subs.forEach(x => {
        const fn = programFn.get(x.key), out = [];
        out.push("async def " + fn + "():");
        out.push("    \"\"\"Saved program: " + x.name.replace(/"/g, "'") + " (a copy, as it was when this was exported)\"\"\"");
        if (x.problem) {
          out.push("    raise RunError(" + pyStr("The program \u201c" + x.name + "\u201d " + x.problem + ", so it can't run as a block.") + ")");
          sections.push(out.join("\n")); return;
        }
        scope = x.key; scopeTag = x.name + "_";
        const subTops = x.ws.getTopBlocks(true).filter(enabled);
        const defs = subTops.filter(b => b.type === "procedures_defnoreturn" || b.type === "procedures_defreturn");
        defs.forEach(b => procId(b.getFieldValue("NAME")));
        let any = false;
        subTops.filter(b => b.type === "rb_start").forEach(b => { if (stmts(b.getNextBlock(), 1, {}, out)) any = true; });
        if (!any) out.push("    pass");
        const procOut = [];
        defs.forEach(b => {
          const name = b.getFieldValue("NAME");
          const params = (b.getVarModels ? b.getVarModels() : []).map(varName);
          const args = params.map(p => ident("arg_" + p));
          procOut.push("async def " + procId(name) + "(" + args.join(", ") + "):");
          procOut.push("    \"\"\"My Block in " + x.name.replace(/"/g, "'") + ": " + name.replace(/"{3}/g, "\x27\x27\x27") + "\"\"\"");
          procOut.push("    _saved = R.push_args({" + params.map((p, i) => pyStr(p) + ": " + args[i]).join(", ") + "})");
          procOut.push("    try:");
          stmts(b.getInputTargetBlock("STACK"), 2, { proc:true }, procOut);
          procOut.push("        return " + (b.getInput("RETURN") ? inp(b, "RETURN", "None") : "None"));
          procOut.push("    finally:");
          procOut.push("        R.pop_args(_saved)");
          procOut.push("");
        });
        scope = ""; scopeTag = "";
        sections.push((procOut.length ? procOut.join("\n") + "\n\n" : "") + out.join("\n"));
      });
    });
    const tops = ws.getTopBlocks(true).filter(enabled);
    let loose = 0, nStart = 0, nSched = 0;
    // Name every My Blocks function first so calls can refer to them in any order.
    tops.filter(b => b.type === "procedures_defnoreturn" || b.type === "procedures_defreturn").forEach(b => procId(b.getFieldValue("NAME")));
    tops.forEach(b => {
      const out = [];
      if (b.type === "procedures_defnoreturn" || b.type === "procedures_defreturn") {
        const name = b.getFieldValue("NAME");
        const params = (b.getVarModels ? b.getVarModels() : []).map(varName);
        const args = params.map(p => ident("arg_" + p));
        out.push("async def " + procId(name) + "(" + args.join(", ") + "):");
        out.push("    \"\"\"My Block: " + name.replace(/"""/g, "'''") + "\"\"\"");
        out.push("    _saved = R.push_args({" + params.map((p, i) => pyStr(p) + ": " + args[i]).join(", ") + "})");
        out.push("    try:");
        stmts(b.getInputTargetBlock("STACK"), 2, { proc:true }, out);
        out.push("        return " + (b.getInput("RETURN") ? inp(b, "RETURN", "None") : "None"));
        out.push("    finally:");
        out.push("        R.pop_args(_saved)");
      } else if (b.type === "rb_start") {
        const fn = ident("when_run_clicked" + (++nStart > 1 ? "_" + nStart : ""));
        out.push("async def " + fn + "():");
        out.push("    \"\"\"when Run is clicked\"\"\"");
        if (!stmts(b.getNextBlock(), 1, {}, out)) out.push("    pass");
        starts.push(fn);
      } else if (b.type === "rb_receive") {
        const msg = String(b.getFieldValue("MSG") || "").trim();
        const fn = ident("when_i_receive_" + msg);
        out.push("async def " + fn + "():");
        out.push("    \"\"\"when I receive " + msg.replace(/"/g, "'") + "\"\"\"");
        if (!stmts(b.getNextBlock(), 1, {}, out)) out.push("    pass");
        const key = msg.toLowerCase();
        (receivers[key] = receivers[key] || []).push(fn);
      } else if (LISTEN[b.type]) {
        const [kind, field, words] = LISTEN[b.type];
        const arg = !field ? "" : field.split("|").map(f => String(b.getFieldValue(f) == null ? "" : b.getFieldValue(f)).trim()).join("|");
        const fn = ident("when_" + kind + "_" + (listeners.filter(l => l[0] === kind).length + 1));
        out.push("async def " + fn + "():");
        const said = kind === "ha_event" ? " " + (arg.split("|")[0] || "anything") + " happens" + (arg.split("|")[1] ? " with " + arg.split("|")[1] : "")
          : kind === "page" ? (([u, w, n]) => " " + u + " changes" + (w ? " (the part with " + w + ")" : "") + ", checked every " + n + " minutes")(arg.split("|"))
          : field ? " " + (arg.replace("|", " ") || "(your own)") + (kind === "calendar" ? " minutes" : kind === "homey" ? " changes" : "") : "";
        out.push("    \"\"\"" + (words + said).replace(/"/g, "'") + "\"\"\"");
        if (!stmts(b.getNextBlock(), 1, {}, out)) out.push("    pass");
        listeners.push([kind, "(" + pyStr(kind) + ", " + pyStr(arg) + ", " + fn + ")"]);
      } else if (b.type === "rb_tg_when") {
        const contains = String(b.getFieldValue("CONTAINS") || "").trim();
        const fn = ident("when_telegram_message_arrives" + (telegram.length ? "_" + (telegram.length + 1) : ""));
        out.push("async def " + fn + "():");
        out.push("    \"\"\"when a Telegram message arrives containing " + (contains || "anything").replace(/"/g, "'") + "\"\"\"");
        if (!stmts(b.getNextBlock(), 1, {}, out)) out.push("    pass");
        telegram.push("(" + pyStr(contains) + ", " + fn + ")");
      } else if (b.type === "rb_when_time" || b.type === "rb_every") {
        const fn = ident("scheduled_" + (++nSched));
        if (b.type === "rb_every") {
          const secs = Math.max(60, Math.min(86400, (Number(b.getFieldValue("N")) || 1) * (b.getFieldValue("UNIT") === "h" ? 3600 : 60)));
          const label = "Every " + (Number(b.getFieldValue("N")) || 1) + (b.getFieldValue("UNIT") === "h" ? " h" : " min");
          out.push("async def " + fn + "():");
          out.push("    \"\"\"" + label.toLowerCase() + "\"\"\"");
          schedules.push("(\"every\", " + secs + ", " + pyStr(label) + ", " + fn + ")");
        } else {
          const h = Math.max(0, Math.min(23, Math.round(Number(b.getFieldValue("HOUR")) || 0))), m = Math.max(0, Math.min(59, Math.round(Number(b.getFieldValue("MINUTE")) || 0)));
          const days = b.getFieldValue("DAYS") || "every";
          out.push("async def " + fn + "():");
          out.push("    \"\"\"when it's " + String(h).padStart(2, "0") + ":" + String(m).padStart(2, "0") + " (" + days + ")\"\"\"");
          schedules.push("(\"time\", " + h + ", " + m + ", " + pyStr(days) + ", " + fn + ")");
        }
        if (!stmts(b.getNextBlock(), 1, {}, out)) out.push("    pass");
      } else if (b.type === "rb_ha_when") {
        const ent = String(b.getFieldValue("ENTITY") || "").trim(), want = String(b.getFieldValue("STATE") || "").trim();
        const fn = ident("when_" + ent + "_changes");
        out.push("async def " + fn + "():");
        out.push("    \"\"\"when " + ent.replace(/"/g, "'") + " changes to " + (want || "anything").replace(/"/g, "'") + "\"\"\"");
        if (!stmts(b.getNextBlock(), 1, {}, out)) out.push("    pass");
        watches.push("(" + pyStr(ent) + ", " + pyStr(want) + ", " + fn + ")");
      } else { loose++; return; }
      sections.push(out.join("\n"));
    });

    const fileBase = slug(progName);
    const when = new Date();
    const usedServices = servicesUsed(), caps = programCapabilities();
    const usesHA = allProgramBlocks().some(b => b.type.startsWith("rb_ha_"));
    const header = [
      "#!/usr/bin/env python3",
      "\"\"\"" + String(progName || "my-program").replace(/"""/g, "'''"),
      "",
      "Exported from Second Thought on " + when.getFullYear() + "-" + String(when.getMonth() + 1).padStart(2, "0") + "-" + String(when.getDate()).padStart(2, "0") + ", with runtime " + RUNTIME_VERSION + ".",
      "To get a newer runtime: python " + fileBase + ".py --update-runtime (the same major version),",
      "or import this file on the Second Thought page and export it again.",
      "",
      "How to run:",
      "  1. Put your keys in second-thought.ini, in the same folder as this file.",
      "     It came in the zip. No zip? Make a text file with that name containing:",
      "         [keys]",
      ...settingsFor().keys.map(k => "         " + k[1] + " = your-key"),
      usesHA ? "         HA_URL = http://homeassistant.local:8123" : null,
      usesHA ? "         HA_TOKEN = your-long-lived-token" : null,
      "  2. Windows: double-click run.bat" + ((schedules.length || watches.length || telegram.length || listeners.length) ? " (or run-on-schedule.bat to keep it running;" : "."),
      (schedules.length || watches.length || telegram.length || listeners.length) ? "     install-startup.bat makes it start by itself each time you log in)" : null,
      "     Linux or Mac:  sh run.sh" + ((schedules.length || watches.length || telegram.length || listeners.length) ? "   (or sh run-on-schedule.sh to keep it running;" : ""),
      (schedules.length || watches.length || telegram.length || listeners.length) ? "     sh install-service.sh makes it start by itself, on Linux or a Mac)" : null,
      "     Or by hand:  pip install " + usedServices.flatMap(s => s.pip || []).join(" ") + ", then  python " + fileBase + ".py" + ((schedules.length || watches.length || telegram.length || listeners.length) ? " [--schedule]" : ""),
      "  Environment variables with the same names still work, and win over the file.",
      "",
      ...canHeader(caps, usedServices),
      ...usedServices.flatMap(s => s.note || []),
      ...usedServices.flatMap(s => s.setup || []),
      "Claude calls go through the Anthropic API and are billed to your API account,",
      "not your claude.ai plan. To change model, set primary in second-thought.ini",
      "(quick, default, complex, gemini-default and so on), or edit MODELS below.",
      "Backup models (tried in order if the main one fails on a step) are in BACKUPS below;",
      "backups in second-thought.ini overrides them, and backups = none turns them off.",
      "\"\"\"",
      ""
    ].filter(l => l !== null).join("\n");
    const program = [
      "",
      "# ---------------------------------------------------------------------------",
      "# Your program",
      "# ---------------------------------------------------------------------------",
      "DEFAULT_TIER = " + pyStr($("tier").value),
      "BACKUPS = [" + backupTiers().map(pyStr).join(", ") + "]  # tried in order if DEFAULT_TIER fails on a step",
      "PROMPTS = {" + [...new Set(allProgramBlocks().filter(b => b.type === "rb_prompt").map(b => String(b.getFieldValue("NAME") || "").trim().toLowerCase()))]
        .filter(k => lib.prompt.has(k)).map(k => pyStr(k) + ": " + pyStr(lib.prompt.get(k).text)).join(", ") + "}",
      "R = Runtime()",
      "V = R.vars",
      loose ? "# " + loose + " loose block" + (loose === 1 ? " wasn't" : "s weren't") + " attached to a script, so " + (loose === 1 ? "it was" : "they were") + " left out." : null,
      "",
      sections.join("\n\n\n"),
      "",
      "",
      "START_SCRIPTS = [" + starts.join(", ") + "]",
      "RECEIVERS = {" + Object.keys(receivers).map(k => pyStr(k) + ": [" + receivers[k].join(", ") + "]").join(", ") + "}",
      "SCHEDULES = [" + schedules.join(", ") + "]",
      "HA_WATCHES = [" + watches.join(", ") + "]",
      telegram.length ? "TELEGRAM_WATCHES = [" + telegram.join(", ") + "]" : null,
      listeners.length ? "LISTENERS = [" + listeners.map(l => l[1]).join(", ") + "]" : null,
      "# What this program can do (listed in the notes at the top). If any of it acts on the world, the program asks",
      "# before its first run, and again whenever this file changes.",
      "CAN = {\"services\": [" + usedServices.map(x => pyStr(x.name)).join(", ") + "], \"can\": [" + caps.map(c => pyStr(c[0])).join(", ") + "]" +
        (settingsFor().mcp.length ? ", \"mcp\": [" + settingsFor().mcp.map(pyStr).join(", ") + "]" : "") +
        (krakenMode() ? ", \"kraken\": " + pyStr(krakenMode()) : "") +
        (settingsFor().flightradar24 ? ", \"flightradar24\": \"read\"" : "") + "}",
      "",
      "if __name__ == \"__main__\":",
      "    R.main(START_SCRIPTS, RECEIVERS, SCHEDULES, HA_WATCHES" + (telegram.length ? ", TELEGRAM_WATCHES" : "") + (listeners.length ? ", listeners=LISTENERS" : "") + ", can=CAN)",
      ""
    ].filter(l => l !== null).join("\n");
    const words = exportWords();
    const speaks = words ? ["# The language this program prints in (language = en in second-thought.ini switches it to English), and its words.",
      "EXPORT_LANGUAGE = " + pyStr(window.ST_LANG), "EXPORT_WORDS = {", ...Object.keys(words).map(k => "    " + JSON.stringify(k) + ": " + JSON.stringify(words[k]) + ","), "}", "", ""].join("\n") : "";
    const code = header + speaks + document.getElementById("py-runtime").textContent.replace(/^\n+/, "") + "\n" + program;
    const payload = b64encode(JSON.stringify(Object.assign({ format:FORMAT, version:FORMAT_VERSION, name:progName, program:saveWs() }, programTests.length ? { tests:programTests } : {})));
    const lines = [code.replace(/\n+$/, ""), "", "", PY_MARK, "# CODE-HASH: " + codeHash(code), "# BLOCKS:"];
    for (let i = 0; i < payload.length; i += 76) lines.push("# " + payload.slice(i, i + 76));
    return lines.join("\n") + "\n";
  }

  function readExported(code){
    const norm = String(code).replace(/\r\n?/g, "\n");
    const at = PY_MARKS.map(m => norm.indexOf(m)).filter(i => i >= 0).sort((a, b) => a - b)[0];
    if (at === undefined) return null;
    const above = norm.slice(0, at);
    let hash = null, inBlocks = false, b64 = "";
    norm.slice(at).split("\n").forEach(line => {
      const m = line.match(/^#\s*CODE-HASH:\s*([0-9a-f]+)/i);
      if (m) { hash = m[1].toLowerCase(); return; }
      if (/^#\s*BLOCKS:\s*$/.test(line)) { inBlocks = true; return; }
      if (inBlocks) { const d = line.match(/^#\s*([A-Za-z0-9+/=]+)\s*$/); if (d) b64 += d[1]; }
    });
    try {
      const data = JSON.parse(b64decode(b64));
      if (!data || !data.program) return null;
      const v = above.match(/^RUNTIME_VERSION = "([^"]+)"/m);
      return { data, edited: !hash || codeHash(above) !== hash, runtime: v ? v[1] : "" };
    } catch(e) { return null; }
  }

