"""End-to-end tests of the page: services, capabilities, every example run on the page and exported."""
from e2e.common import *  # noqa: F401,F403
from e2e.page_features import new_feature_page_tests  # noqa: E402
from e2e.sources import rehash_export  # noqa: E402


async def page_tests():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await browser.new_page(viewport={"width": 1400, "height": 1000})
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.route("**/*", route)
        await pg.add_init_script(MOCK)
        await pg.goto("http://test/")
        await pg.wait_for_timeout(1500)

        sys.path.insert(0, str(ROOT / "tools"))
        import sync as sync_tool
        services = json.loads(sync_tool.services_json())
        groups = await pg.eval_on_selector_all("#tier optgroup", "e => e.map(g => [g.label, g.children.length])")
        check([g[0].split(" (runs in")[0] for g in groups] == [s["menu"] for s in services] and all(n >= 1 for _, n in groups)
              and await pg.input_value("#tier") == "default",
              f"the model menu has a heading for each of the {len(services)} services in SERVICES, with Claude balanced chosen")

        chk = await pg.evaluate("window.__capabilityCheck()")
        caps = json.loads(sync_tool.capabilities_json())
        registered = set(await pg.evaluate("Object.keys(Blockly.Blocks).filter(k => k.startsWith('rb_'))"))
        listed, none = set(chk["blocks"]), set(chk["none"])
        listed.add("rb_agent_builtin")  # classified by its tool kind, checked next
        check(registered == listed | none and not listed & none,
              "every block is either listed with what it lets a program do, or as doing nothing to declare"
              + ("" if registered == listed | none else f" (missing: {sorted(registered - listed - none)}; unknown: {sorted((listed | none) - registered)})"))
        check(set(chk["kinds"]) == set(chk["agentKinds"]), "every agent tool kind says what it lets a program do"
              + ("" if set(chk["kinds"]) == set(chk["agentKinds"]) else f" ({sorted(set(chk['agentKinds']) ^ set(chk['kinds']))})"))
        ids = [c[0] for c in caps]
        check(set(chk["used"]) == set(ids) and chk["ids"] == ids,
              f"each of the {len(ids)} capabilities in CAPABILITIES comes from some block or tool, and the page has the same list")

        rt = {"__name__": "rt"}
        exec(compile((ROOT / "python" / "runtime.py").read_text(encoding="utf-8"), "rt", "exec"), rt)  # noqa: S102
        notes = [{"name": n, "value": v, "updated": u} for n, v, u in [
            ("rye loaf", "78% hydration, 20% wholemeal rye, proved overnight", 3), ("starter feeding", "Feed it 1:5:5 at 8pm; peaks at 7am", 2),
            ("oven", "Dutch oven at 250 °C for 20 min", 1), ("Crème pâtissière", "Vanilla custard for the brioche", 4),
            ("shopping", "strong white flour\nrye flour\nsea salt", 5), ("Spelt", "spelt loaves prove faster than wheat", 5),
            ("Baking days", "Bake on Saturdays, feed the starter on Fridays", 6), ("ﬁnal notes", "ligatures and 2² oddities", 7),
            ("café", "Cafe\u0301 au lait with breakfast", 8), ("x", "", 0)]]
        queries = ["rye", "when does the starter peak", "hydrat", "crème", "flour salt", "bake", "proving loaves", "oven 250 °C",
                   "café", "final", "2", "the of and", "SPELT", "feeding the starter friday"]
        page_ranks = await pg.evaluate("([notes, qs]) => qs.map(q => window.__memRank(notes, q, 10).map(f => [f.name, f.score]))", [notes, queries])
        py_ranks = [[[f["name"], f["score"]] for f in rt["Runtime"].rank_notes(notes, q, 10)] for q in queries]
        differ = [q for q, a, b in zip(queries, page_ranks, py_ranks) if a != b]
        check(not differ and sum(map(len, py_ranks)) >= 14 and py_ranks[queries.index("final")][0][0] == "ﬁnal notes",
              f"the page and Python rank saved notes the same, scores and order, for {len(queries)} searches" + (f" (differ: {differ})" if differ else ""))

        lines = "- a\n* b\n\n3. c\n• d\n4) e\n(5) f\n•h\n1.Item\n10 green bottles\n2024 plan\n1.5 kg flour\n-5 °C overnight\n**Rye** loaf\n  12. twelve"
        page_list = await pg.evaluate("t => window.__list(t)", lines)
        check(page_list == rt["to_list"](lines) and "10 green bottles" in page_list and "first" not in page_list,
              f"the page and Python split a text into list items the same way, keeping numbers that aren't markers ({page_list})")

        EXAMPLES.extend(await pg.eval_on_selector_all("#example option", "e => e.map(o => o.value)"))
        print(f"Examples in the page ({len(EXAMPLES)})")
        for ex in EXAMPLES:
            await pg.select_option("#example", ex)
            await pg.click("#load")
            status = await run_program(pg)
            has_result = await pg.query_selector(".result") is not None
            check(status.startswith("done") and has_result, f"{ex}: {status}")
            if ex == "gemini":
                labelled = await pg.eval_on_selector_all(".step-name", "e => e.filter(x => x.textContent.includes('standing in for Gemini')).length")
                check(labelled > 0, f"page marks {labelled} step(s) as Claude standing in for Gemini")

        print("Home Assistant panel")
        await pg.select_option("#example", "ha_doorbell")
        await pg.click("#load")
        await pg.click("#ha-toggle")
        await pg.fill("#ha-filter", "doorbell")
        await pg.wait_for_timeout(200)
        inp = await pg.query_selector(".ha-state")
        await inp.fill("on")
        await inp.press("Enter")
        for _ in range(100):
            await pg.wait_for_timeout(150)
            if await pg.is_enabled("#run") and await pg.query_selector(".result"):
                break
        names = await pg.eval_on_selector_all(".step-name", "e => e.map(x => x.textContent)")
        check(any(n.startswith("Snapshot") for n in names) and await pg.query_selector(".result") is not None,
              "changing the doorbell in the panel runs the doorbell script")
        await pg.click("#ha-toggle")

        print("Block search")
        await pg.fill("#block-search", "record")
        await pg.wait_for_timeout(300)
        found = await pg.evaluate("Blockly.getMainWorkspace().getToolbox().getFlyout().getWorkspace().getTopBlocks(false).length")
        check(found >= 5, f"'record' finds {found} blocks")
        await pg.press("#block-search", "Escape")

        print("Backup models")
        await pg.click("#bk-toggle")
        await pg.select_option("#tier", "complex")
        await pg.select_option("#bk-1", "quick")
        await pg.evaluate("window.__failTier = 'complex'")
        await pg.select_option("#example", "review")
        await pg.click("#load")
        status = await run_program(pg)
        names = await pg.eval_on_selector_all(".step-name", "e => e.map(x => x.textContent)")
        check(status.startswith("done") and any(n.startswith("Backup") for n in names),
              f"when the primary fails, the backup answers ({status})")
        label = await pg.text_content("#bk-toggle")
        check(label == "Backups (1)", f"the Backups button shows how many are set ({label})")
        await pg.click("#io-export")
        await pg.click("#io-py-show")
        code = await pg.input_value("#io-export-text")
        check('BACKUPS = ["quick"]' in code, "exported Python lists the backup")
        await pg.click("#io-py-show")
        await pg.click("#io-export")
        await pg.click("#bk-toggle")
        await pg.select_option("#bk-1", "")
        await pg.evaluate("window.__failTier = 'complex'")
        await pg.select_option("#example", "review")
        await pg.click("#load")
        status = await run_program(pg)
        check(not status.startswith("done"), f"with no backups, a failing primary stops the run ({status})")
        await pg.evaluate("window.__failTier = null")
        await pg.select_option("#tier", "default")
        await pg.click("#bk-toggle")

        print("Python export and import")
        await pg.click("#io-export")
        codes = {}
        for ex in EXAMPLES:
            await pg.select_option("#example", ex)
            await pg.click("#load")
            n = await pg.evaluate("Blockly.getMainWorkspace().getAllBlocks(false).length")
            await pg.fill("#io-name", ex)
            await pg.click("#io-py-show")
            codes[ex] = (await pg.input_value("#io-export-text"), n)
            await pg.click("#io-py-show")
        print("Exported zip contents")
        for ex in ("review", "w_judges", "ha_doorbell", "ha_morning"):
            await pg.select_option("#example", ex)
            await pg.click("#load")
            await pg.fill("#io-name", ex)
            EXPORTS[ex] = {f["name"]: f["text"] for f in await pg.evaluate("window.__exportFiles()")}
            if ex == "ha_morning":
                import base64, io, zipfile
                zf = zipfile.ZipFile(io.BytesIO(base64.b64decode(await pg.evaluate("window.__zipBase64()"))))
                modes = {i.filename: (i.external_attr >> 16) & 0o777 for i in zf.infolist()}
                check(modes.get("run.sh") == 0o755 and modes.get("install-service.sh") == 0o755 and modes.get("second-thought.ini") == 0o644,
                      f"the zip marks the .sh scripts as runnable ({modes})")
                check(zf.read("second-thought.ini").decode() == EXPORTS[ex]["second-thought.ini"], "the zip unpacks to the same files")
        names = sorted(EXPORTS["review"])
        check(names == ["requirements.txt", "review.py", "run.bat", "run.sh", "second-thought.ini"], f"the zip holds the program, its settings, run.bat and run.sh ({', '.join(names)})")
        check(all(f in EXPORTS["ha_morning"] for f in ("run-on-schedule.bat", "run-on-schedule.sh", "install-service.sh", "install-startup.bat"))
              and "--schedule" in EXPORTS["ha_morning"]["run-on-schedule.sh"],
              "a program with timed scripts also gets run-on-schedule and install-startup / install-service scripts")
        check(all("\r" not in t for f, t in EXPORTS["ha_morning"].items() if f.endswith(".sh")), "the .sh scripts use Linux line endings")
        check(all("\r\n" in t and "\n" not in t.replace("\r\n", "") for f, t in EXPORTS["review"].items() if f.endswith((".bat", ".ini"))),
              "run.bat and second-thought.ini use Windows line endings")
        judges_ini = EXPORTS["w_judges"]["second-thought.ini"]
        check(all(k + " = " in judges_ini for k in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "DEEPSEEK_API_KEY", "XAI_API_KEY", "OPENAI_API_KEY")),
              "the ini asks for every key the program uses")
        check("LLAMA_BASE_URL" in judges_ini and "HA_TOKEN" not in judges_ini, "the ini only has the sections the program needs")
        check("HA_TOKEN = " in EXPORTS["ha_doorbell"]["second-thought.ini"], "a Home Assistant program's ini asks for HA_URL and HA_TOKEN")
        check("; approve = no" in EXPORTS["ha_doorbell"]["second-thought.ini"] and "approve" not in EXPORTS["review"]["second-thought.ini"],
              "the ini mentions approve = no only for a program that can act")
        check(not any(l.strip().startswith("export ") for l in EXPORTS["w_judges"]["w_judges.py"].splitlines()[:40]),
              "the program's instructions no longer say 'export'")
        code, n = codes["brainstorm"]
        await pg.select_option("#example", "review")
        await pg.click("#load")
        await paste(pg, code)
        await pg.click("#io-load-paste")
        await pg.wait_for_timeout(300)
        n2 = await pg.evaluate("Blockly.getMainWorkspace().getAllBlocks(false).length")
        check(n == n2, f"exported Python imports back exactly ({n} blocks)")
        await paste(pg, code.replace("R.main(START_SCRIPTS", "R.main(START_SCRIPTS  # edited\n    ", 1))
        await pg.click("#io-load-paste")
        await pg.wait_for_timeout(300)
        choices = await pg.eval_on_selector_all("#io-choice button", "e => e.map(x => x.textContent)")
        check(len(choices) == 2, "edited export is noticed and offers a choice")

        rv = re.search(r'^RUNTIME_VERSION = "([^"]+)"', code, re.M).group(1)
        check(f", with runtime {rv}." in code[:3000],
              f"the export header says which runtime it was made with ({rv})")
        hint = await pg.text_content("#io-py-version")
        check(f"runtime {rv}" in (hint or ""), f"the export panel says which runtime exports get ({hint!r})")
        for older, want in [(code.replace(f'RUNTIME_VERSION = "{rv}"', 'RUNTIME_VERSION = "0.9.0"', 1), "exported with runtime 0.9.0"),
                            (re.sub(r'^RUNTIME_VERSION = .*\n', "", code, count=1, flags=re.M), "from before versions were numbered")]:
            await paste(pg, rehash_export(older))
            await pg.click("#io-load-paste")
            await pg.wait_for_timeout(300)
            msg = await pg.text_content("#io-import-msg")
            choices = await pg.eval_on_selector_all("#io-choice button", "e => e.map(x => x.textContent)")
            check(not choices and "Loaded" in msg and want in msg and f"this page has runtime {rv}" in msg,
                  f"importing a program made with another runtime loads it and says how to upgrade ({msg[:90]!r}…)")
        await paste(pg, code)
        await pg.click("#io-load-paste")
        await pg.wait_for_timeout(300)
        msg = await pg.text_content("#io-import-msg")
        check("runtime" not in msg, "importing a program made with this page's runtime says nothing about runtimes")
        await pg.select_option("#example", "a_inbox")
        await pg.click("#load")
        inbox = await export_python(pg, "inbox")
        await pg.select_option("#example", "review")
        await pg.click("#load")
        await paste(pg, inbox)
        await pg.click("#io-load-paste")
        await pg.wait_for_timeout(300)
        msg = await pg.text_content("#io-import-msg")
        check("It can send email. It can also read your email and read your calendars." in msg and "asks you before its first run" in msg,
              f"importing a program says what it can do, what acts first ({msg[:140]!r}…)")
        head = inbox.split('"""', 2)[1]
        check("What this program can do:\n  - send email\n  - read your email\n  - read your calendars\n" in head
              and "asks you before its first run" in head and 'CAN = {"services": ["Claude"], "can": ["email_send", "email_read", "calendar"]}' in inbox
              and ", can=CAN)" in inbox,
              "the export lists what the program can do in its notes, and hands the list to the runtime")
        await pg.select_option("#example", "brainstorm")
        await pg.click("#load")
        plain = await export_python(pg, "plain")
        check("  - nothing beyond asking its models" in plain and "asks you before its first run" not in plain.split('"""', 2)[1]
              and '"can": []' in plain, "a program that only asks its models says so, and won't ask before running")

        await new_feature_page_tests(pg)

        # A blocks library that arrives different from the file the page pinned (a tampered CDN, or a proxy that
        # rewrote it): the browser refuses to run it, and the page says so rather than showing half an editor (#310).
        pg2 = await browser.new_page(viewport={"width": 1400, "height": 1000})
        await pg2.route("**/*", route)
        tampered = (VENDOR / "blockly" / "package" / "blockly.min.js").read_bytes() + b" "  # not the pinned bytes
        await pg2.route("**/blockly.min.js", lambda r: r.fulfill(body=tampered, content_type="application/javascript"))
        await pg2.add_init_script(MOCK)
        await pg2.goto("http://test/")
        await pg2.wait_for_timeout(1500)
        got = await pg2.evaluate("typeof Blockly === 'undefined' && !document.getElementById('banner').hidden\n"
                                 "  ? document.getElementById('banner').textContent : ''")
        check(got == "Second Thought couldn't load its blocks library. Check your connection and reload to try again.",
              f"a blocks library that doesn't match the page's fingerprint doesn't run, and the page says so ({got!r})")
        await pg2.close()

        # One row of controls (#444): at 1280×720 the canvas starts within 120 px of the top and Run is on the
        # first row — in the language with the longest words for these controls, and with the off-claude.ai
        # banner showing, as on GitHub Pages.
        print("One row of controls (#444)")
        langs = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "i18n").glob("*.json"))}
        row_keys = ["Program", "Data", "Settings", "New", "Import", "Export", "Share", "Theme", "System", "Light", "Dark",
                    "Run", "Stop", "Step: off", "Schedules: off", "Browse examples", "My programs", "Memory", "Home Assistant",
                    "Backups", "Model", "Currency", "Blocks", "Example", "Load", "Build it", "Change this program", "Keyboard help",
                    "Describe a program", "Second Thought"]
        longest = max(langs, key=lambda c: sum(len((langs[c].get("page") or {}).get(k, k)) for k in row_keys))
        pg3 = await browser.new_page(viewport={"width": 1280, "height": 720})
        pg3.on("pageerror", lambda e: errors.append(str(e)))
        await pg3.route("**/*", route)
        await pg3.add_init_script(MOCK + f";try{{if(!sessionStorage.getItem('lang-set')){{localStorage.setItem('second-thought-language','{longest}');"
                                        "sessionStorage.setItem('lang-set','1')}}catch(e){{}}")
        await pg3.goto("http://test/")
        await pg3.wait_for_timeout(1800)
        m = await pg3.evaluate("""() => { const r = s => document.querySelector(s).getBoundingClientRect();
          return { canvas: Math.round(r('.canvas').top), run: Math.round(r('#run').top), prog: Math.round(r('#menu-program summary').top),
                   settings: Math.round(r('#menu-settings summary').top), lang: document.documentElement.lang }; }""")
        await pg3.evaluate("document.getElementById('offsite').hidden = false")
        await pg3.wait_for_timeout(100)
        m_banner = await pg3.evaluate("() => Math.round(document.querySelector('.canvas').getBoundingClientRect().top)")
        check(m["canvas"] <= 120 and m_banner <= 120 and abs(m["run"] - m["prog"]) < 6 and abs(m["run"] - m["settings"]) < 6
              and m["lang"] == longest,
              f"in {longest} (longest words) at 1280×720 the canvas starts at {m['canvas']} px, {m_banner} px with the banner, "
              f"and Run is on the first row (run {m['run']}, menus {m['prog']}/{m['settings']})")
        await pg3.evaluate("document.getElementById('menu-settings').open = true")
        await pg3.select_option("#theme", "dark")
        await pg3.wait_for_timeout(200)
        dark = await pg3.evaluate("document.documentElement.getAttribute('data-theme')")
        await pg3.select_option("#theme", "")
        back = await pg3.evaluate("document.documentElement.getAttribute('data-theme')")
        check(dark == "dark" and back is None, "the Settings menu's theme choice applies, and System clears it")
        await pg3.close()

        # Panels are drawers over the canvas (#445): opening one never moves the page, and Esc closes it.
        print("Drawers over the canvas (#445)")
        base = await pg.evaluate("JSON.stringify(document.querySelector('.canvas').getBoundingClientRect())")
        for btn, panel in [("#ex-toggle", "#gallery"), ("#io-export", "#io"), ("#lib-toggle", "#lib"), ("#mem-toggle", "#mem"),
                           ("#ha-toggle", "#ha"), ("#bk-toggle", "#bk"), ("#keys-toggle", "#keys"), ("#conn-toggle", "#conn"), ("#share-prog", "#share")]:
            await pg.click(btn)
            await pg.wait_for_timeout(250)
            r = await pg.evaluate("""([panel, base]) => ({ same: JSON.stringify(document.querySelector('.canvas').getBoundingClientRect()) === base,
                   open: !document.querySelector(panel).hidden, fixed: getComputedStyle(document.querySelector(panel)).position,
                   focusIn: document.querySelector(panel).contains(document.activeElement) })""", [panel, base])
            check(r["same"] and r["open"] and r["fixed"] == "fixed" and r["focusIn"],
                  f"{btn} opens {panel} as a drawer over the canvas: the canvas doesn't move, focus is inside ({r})")
            await pg.keyboard.press("Escape")
            await pg.wait_for_timeout(150)
            check(await pg.evaluate("p => document.querySelector(p).hidden", panel),
                  f"Esc closes {panel} (open drawer now: {await pg.evaluate('window.__openDrawer()')})")

        # A program as a link (#436): Copy link packs the block file into #p=; opening the link in a fresh page offers
        # the program with its capabilities and loads nothing until Load; a broken or too-new link says so, loads nothing.
        print("Program links (#436)")
        await pg.select_option("#example", "a_inbox")
        await pg.click("#load")
        n_src = await pg.evaluate("Blockly.getMainWorkspace().getAllBlocks(false).length")
        src_json = await pg.evaluate("JSON.stringify(Blockly.serialization.workspaces.save(Blockly.getMainWorkspace()), (k, v) => k === 'id' ? undefined : v)")
        await pg.click("#io-export")  # opens the Import / export drawer
        await pg.wait_for_timeout(250)
        await pg.fill("#io-name", "link test")
        await pg.context.grant_permissions(["clipboard-read", "clipboard-write"], origin="http://test")
        await pg.click("#io-link")
        await pg.wait_for_timeout(300)
        link = await pg.evaluate("window.__programLink()")
        clip = await pg.evaluate("navigator.clipboard ? navigator.clipboard.readText().catch(() => '') : ''")
        msg = await pg.text_content("#io-export-msg")
        ta = await pg.input_value("#io-export-text")
        copied = clip if clip.startswith("http://test/#p=") else (ta if ta.startswith("http://test/#p=") else "")
        check(link.startswith("http://test/#p=") and len(link) > len("http://test/#p=") and copied == link,
              f"Copy link puts the #p= link on the clipboard ({len(link)} chars) — or selects it below if copying is refused ({msg!r})")
        await pg.keyboard.press("Escape")  # close the drawer

        # What a fresh page's canvas holds before any link is opened, to prove a link loads nothing by itself.
        pgRef = await browser.new_page(viewport={"width": 1400, "height": 1000})
        await pgRef.route("**/*", route)
        await pgRef.add_init_script(MOCK)
        await pgRef.goto("http://test/")
        await pgRef.wait_for_timeout(1500)
        ref = await pgRef.evaluate("""() => ({ blocks: Blockly.getMainWorkspace().getAllBlocks(false).length,
            json: JSON.stringify(Blockly.serialization.workspaces.save(Blockly.getMainWorkspace()), (k, v) => k === 'id' ? undefined : v) })""")
        await pgRef.close()

        pg4 = await browser.new_page(viewport={"width": 1400, "height": 1000})
        pg4.on("pageerror", lambda e: errors.append(str(e)))
        await pg4.route("**/*", route)
        await pg4.add_init_script(MOCK)
        await pg4.goto(link)
        await pg4.wait_for_timeout(1800)
        offer = await pg4.evaluate("""() => ({ ioOpen: !document.getElementById('io').hidden,
            msg: document.getElementById('io-import-msg').textContent,
            choices: [...document.querySelectorAll('#io-choice button')].map(b => b.textContent),
            blocks: Blockly.getMainWorkspace().getAllBlocks(false).length,
            json: JSON.stringify(Blockly.serialization.workspaces.save(Blockly.getMainWorkspace()), (k, v) => k === 'id' ? undefined : v), hash: location.hash })""")
        check(offer["ioOpen"] and "link test" in offer["msg"] and "blocks" in offer["msg"]
              and "It can send email" in offer["msg"] and "loads only if you choose Load" in offer["msg"]
              and offer["choices"] == ["Load this program"] and offer["blocks"] == ref["blocks"] and offer["json"] == ref["json"]
              and offer["hash"].startswith("#p="),
              f"opening the link offers the program with its capabilities and loads nothing yet "
              f"(msg {offer['msg'][:110]!r}…, choices {offer['choices']}, canvas still the fresh page's {offer['blocks']} blocks)")
        await pg4.click("#io-choice button")
        await pg4.wait_for_timeout(400)
        loaded = await pg4.evaluate("""() => ({ blocks: Blockly.getMainWorkspace().getAllBlocks(false).length,
            name: document.getElementById('io-name').value, hash: location.hash,
            json: JSON.stringify(Blockly.serialization.workspaces.save(Blockly.getMainWorkspace()), (k, v) => k === 'id' ? undefined : v) })""")
        check(loaded["blocks"] == n_src and loaded["name"] == "link-test" and loaded["hash"] == "" and loaded["json"] == src_json,
              f"Load loads the same program ({loaded['blocks']} blocks), sets the file name, and clears the hash")
        await pg4.close()

        import base64 as _b64, zlib as _zlib
        pg5 = await browser.new_page(viewport={"width": 1400, "height": 1000})
        pg5.on("pageerror", lambda e: errors.append(str(e)))
        await pg5.route("**/*", route)
        await pg5.add_init_script(MOCK)
        await pg5.goto("http://test/#p=abc")  # well-formed characters, not a deflated program
        await pg5.wait_for_timeout(1800)
        broken = await pg5.evaluate("""() => ({ msg: document.getElementById('io-import-msg').textContent,
            choices: document.querySelectorAll('#io-choice button').length,
            blocks: Blockly.getMainWorkspace().getAllBlocks(false).length, hash: location.hash })""")
        check("broken" in broken["msg"] and broken["choices"] == 0 and broken["blocks"] == ref["blocks"] and broken["hash"] == "",
              f"a broken link says so and loads nothing ({broken['msg'][:100]!r})")
        future = _b64.urlsafe_b64encode(_zlib.compress(json.dumps({"format": "reflection-blocks", "version": 999, "name": "future",
              "program": {"blocks": {"languageVersion": 0, "blocks": []}}}, separators=(",", ":")).encode(), 9, -15)).decode().rstrip("=")
        await pg5.goto(f"http://test/#p={future}")  # same page, new hash: the hashchange handler offers it too
        await pg5.wait_for_timeout(1800)
        newer = await pg5.evaluate("""() => ({ msg: document.getElementById('io-import-msg').textContent,
            choices: document.querySelectorAll('#io-choice button').length,
            blocks: Blockly.getMainWorkspace().getAllBlocks(false).length, hash: location.hash })""")
        check("newer Second Thought" in newer["msg"] and newer["choices"] == 0 and newer["blocks"] == ref["blocks"] and newer["hash"] == "",
              f"a too-new link says so and loads nothing ({newer['msg'][:100]!r})")
        await pg5.close()

        # Offering a program to the gallery (#437): Share… opens a form that shows the card as it will look and
        # builds a prefilled "Share a program" issue form's address with the #p= link (#436) in it.
        print("Share to the gallery (#437)")
        await pg.select_option("#example", "a_inbox")
        await pg.click("#load")
        await pg.evaluate("document.getElementById('io-name').value = 'link test'")
        await pg.evaluate("window.__opened = []; window.open = u => { if (typeof u === 'string') window.__opened.push(u); return null; }")
        await pg.click("#share-prog")
        await pg.wait_for_timeout(300)
        share_open = await pg.evaluate("() => ({ open: !document.getElementById('share').hidden, focusIn: document.getElementById('share').contains(document.activeElement) })")
        check(share_open["open"] and share_open["focusIn"], f"Share… opens the share drawer, focus inside ({share_open})")
        await pg.click("#sh-open")
        await pg.wait_for_timeout(300)
        msg = await pg.text_content("#sh-msg")
        opened = await pg.evaluate("window.__opened")
        check("Fill in" in (msg or "") and opened == [], f"an empty form refuses to open and says why ({msg!r}, opened {opened})")
        await pg.fill("#sh-title", "Inbox triage")
        await pg.select_option("#sh-category", "calendar")
        await pg.fill("#sh-desc", "Sorts my inbox and drafts replies.")
        await pg.fill("#sh-tip", "Try it on this week's mail.")
        await pg.fill("#sh-author", "Francis")
        await pg.wait_for_timeout(200)
        card = await pg.evaluate("document.getElementById('sh-card').innerText")
        check("Inbox triage" in card and "Shared by Francis" in card and "It can send email" in card
              and "Try: Try it on this week's mail." in card,
              f"the card preview shows the title, author, capabilities and tip as the gallery card will look ({card[:90]!r}…)")
        url = await pg.evaluate("window.__shareUrl()")
        check(url.startswith("https://github.com/itsfja/second-thought/issues/new?") and "template=share-a-program.yml" in url,
              f"the share address is the issue form with its template ({url[:80]}…)")
        from urllib.parse import urlparse, parse_qs
        q = parse_qs(urlparse(url).query)
        check(q.get("title") == ["Share a program: Inbox triage"] and q.get("category") == ["Community: calendar and email"]
              and q.get("author") == ["Francis"] and q.get("name") == ["link-test"] and q.get("runtime")
              and q.get("link", [""])[0].startswith("http://test/#p="),
              f"the fields are prefilled (title {q.get('title')}, category {q.get('category')}, name {q.get('name')}, runtime {q.get('runtime')})")
        import base64 as _b64, zlib as _zlib
        packed = q["link"][0].split("#p=")[1]
        payload = json.loads(_zlib.decompress(_b64.urlsafe_b64decode(packed + "=" * (-len(packed) % 4)), -15).decode())
        ws = json.loads(await pg.evaluate("JSON.stringify(Blockly.serialization.workspaces.save(Blockly.getMainWorkspace()))"))
        check(payload.get("program") == ws and payload.get("name") == "link test" and isinstance(payload.get("version"), int),
              f"the prefilled link unpacks to the canvas's program ({len(packed)} chars packed, name {payload.get('name')!r})")
        await pg.click("#sh-open")
        await pg.wait_for_timeout(600)
        opened = await pg.evaluate("window.__opened")
        check(opened == [url], f"Open opens exactly that address in a new tab ({[str(u)[:60] for u in opened]})")
        await pg.keyboard.press("Escape")  # close the drawer

        # The first screen (#443): a fresh browser gets three ways in; each path lands in the editor with a program.
        print("First screen (#443)")
        pgF = await browser.new_page(viewport={"width": 1400, "height": 1000})
        pgF.on("pageerror", lambda e: errors.append(str(e)))
        await pgF.route("**/*", route)
        await pgF.add_init_script(MOCK)
        await pgF.goto("http://test/")
        await pgF.wait_for_timeout(1500)
        first = await pgF.evaluate("""() => ({ visible: !document.getElementById('first').hidden,
            focusIn: document.getElementById('first').contains(document.activeElement),
            starters: document.querySelectorAll('#first-starters button').length,
            examples: [...document.querySelectorAll('#first-examples button')].map(b => b.textContent) })""")
        check(first["visible"] and first["focusIn"] and first["starters"] == 3 and len(first["examples"]) == 6,
              f"a fresh browser sees the first screen with three sentences and six examples, focus inside ({first['examples']})")
        await pgF.click("#first-starters button")
        txt = await pgF.input_value("#first-text")
        check("Telegram" in txt, f"clicking a sentence fills the describe box ({txt[:50]!r}…)")
        await pgF.evaluate("r => { window.__jsonScript = r; window.__jsonPrompts = []; }",
                           [{"program": script(add(tx("hello from the first screen"))), "summary": "Says hello.", "unmapped": []}])
        await pgF.click("#first-build")
        await pgF.wait_for_function("!document.getElementById('describe-load').hidden || document.getElementById('describe-msg').className.includes('bad')", timeout=20000)
        built = await pgF.evaluate("""() => ({ firstHidden: document.getElementById('first').hidden,
            loadVisible: !document.getElementById('describe-load').hidden,
            blocks: Blockly.getMainWorkspace().getAllBlocks(false).length })""")
        check(built["firstHidden"] and built["loadVisible"] and built["blocks"] > 0,
              f"Build it leaves the first screen and offers the built program before loading anything ({built})")
        await pgF.click("#describe-load")
        await pgF.wait_for_timeout(400)
        nF = await pgF.evaluate("Blockly.getMainWorkspace().getAllBlocks(false).length")
        check(nF >= 2 and await pgF.evaluate("document.getElementById('first').hidden"),
              f"Load it lands in the editor with the built program ({nF} blocks)")
        await pgF.close()

        pgF2 = await browser.new_page(viewport={"width": 1400, "height": 1000})
        pgF2.on("pageerror", lambda e: errors.append(str(e)))
        await pgF2.route("**/*", route)
        await pgF2.add_init_script(MOCK)
        await pgF2.goto("http://test/")
        await pgF2.wait_for_timeout(1500)
        await pgF2.click("#first-examples button:nth-child(2)")
        await pgF2.wait_for_timeout(400)
        n2 = await pgF2.evaluate("Blockly.getMainWorkspace().getAllBlocks(false).length")
        check(await pgF2.evaluate("document.getElementById('first').hidden") and n2 > 0,
              f"starting from an example hides the first screen and loads the program ({n2} blocks)")
        await pgF2.close()

        import tempfile
        prog = {"format": "reflection-blocks", "version": 1, "name": "from-a-file", "program": script(add(tx("loaded from a file")))}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(prog, fh)
            fpath = fh.name
        pgF3 = await browser.new_page(viewport={"width": 1400, "height": 1000})
        pgF3.on("pageerror", lambda e: errors.append(str(e)))
        await pgF3.route("**/*", route)
        await pgF3.add_init_script(MOCK)
        await pgF3.goto("http://test/")
        await pgF3.wait_for_timeout(1500)
        await pgF3.set_input_files("#io-file", fpath)
        await pgF3.wait_for_timeout(800)
        n3 = await pgF3.evaluate("Blockly.getMainWorkspace().getAllBlocks(false).length")
        check(await pgF3.evaluate("document.getElementById('first').hidden") and n3 >= 2,
              f"opening a file lands in the editor with the program ({n3} blocks)")
        await pgF3.close()

        pgR = await browser.new_page(viewport={"width": 1400, "height": 1000})
        await pgR.route("**/*", route)
        await pgR.add_init_script(MOCK + ";try{localStorage.setItem('reflection-blocks-program-v3','{}')}catch(e){}")
        await pgR.goto("http://test/")
        await pgR.wait_for_timeout(1500)
        check(await pgR.evaluate("document.getElementById('first').hidden"),
              "a browser with a program kept lands in the editor, with no first screen")
        await pgR.close()

        # The acting-capabilities line and the block marks (#448): the line under the controls says what the program
        # can do, updates as blocks come and go, is a role=status for screen readers, and every acting block carries a
        # shape mark (triangle = asks first, diamond = no asking).
        print("Acting capabilities line (#448)")
        MARKS_JS = """() => Blockly.getMainWorkspace().getAllBlocks(false).map(b => {
            const want = window.__actsMark(b);
            const root = b.getSvgRoot && b.getSvgRoot();
            const got = root && root.querySelector(':scope > .acts-mark') ? root.querySelector(':scope > .acts-mark').dataset.shape : null;
            return { type:b.type, kind:b.type === 'rb_agent_builtin' ? String(b.getFieldValue('KIND') || '') : '', want, got }; })"""
        await pg.select_option("#example", "a_inbox")
        await pg.click("#load")
        await pg.wait_for_timeout(400)
        role = await pg.get_attribute("#caps-line", "role")
        line1 = await pg.text_content("#caps-line")
        check(role == "status", f"the capabilities line is a live region for screen readers (role={role!r})")
        check("This program can:" in line1 and "send email (asks first)" in line1 and "read your email" in line1,
              f"the line says what the program can send and read ({line1!r})")
        marks = await pg.evaluate(MARKS_JS)
        acting = [m for m in marks if m["want"]]
        check(all(m["want"] == m["got"] for m in marks) and len(acting) == 1
              and acting[0]["kind"] == "email_send" and acting[0]["want"] == "triangle",
              f"the acting block carries a triangle mark and nothing else is marked ({[(m['type'], m['kind'], m['want'], m['got']) for m in marks if m['want'] or m['got']]})")
        await pg.select_option("#example", "a_prreview")
        await pg.click("#load")
        await pg.wait_for_timeout(400)
        line2 = await pg.text_content("#caps-line")
        marks2 = await pg.evaluate(MARKS_JS)
        acting2 = [m for m in marks2 if m["want"]]
        check(line2 != line1 and "comment on GitHub" in line2 and "(asks first)" in line2,
              f"the line updates when the program changes ({line2!r})")
        check(all(m["want"] == m["got"] for m in marks2) and any(m["kind"] == "github_act" and m["want"] == "triangle" for m in acting2),
              f"the new program's acting tool is marked ({[(m['type'], m['kind'], m['want'], m['got']) for m in marks2 if m['want'] or m['got']]})")
        await pg.select_option("#example", "review")
        await pg.click("#load")
        await pg.wait_for_timeout(400)
        line3 = await pg.text_content("#caps-line")
        marks3 = await pg.evaluate(MARKS_JS)
        check("only uses your models" in line3 and not any(m["want"] or m["got"] for m in marks3) and len(marks3) > 0,
              f"a model-only program says so and carries no marks ({line3!r}, {len(marks3)} blocks)")

        # The Connections list in Settings (#446): a fresh page shows the core categories plus Connections, the
        # one-service categories nest inside Connections only when turned on, loading a program that uses a service
        # turns it on, and Find a block still reaches every block. On a fresh browser, so earlier example loads in
        # this test don't turn services on already.
        print("Connections in Settings (#446)")
        pgF = await browser.new_page(viewport={"width": 1400, "height": 1000})
        pgF.on("pageerror", lambda e: errors.append(str(e)))
        await pgF.route("**/*", route)
        await pgF.add_init_script(MOCK)
        await pgF.goto("http://test/")
        await pgF.wait_for_timeout(1500)
        VIS = """() => { const tb = window.__visibleToolbox(); const conn = tb.contents.find(c => c.name === "Connections");
            return { top: tb.contents.filter(c => c.kind === "category").map(c => c.name),
                     conn: (conn.contents || []).filter(c => c.kind === "category").map(c => c.name),
                     enabled: window.__services().enabled }; }"""
        vis = await pgF.evaluate(VIS)
        check(len(vis["top"]) == 22 and "Connections" in vis["top"] and "Home Assistant" not in vis["top"]
              and vis["conn"] == [] and vis["enabled"] == [],
              f"a fresh page shows the {len(vis['top'])} core categories plus Connections, no service nested ({vis['top'][:4]}…)")
        await pgF.click("#conn-toggle")
        await pgF.wait_for_timeout(250)
        items = await pgF.eval_on_selector_all("#conn-list .conn-item", "els => els.map(e => [e.querySelector('input').dataset.service, e.querySelector('span').textContent])")
        check(len(items) == 18 and any(i[0] == "ha" and i[1] == "Home Assistant" for i in items),
              f"the Connections drawer lists all 18 services by their category names ({len(items)}: {items[:3]}…)")
        await pgF.check("#conn-list input[data-service=ha]")
        await pgF.wait_for_timeout(300)
        vis = await pgF.evaluate(VIS)
        live = await pgF.evaluate("""() => { const items = Blockly.getMainWorkspace().getToolbox().getToolboxItems();
            const name = i => i.getName ? i.getName() : null;
            const top = items.filter(i => { const p = i.getParent && i.getParent(); return !p || !name(p); }).map(name).filter(Boolean);
            const ha = items.find(i => name(i) === "Home Assistant");
            return { top, haParent: ha && ha.getParent() ? name(ha.getParent()) : null }; }""")
        check(vis["conn"] == ["Home Assistant"] and vis["enabled"] == ["ha"] and len(vis["top"]) == 22
              and len(live["top"]) == 22 and "Home Assistant" not in live["top"] and live["haParent"] == "Connections",
              f"turning Home Assistant on nests it inside Connections in the live toolbox too ({vis['conn']}; live top-level: {len(live['top'])}, HA's parent: {live['haParent']})")
        await pgF.keyboard.press("Escape")
        await pgF.reload()
        await pgF.wait_for_timeout(1500)
        vis = await pgF.evaluate(VIS)
        check(vis["enabled"] == ["ha"] and vis["conn"] == ["Home Assistant"],
              f"the turned-on service is kept across a reload ({vis['enabled']})")
        # loading a program that uses a service turns it on: the gallery's dns-check uses Pi-hole
        await pgF.click("#ex-toggle")
        await pgF.wait_for_timeout(300)
        await pgF.fill("#gal-search", "dns")
        await pgF.wait_for_timeout(300)
        card = await pgF.query_selector(".gal-card[data-key='g_dns_check'] button")
        check(card is not None, "the gallery search finds the dns-check program")
        await card.click()
        await pgF.wait_for_timeout(500)
        vis = await pgF.evaluate(VIS)
        check("pihole" in vis["enabled"] and "Pi-hole" in vis["conn"] and vis["enabled"] == ["ha", "pihole", "telegram"],
              f"loading a program that uses Pi-hole turns it on ({vis['enabled']}; nested: {vis['conn']})")
        # Find a block still reaches a service that is off (Proxmox)
        await pgF.fill("#block-search", "proxmox")
        await pgF.wait_for_timeout(300)
        found = await pgF.evaluate("Blockly.getMainWorkspace().getToolbox().getFlyout().getWorkspace().getTopBlocks(false).length")
        check(found >= 1 and "proxmox" not in vis["enabled"],
              f"'proxmox' still finds {found} blocks although Proxmox is off")
        await pgF.press("#block-search", "Escape")
        await pgF.close()

        check(not errors, "no page errors" + ("" if not errors else ": " + "; ".join(errors[:3])))
        await browser.close()
        return codes
