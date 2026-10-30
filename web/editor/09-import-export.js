  // 09-import-export.js: Import and export: block files, backup models, Save as GitHub Actions.
  /* ---------- Import / export ---------- */
  /* ----- Backup models: tried in order when the primary (the Model menu) fails on a step ----- */
  const BK_LS = "second-thought-backups";
  function backupTiers(){
    const primary = $("tier").value, seen = new Set([primary]);
    return ["bk-1", "bk-2", "bk-3"].map(id => $(id).value).filter(t => t && !seen.has(t) && seen.add(t));
  }
  function showBackups(){
    const n = backupTiers().length;
    $("bk-toggle").textContent = n ? tr("Backups ({n})", { n }) : tr("Backups");
    const same = ["bk-1", "bk-2", "bk-3"].some(id => $(id).value && $(id).value === $("tier").value);
    $("bk-msg").textContent = same ? "A backup is the same as the primary model, so it is skipped." : n ? "Order: " + [$("tier").value].concat(backupTiers()).map(tierLabel).join(" \u2192 ") : "No backups: if the primary fails, the step fails.";
  }
  (function setupBackups(){
    const opts = [["(none)", ""]].concat(TIERS);
    let saved = [];
    try { saved = JSON.parse(localStorage.getItem(BK_LS) || "[]"); } catch(e) {}
    ["bk-1", "bk-2", "bk-3"].forEach((id, i) => {
      const sel = $(id);
      opts.forEach(([label, value]) => { const o = document.createElement("option"); o.value = value; o.textContent = label; sel.appendChild(o); });
      if (saved[i] && TIERS.some(t => t[1] === saved[i])) sel.value = saved[i];
      sel.onchange = () => { try { localStorage.setItem(BK_LS, JSON.stringify(["bk-1", "bk-2", "bk-3"].map(x => $(x).value))); } catch(e) {} showBackups(); };
    });
    $("tier").addEventListener("change", showBackups);
    $("bk-toggle").onclick = () => {
      const bk = $("bk"), open = bk.hidden;
      bk.hidden = !open; $("bk-toggle").setAttribute("aria-expanded", String(open));
      setTimeout(() => Blockly.svgResize(ws), 0);
    };
    showBackups();
  })();

  const FORMAT = "reflection-blocks";
  const ioMsg = (id, text, kind) => { const m = $(id); m.textContent = tr(text); m.className = "msg" + (kind ? " " + kind : ""); };
  $("io-toggle").onclick = () => {
    const io = $("io"), open = io.hidden;
    io.hidden = !open; $("io-toggle").setAttribute("aria-expanded", String(open));
    if (open) { ioMsg("io-export-msg", ""); $("io-export-text").hidden = true; }
    setTimeout(() => Blockly.svgResize(ws), 0);
  };
  let downloads = null;
  if (window.claude && window.claude.use) {
    window.claude.use("downloads").then(d => { downloads = d; $("io-save").hidden = !d; $("io-py-save").hidden = !d; $("io-gha-save").hidden = !d; $("log-save").hidden = !d; }).catch(() => {});
  }
  function slug(name){
    const s = String(name || "").trim().replace(/\.json$/i, "").replace(/[^\w\- ]+/g, "").replace(/\s+/g, "-").slice(0, 80);
    return s || "my-program";
  }
  function exportText(){
    return JSON.stringify(Object.assign({ format:FORMAT, version:FORMAT_VERSION, name:$("io-name").value.trim() || "my-program",
      exported:new Date().toISOString(), program:saveWs() }, programTests.length ? { tests:programTests } : {}), null, 2);
  }
  $("io-save").onclick = async () => {
    if (!downloads) return;
    const btn = $("io-save"); btn.disabled = true;
    try {
      const r = await downloads.save({ filename:slug($("io-name").value) + ".json", data:exportText() });
      ioMsg("io-export-msg", r.status === "saved" ? tr("Saved {file}.", { file:slug($("io-name").value) + ".json" }) : "File sent.", "ok");
    } catch(e) {
      const code = e && e.code;
      if (code === "declined") ioMsg("io-export-msg", "Save cancelled.");
      else if (code === "rate_limited") ioMsg("io-export-msg", "A save prompt is already open. Finish that one first.", "bad");
      else { $("io-save").hidden = true; $("io-py-save").hidden = true; ioMsg("io-export-msg", "Saving files isn't available here. Use Copy as text instead.", "bad"); }
    } finally { btn.disabled = false; }
  };
  $("io-copy").onclick = async () => {
    const text = exportText(), ta = $("io-export-text");
    ta.value = text;
    ta.dataset.kind = "json"; $("io-py-show").textContent = tr("Show code");
    try { await navigator.clipboard.writeText(text); ta.hidden = true; ioMsg("io-export-msg", "Copied. Paste it anywhere to keep or share it.", "ok"); }
    catch(e) { ta.hidden = false; ta.focus(); ta.select(); ioMsg("io-export-msg", "Copy isn't allowed here, so the text is selected below. Press Ctrl+C (or Cmd+C).", "bad"); }
  };

  const pyName = () => slug($("io-name").value);
  // Everything in the exported zip: the program, its settings file, what to install, and Windows launchers.
  function exportFiles(progName, code){
    const base = pyName(), sched = ws.getTopBlocks(false).some(b => ["rb_when_time", "rb_every", "rb_ha_when"].includes(b.type) || LISTENER_HATS.has(b.type));
    const req = servicesUsed().flatMap(s => s.pip || []).concat(settingsFor().calendar ? ["tzdata"] : [], settingsFor().mqtt ? ["paho-mqtt>=2"] : []).join("\n") + "\n";
    const files = [{ name:base + ".py", text:code }, { name:"second-thought.ini", text:iniText(progName) },
                   { name:"requirements.txt", text:req }, { name:"run.bat", text:runBat(base, false) },
                   { name:"run.sh", text:runSh(base, false) }];
    if (sched) files.push({ name:"run-on-schedule.bat", text:runBat(base, true) }, { name:"run-on-schedule.sh", text:runSh(base, true) },
                          { name:"install-startup.bat", text:installStartupBat(base) }, { name:"install-service.sh", text:installServiceSh(base) });
    if (programTests.length) files.push({ name:base + ".tests.json", text:JSON.stringify(programTests, null, 1) + "\n" });
    return files;
  }
  window.__zipBase64 = async () => { const b = new Uint8Array(await makeZip(window.__exportFiles()).arrayBuffer()); let t = ""; b.forEach(x => t += String.fromCharCode(x)); return btoa(t); };
  window.__exportFiles = () => exportFiles($("io-name").value.trim() || "my-program", toPython($("io-name").value.trim() || "my-program"));
  // ----- Save as GitHub Actions: the program runs at its scheduled times on GitHub's computers, with no computer of yours on -----
  const ASK_BLOCKS = new Set(["rb_ask_me", "rb_approve", "rb_choose", "rb_img_choose", "rb_ask_record", "rb_ask_records", "rb_file_choose", "rb_pause"]);
  const isOn = b => !b.isEnabled || b.isEnabled();
  const exportedScheduleHats = () => ws.getTopBlocks(true).filter(isOn).filter(b => b.type === "rb_when_time" || b.type === "rb_every");
  // Every block a scheduled script can reach: its own blocks, the 'when I receive' scripts it broadcasts to, and the
  // My Blocks it calls. A message worked out while running could be any of them, so it reaches every receiver.
  function scheduledBlocks(){
    const tops = ws.getTopBlocks(true).filter(isOn), seen = new Set(), queue = exportedScheduleHats(), out = [];
    while (queue.length) {
      const t = queue.shift();
      if (seen.has(t.id)) continue;
      seen.add(t.id);
      t.getDescendants(false).forEach(d => {
        out.push(d);
        if (/^rb_broadcast/.test(d.type)) {
          const mb = d.getInputTargetBlock("MSG"), msg = mb && mb.type === "text" ? String(mb.getFieldValue("TEXT") || "").trim().toLowerCase() : null;
          tops.filter(r => r.type === "rb_receive" && (msg === null || String(r.getFieldValue("MSG") || "").trim().toLowerCase() === msg)).forEach(r => queue.push(r));
        }
        if (/^procedures_call/.test(d.type))
          tops.filter(r => /^procedures_def/.test(r.type) && r.getFieldValue("NAME") === d.getFieldValue("NAME")).forEach(r => queue.push(r));
      });
    }
    return out;
  }
  // Why this program can't run on GitHub Actions, or "" if it can.
  function actionsProblem(){
    const tops = ws.getTopBlocks(true).filter(isOn), need = settingsFor();
    if (tops.some(b => LISTENER_HATS.has(b.type) || b.type === "rb_tg_when" || b.type === "rb_ha_when"))
      return tr("it waits for things to happen, like messages, web requests or changes, and GitHub Actions only runs it at set times");
    if (need.llama || need.mcp.length || allProgramBlocks().some(b => b.type === "rb_folder_files"))
      return tr("it uses Llama, MCP servers or folders on your own computer, which GitHub can't reach");
    if (!exportedScheduleHats().length) return tr("it has no 'when it's' or 'every' script, so there's nothing to run on a schedule");
    if (scheduledBlocks().some(b => ASK_BLOCKS.has(b.type))) return tr("it asks you questions while it runs, and nobody is there to answer");
    return "";
  }
  // The settings a program needs, as [setting, the repository secret it comes from, required].
  function actionsSecrets(){
    const n = settingsFor(), out = n.keys.map(k => [k[1], k[1], true]);
    const add = (on, req, opt) => { if (on) { req.forEach(k => out.push([k, k, true])); (opt || []).forEach(k => out.push([k, k, false])); } };
    add(n.ha, ["HA_URL", "HA_TOKEN"]);
    if (n.github) out.push(["GITHUB_TOKEN", "ST_GITHUB_TOKEN", true]);  // secret names can't start with GITHUB_
    add(n.telegram, ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]);
    add(n.discord, ["DISCORD_BOT_TOKEN", "DISCORD_CHANNEL_ID"]);
    add(n.slack, ["SLACK_BOT_TOKEN", "SLACK_CHANNEL_ID"]);
    add(n.email, ["EMAIL_ADDRESS", "EMAIL_PASSWORD"], ["EMAIL_IMAP_HOST", "EMAIL_SMTP_HOST"]);
    add(n.calendar, ["CALENDAR_URL"]);
    add(n.feeds, ["RB_FEEDS"]);
    add(n.homey, ["HOMEY_URL", "HOMEY_API_KEY"]);
    add(n.mqtt, ["MQTT_HOST"], ["MQTT_USERNAME", "MQTT_PASSWORD", "MQTT_TLS"]);
    return out;
  }
  // GitHub's cron lines for one schedule. Times are UTC there, so a 'when it's' script gets one line for each offset
  // its time zone has in the year (winter and summer), and the program itself skips the one that isn't its time.
  function actionsCrons(b){
    if (b.type === "rb_every") {
      const n = Math.max(1, Number(b.getFieldValue("N")) || 1), hours = b.getFieldValue("UNIT") === "h";
      if (hours && n >= 24) return [{ cron:"0 0 * * *", note:"once a day" }];
      if (hours) return [{ cron:"0 */" + n + " * * *", note:24 % n ? "every " + n + " h, starting again at midnight UTC" : "" }];
      const m = Math.max(5, n);
      if (m >= 60) return [{ cron:"0 * * * *", note:"every hour" }];
      return [{ cron:"*/" + m + " * * * *", note:(n < 5 ? "GitHub runs schedules at most every 5 minutes" : "") + (60 % m ? "every " + m + " min, starting again each hour" : "") }];
    }
    const h = Math.max(0, Math.min(23, Math.round(Number(b.getFieldValue("HOUR")) || 0))), mi = Math.max(0, Math.min(59, Math.round(Number(b.getFieldValue("MINUTE")) || 0)));
    const days = { every:[0, 1, 2, 3, 4, 5, 6], weekdays:[1, 2, 3, 4, 5], weekends:[0, 6] }[b.getFieldValue("DAYS") || "every"] || [0, 1, 2, 3, 4, 5, 6];
    const y = new Date().getFullYear(), seen = new Map();
    // Winter is the month on standard time, the one further behind UTC: January in the north, July in the south.
    const winter = new Date(y, 0, 15).getTimezoneOffset() >= new Date(y, 6, 15).getTimezoneOffset() ? 0 : 6;
    [winter, 6 - winter].forEach(month => {
      const local = new Date(y, month, 15, h, mi), utcMin = local.getUTCHours() * 60 + local.getUTCMinutes();
      const shift = Math.floor((h * 60 + mi + local.getTimezoneOffset()) / 1440);  // the day it is in UTC, against the day it is here
      const ds = days.map(d => (d + shift + 7) % 7).sort((a, c) => a - c);
      const dow = days.length === 7 ? "*" : ds.length > 2 && ds[ds.length - 1] - ds[0] === ds.length - 1 ? ds[0] + "-" + ds[ds.length - 1] : ds.join(",");
      const cron = (utcMin % 60) + " " + Math.floor(utcMin / 60) + " * * " + dow;
      if (!seen.has(cron)) seen.set(cron, month === winter ? "winter" : "summer");
    });
    return [...seen].map(([cron, when]) => ({ cron, note:seen.size > 1 ? when : "" }));
  }
  function actionsFiles(progName, code){
    const why = actionsProblem();
    if (why) throw new Error(why);
    const base = pyName(), tz = (Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"), secrets = actionsSecrets();
    const hats = exportedScheduleHats(), q = JSON.stringify;
    const label = (b, i) => (i + 1) + ": " + (b.type === "rb_every" ? "every " + (Number(b.getFieldValue("N")) || 1) + (b.getFieldValue("UNIT") === "h" ? " h" : " min")
      : "when it's " + String(b.getFieldValue("HOUR")).padStart(2, "0") + ":" + String(b.getFieldValue("MINUTE")).padStart(2, "0") + " (" + (b.getFieldValue("DAYS") || "every") + ")");
    const byCron = new Map(), cronLines = [];
    hats.forEach((b, i) => actionsCrons(b).forEach(c => {
      if (!byCron.has(c.cron)) { byCron.set(c.cron, []); cronLines.push("    - cron: " + q(c.cron) + "   # script " + label(b, i) + (c.note ? ", " + c.note : "")); }
      else cronLines.push("    # " + q(c.cron) + " also runs script " + label(b, i) + (c.note ? ", " + c.note : ""));
      byCron.get(c.cron).push(i + 1);
    }));
    const run = n => "python " + base + ".py --run-schedule " + n + " || failed=1";
    const wf = [
      "# " + progName + ": runs on GitHub Actions at the times its 'when it's' and 'every' scripts say.",
      "# Saved from Second Thought with runtime " + RUNTIME_VERSION + ". SETUP.md says which secrets to add.",
      "#",
      "# GitHub's schedules are in UTC. The times below are worked out for " + tz + ". Where the clocks change there,",
      "# a script has a line for winter and one for summer, and the program only runs it within an hour after its",
      "# time, so the other line does nothing. GitHub often starts scheduled runs a few minutes late, and now and then",
      "# skips one when it's busy. To change a time, change the program on the page and save it again.",
      "name: " + q(progName),
      "on:",
      "  schedule:",
      ...cronLines,
      "  workflow_dispatch:   # the Run workflow button on the Actions tab: runs a script now",
      "    inputs:",
      "      script:",
      "        description: Which script to run now",
      "        type: choice",
      "        options:",
      ...hats.map((b, i) => "          - " + q(label(b, i))),
      "permissions:",
      "  contents: write   # to save what the program remembers (memory.json) and makes (outputs/) back to the repository",
      "concurrency:",
      "  group: " + q(base),
      "  cancel-in-progress: false",
      "jobs:",
      "  run:",
      "    runs-on: ubuntu-latest",
      "    timeout-minutes: 30",
      "    steps:",
      "      - uses: actions/checkout@v4",
      "      - uses: actions/setup-python@v5",
      "        with:",
      "          python-version: \"3.12\"",
      "          cache: pip",
      "      - run: pip install -r requirements.txt",
      "      - name: Run the script that's due",
      "        env:",
      "          TZ: " + q(tz),
      "          RB_APPROVE: \"no\"   # adding this workflow to your repository is your yes to what it can do (SETUP.md lists it)",
      "          PYTHONIOENCODING: utf-8",
      "          SCHEDULE: ${{ github.event.schedule }}",
      "          SCRIPT: ${{ inputs.script }}",
      ...secrets.map(([env, secret]) => "          " + env + ": ${{ secrets." + secret + " }}"),
      "        run: |",
      "          failed=0",
      "          case \"$SCHEDULE\" in",
      ...[...byCron].map(([cron, ns]) => "            " + q(cron) + ") " + ns.map(run).join("; ") + " ;;"),
      "            \"\") python " + base + ".py --run-schedule \"${SCRIPT%%:*}\" --now || failed=1 ;;",
      "          esac",
      "          exit $failed",
      "      - name: Keep what it remembered",
      "        if: always()",
      "        run: |",
      "          git config user.name \"second-thought\"",
      "          git config user.email \"second-thought@users.noreply.github.com\"",
      "          for f in memory.json outputs; do if [ -e \"$f\" ]; then git add \"$f\"; fi; done",
      "          git diff --cached --quiet || { git commit -m \"What " + base.replace(/"/g, "") + " remembered\" && git push; }",
      "      # To keep memory.json out of the repository instead (for a public one), delete the step above and use",
      "      # actions/cache: restore it before the run and save it after. A cache GitHub hasn't used for 7 days is deleted.",
      ""
    ].join("\n");
    const caps = programCapabilities();
    const setup = [
      "# " + progName + " on GitHub Actions", "",
      "This runs the program's scheduled scripts on GitHub's computers, so yours doesn't need to be on.", "",
      "## Set it up", "",
      "1. Make a **private** repository on GitHub. (What the program remembers is saved in it, in `memory.json`.)",
      "2. Put these files in it, keeping `.github/workflows/" + base + ".yml` in that folder.",
      "3. In the repository, go to **Settings → Secrets and variables → Actions → New repository secret**, and add:", "",
      ...secrets.map(([env, secret, req]) => "   - `" + secret + "`" + (req ? "" : " (if you need it)") + (secret !== env ? ": the token you'd put as " + env + " (GitHub doesn't allow secret names starting GITHUB_)" : "")),
      "",
      "4. On the **Actions** tab, choose the workflow and **Run workflow** to try a script now.", "",
      "## Good to know", "",
      "- Times are worked out for " + tz + ". GitHub often starts a scheduled run a few minutes late, and sometimes skips one.",
      "- On GitHub's free plan, private repositories get 2,000 minutes a month. Each run takes about a minute.",
      "- Home Assistant, Homey and MQTT have to be reachable from the internet, not just your home network.",
      "- Model calls are billed to your API accounts, as on your own computer.",
      ...(caps.some(c => c[2]) ? ["", "## What it can do", "", "Adding the workflow is your yes to these, as answering y is when it runs on your computer:", "",
        ...caps.map(c => "- " + c[1])] : []),
      ""
    ].join("\n");
    const req = servicesUsed().flatMap(s => s.pip || []).concat(settingsFor().calendar ? ["tzdata"] : [], settingsFor().mqtt ? ["paho-mqtt>=2"] : []).join("\n") + "\n";
    return [{ name:base + ".py", text:code }, { name:"requirements.txt", text:req }, { name:".github/workflows/" + base + ".yml", text:wf },
            { name:"SETUP.md", text:setup }, { name:".gitignore", text:"second-thought.ini\n__pycache__/\n" }];
  }
  window.__actionsFiles = () => { try { return actionsFiles($("io-name").value.trim() || "my-program", toPython($("io-name").value.trim() || "my-program")); } catch(e) { return { error:e.message }; } };
  $("io-gha-save").onclick = async () => {
    if (!downloads) return;
    const btn = $("io-gha-save"); btn.disabled = true;
    try {
      const why = actionsProblem();
      if (why) { ioMsg("io-export-msg", tr("This program can't run on GitHub Actions: {why}.", { why }), "bad"); return; }
      const files = actionsFiles($("io-name").value.trim() || "my-program", toPython($("io-name").value.trim() || "my-program"));
      const r = await downloads.save({ filename:pyName() + "-actions.zip", data:makeZip(files) });
      ioMsg("io-export-msg", r.status === "saved" ? tr("Saved {name}-actions.zip. Put its files in a private GitHub repository and add the secrets SETUP.md lists; then it runs on schedule.", { name:pyName() }) : "File sent.", "ok");
    } catch(e) {
      const code = e && e.code;
      if (code === "declined") ioMsg("io-export-msg", "Save cancelled.");
      else if (code === "rate_limited") ioMsg("io-export-msg", "A save prompt is already open. Finish that one first.", "bad");
      else if (e instanceof Error) ioMsg("io-export-msg", tr("The code couldn't be generated: {problem}", { problem:e.message }), "bad");
      else ioMsg("io-export-msg", "Saving files isn't available here. Use Copy Python code instead.", "bad");
    } finally { btn.disabled = false; }
  };
  $("io-py-save").onclick = async () => {
    if (!downloads) return;
    const btn = $("io-py-save"); btn.disabled = true;
    try {
      const code = toPython($("io-name").value.trim() || "my-program");
      const files = exportFiles($("io-name").value.trim() || "my-program", code);
      const zip = makeZip(files);
      const r = await downloads.save({ filename:pyName() + ".zip", data:zip });
      ioMsg("io-export-msg", r.status === "saved" ? tr("Saved {name}.zip. Unzip it, put your keys in second-thought.ini, then run {name}.py (on Windows, double-click run.bat).", { name:pyName() }) : "File sent.", "ok");
    } catch(e) {
      const code = e && e.code;
      if (code === "declined") ioMsg("io-export-msg", "Save cancelled.");
      else if (code === "rate_limited") ioMsg("io-export-msg", "A save prompt is already open. Finish that one first.", "bad");
      else if (e instanceof Error) ioMsg("io-export-msg", tr("The code couldn't be generated: {problem}", { problem:e.message }), "bad");
      else ioMsg("io-export-msg", "Saving files isn't available here. Use Copy Python code instead.", "bad");
    } finally { btn.disabled = false; }
  };
  $("io-py-copy").onclick = async () => {
    let code;
    try { code = toPython($("io-name").value.trim() || "my-program"); }
    catch(e) { ioMsg("io-export-msg", "The code couldn't be generated: " + (e && e.message ? e.message : "unknown error"), "bad"); return; }
    const ta = $("io-export-text");
    ta.value = code;
    try { await navigator.clipboard.writeText(code); ta.hidden = true; ioMsg("io-export-msg", tr("Python code copied. Save it as {name}.py.", { name:pyName() }), "ok"); }
    catch(e) { ta.hidden = false; ta.focus(); ta.select(); ioMsg("io-export-msg", tr("Copy isn't allowed here, so the code is selected below. Press Ctrl+C (or Cmd+C), then save it as {name}.py.", { name:pyName() }), "bad"); }
  };
  $("io-py-show").onclick = () => {
    const ta = $("io-export-text");
    if (!ta.hidden && ta.dataset.kind === "py") { ta.hidden = true; $("io-py-show").textContent = tr("Show code"); return; }
    try { ta.value = toPython($("io-name").value.trim() || "my-program"); }
    catch(e) { ioMsg("io-export-msg", "The code couldn't be generated: " + (e && e.message ? e.message : "unknown error"), "bad"); return; }
    ta.dataset.kind = "py"; ta.hidden = false; $("io-py-show").textContent = tr("Hide code");
    const at = ta.value.indexOf("# Your program"); if (at > 0) { ta.focus(); ta.setSelectionRange(at, at); ta.scrollTop = ta.scrollHeight * (at / ta.value.length) - 20; ta.blur(); }
  };

  let beforeImport = null, beforeImportTests = [];
  function unknownTypes(state){
    const bad = new Set();
    const walk = o => {
      if (!o || typeof o !== "object") return;
      if (Array.isArray(o)) { o.forEach(walk); return; }
      if (typeof o.type === "string" && (o.fields || o.inputs || o.next || o.x !== undefined || o.id || o.extraState || o.type.includes("_"))) {
        if (!Blockly.Blocks[o.type]) bad.add(o.type);
      }
      Object.keys(o).forEach(k => { if (k !== "fields" && k !== "extraState") walk(o[k]); });
    };
    walk(state.blocks);
    return [...bad];
  }
  function applyProgram(state, name, converted, version, tests){
    if (!state || typeof state !== "object" || !state.blocks || !Array.isArray(state.blocks.blocks)) {
      ioMsg("io-import-msg", "This doesn't look like a Second Thought program. Export one from this page and import that file.", "bad"); return false;
    }
    let from = FORMAT_VERSION;
    try { ({ state, from } = migrateProgram(state, converted ? FORMAT_VERSION : version)); }
    catch(e) { ioMsg("io-import-msg", e.message, "bad"); return false; }
    const bad = unknownTypes(state);
    if (bad.length) { ioMsg("io-import-msg", tr("This program uses blocks this page doesn't have: {blocks}.", { blocks:bad.join(", ") }), "bad"); return false; }
    const prev = saveWs();
    try {
      load(state);
      if (converted) { try { ws.cleanUp(); } catch(e) {} }
    } catch(e) {
      load(prev);
      ioMsg("io-import-msg", tr("The program couldn't be loaded, so your canvas was left as it was. ({problem})", { problem:e && e.message ? e.message : tr("unknown error") }), "bad");
      return false;
    }
    beforeImport = prev; beforeImportTests = programTests;
    setTests(tests === undefined ? (converted === "change" ? programTests : []) : tests);
    $("io-undo").hidden = false;
    clearChoice();
    const count = ws.getAllBlocks(false).length;
    const can = capabilitySentence(programCapabilities());
    ioMsg("io-import-msg", tr(converted ? (name ? "Converted \u201c{name}\u201d ({n} blocks)." : "Converted program ({n} blocks).") : (name ? "Loaded \u201c{name}\u201d ({n} blocks)." : "Loaded program ({n} blocks)."), { name, n:count }) + (can ? " " + can : "") +
      (from < FORMAT_VERSION ? " " + tr("It was saved with older blocks and has been brought up to date (block format {from} to {to}).", { from, to:FORMAT_VERSION }) : ""), "ok");
    try { ws.zoomToFit(); } catch(e) {}
    return true;
  }
  function importText(text, sourceLabel){
    const t = String(text).replace(/^\uFEFF/, "");
    if (!/^\s*[\[{]/.test(t)) { importCode(t, sourceLabel); return false; }
    let data;
    try { data = JSON.parse(t); }
    catch(e) { ioMsg("io-import-msg", "That isn't valid program text. Export a program from this page and import that file.", "bad"); return false; }
    const isOurs = data && data.format === FORMAT;
    const ok = applyProgram(isOurs ? data.program : data, isOurs && data.name ? data.name : sourceLabel, false, isOurs ? data.version : 1, isOurs ? data.tests || [] : []);
    if (ok && isOurs && data.name) $("io-name").value = slug(data.name);
    return ok;
  }
  function readFile(file){
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) { ioMsg("io-import-msg", "That file is over 5 MB, which is too big for a program file.", "bad"); return; }
    clearChoice();
    const label = file.name.replace(/\.(json|py|txt|zip)$/i, "");
    if (/\.zip$/i.test(file.name)) {
      file.arrayBuffer().then(readZipCode).then(f => importText(f.text, f.name.replace(/\.(json|py|txt)$/i, "")))
        .catch(e => ioMsg("io-import-msg", tr("That zip couldn't be opened: {problem}.", { problem:e && e.message ? e.message : tr("unknown error") }), "bad"));
      return;
    }
    const r = new FileReader();
    r.onload = () => importText(String(r.result), label);
    r.onerror = () => ioMsg("io-import-msg", "The file couldn't be read. Try choosing it again.", "bad");
    r.readAsText(file);
  }
  $("io-file").onchange = e => { readFile(e.target.files && e.target.files[0]); e.target.value = ""; };
  $("io-load-paste").onclick = () => {
    const t = $("io-paste").value.trim();
    if (!t) { ioMsg("io-import-msg", "Paste program text or code into the box first.", "bad"); $("io-paste").focus(); return; }
    clearChoice();
    if (importText(t, "")) $("io-paste").value = "";
  };
  $("io-paste").addEventListener("input", () => ioMsg("io-import-msg", ""));
  $("io-undo").onclick = () => {
    if (!beforeImport) return;
    load(beforeImport); beforeImport = null; $("io-undo").hidden = true; setTests(beforeImportTests);
    ioMsg("io-import-msg", "Import undone. Your previous program is back.", "ok");
  };
  const canvasEl = document.querySelector(".canvas");
  canvasEl.addEventListener("dragover", e => { if (e.dataTransfer && [...e.dataTransfer.types].includes("Files")) { e.preventDefault(); canvasEl.classList.add("dropping"); } });
  canvasEl.addEventListener("dragleave", () => canvasEl.classList.remove("dropping"));
  canvasEl.addEventListener("drop", e => {
    if (!e.dataTransfer || !e.dataTransfer.files.length) return;
    e.preventDefault(); canvasEl.classList.remove("dropping");
    if ($("io").hidden) $("io-toggle").click();
    readFile(e.dataTransfer.files[0]);
  });

