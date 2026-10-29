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
        await pg.click("#io-toggle")
        await pg.click("#io-py-show")
        code = await pg.input_value("#io-export-text")
        check('BACKUPS = ["quick"]' in code, "exported Python lists the backup")
        await pg.click("#io-py-show")
        await pg.click("#io-toggle")
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
        await pg.click("#io-toggle")
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

        check(not errors, "no page errors" + ("" if not errors else ": " + "; ".join(errors[:3])))
        await browser.close()
        return codes
