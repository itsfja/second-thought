"""End-to-end tests of the community gallery."""
from e2e.common import *  # noqa: F401,F403


async def gallery_tests():
    """The community gallery: every entry is on the page, loads with no unknown blocks, and shows what it can do as the page
    works it out. (Each one is also run, exported and run as Python with the other examples.)"""
    print("Community gallery")
    files = {path.name: json.loads(path.read_text(encoding="utf-8")) for path in sorted((ROOT / "gallery").glob("*.json"))}
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await browser.new_page(viewport={"width": 1400, "height": 1000})
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.route("**/*", route)
        await pg.add_init_script(MOCK)
        await pg.goto("http://test/")
        await pg.wait_for_timeout(1500)
        check(await pg.eval_on_selector_all("#gal-body .gal-card", "e => e.length") == 0,
              "no example card is built until Browse examples is opened (#417)")
        await pg.click("#ex-toggle")
        await pg.wait_for_timeout(400)
        n_cards = await pg.eval_on_selector_all("#gal-body .gal-card", "e => e.length")
        check(n_cards > 100, f"opening Browse examples builds its {n_cards} cards on first open")

        # Search and filters (#445): by words, and by what the page works out each program can do.
        vis_keys = "[...document.querySelectorAll('#gal-body .gal-card')].filter(c => c.style.display !== 'none').map(c => c.dataset.key)"
        count = await pg.text_content("#gal-count")
        check(re.fullmatch(rf"{n_cards} of {n_cards} examples", count.strip()) is not None, f"the count line says how many show ({count!r})")
        await pg.fill("#gal-search", "doorbell")
        await pg.wait_for_timeout(150)
        got = await pg.evaluate(vis_keys)
        check(got == ["ha_doorbell"], f"the search box finds examples by their words ({got})")
        await pg.fill("#gal-search", "")
        await pg.click("#gf-models")
        await pg.wait_for_timeout(150)
        got = await pg.evaluate(vis_keys)
        check("review" in got and "ha_doorbell" not in got, f"the 'Only uses models' filter keeps model-only examples ({len(got)} shown)")
        await pg.click("#gf-models")
        await pg.select_option("#gf-service", "ha_act")
        await pg.wait_for_timeout(150)
        got = await pg.evaluate(vis_keys)
        check("ha_doorbell" in got and "review" not in got, f"the service filter keeps what needs that service ({len(got)} shown)")
        await pg.select_option("#gf-service", "")
        await pg.select_option("#gf-which", "shared")
        await pg.wait_for_timeout(150)
        got = await pg.evaluate(vis_keys)
        n_shared = len(await pg.evaluate("window.__gallery()"))
        check(0 < len(got) == n_shared and all(k.startswith("g_") for k in got),
              f"the 'Shared' filter keeps only community programs ({len(got)} of {n_shared})")
        await pg.select_option("#gf-which", "")
        await pg.wait_for_timeout(150)
        got = await pg.evaluate(vis_keys)
        check(len(got) == n_cards, f"clearing the filters shows all {n_cards} again ({len(got)})")
        entries = await pg.evaluate("window.__gallery()")
        check(sorted(e["file"] for e in entries) == sorted(files), f"every file in gallery/ is in the page ({len(entries)} entries)")
        groups = await pg.eval_on_selector_all("#example optgroup", "e => e.map(g => g.label)")
        files_by_key = {"g_" + name[:-5].replace("-", "_"): d for name, d in files.items()}
        want = {"github": "Community: GitHub", "coding": "Community: code and data", "news": "Community: news", "money": "Community: money",
                "calendar": "Community: calendar and email", "home": "Community: home and baking", "learning": "Community: teaching",
                "odds": "Community: odds and ends"}
        used = [g for k, g in want.items() if any(d["gallery"].get("category", "odds") == k for d in files.values())]
        community = [g for g in groups if g.startswith("Community: ")]
        check(community == used and groups.index(community[0]) == groups.index("Research") + 1,
              f"the Example menu has a Community group for each category in use, in order, straight after Research ({community})")
        placed = await pg.evaluate("[...document.querySelectorAll('#example optgroup')].flatMap(g => [...g.children].map(o => [o.value, g.label]))")
        wrong = [k for k, g in placed if k in files_by_key and g != want[files_by_key[k]["gallery"].get("category", "odds")]]
        check(not wrong, "each gallery program is in its category's group" + (f" (not {wrong})" if wrong else ""))
        heads = await pg.eval_on_selector_all("#gal-body .gal-cat", "e => e.map(s => [s.querySelector('h3').textContent, !!s.querySelector('.hint')])")
        check(heads[2] == [used[0], True] and not any(h for t, h in heads if t != used[0]),
              f"in Browse examples, the community groups come third, and the first explains shared programs ({heads[:4]})")
        caps = await pg.evaluate("Object.fromEntries(JSON.parse(document.getElementById('capabilities').textContent).map(c => [c[0], c]))")
        for e in entries:
            check(not e["unknown"], f"{e['file']} uses only blocks the page has" + (f" (not {e['unknown']})" if e["unknown"] else ""))
            await pg.select_option("#example", e["key"])
            await pg.click("#load")
            loaded = (await pg.evaluate("window.__capabilityCheck()"))["program"]
            check(sorted(loaded) == sorted(e["can"]), f"{e['file']}: its card says what it can do, as loading it shows ({e['can']})")
            wording = [caps[c][1] for c in e["can"]]
            check("Shared by " in e["card"] and all(w in e["card"] for w in wording)
                  and (bool(wording) or "only uses your models" in e["card"]),
                  f"{e['file']}: the card names who shared it and everything it can do")
            if any(caps[c][2] for c in e["can"]):
                check("asks you before its first run" in e["card"], f"{e['file']} can act, and its card says Python asks first")
        acts = [e for e in entries if any(caps[c][2] for c in e["can"])]
        check(bool(acts), "at least one gallery entry acts, so the trust wording is tested")
        if acts:
            text = json.dumps(files[acts[0]["file"]])
            await pg.click("#io-export")
            await paste(pg, text)
            await pg.click("#io-load-paste")
            msg = await pg.text_content("#io-import-msg")
            check(msg.startswith("Loaded") and caps[acts[0]["can"][0]][1] in msg,
                  f"a gallery file imports like any block file, saying what it can do ({msg})")
        check(not errors, "no page errors with the gallery" + (f": {errors[:2]}" if errors else ""))
        await browser.close()


async def broken_gallery_tests():
    """A gallery file with a block the page doesn't have (#417): the page still starts, Run runs, the panels open, no
    card is built until Browse examples is opened, and the broken program's card says it can't be loaded and why."""
    print("A gallery program that won't load")
    broken = {"key": "g_broken_test", "file": "broken-test.json", "category": "odds", "title": "Broken test",
              "description": "A test program with a block this page doesn't have.", "tip": "Nothing to try.",
              "author": "test", "runtime": "3.0.0", "version": 1,
              "program": {"blocks": {"languageVersion": 0, "blocks": [
                  {"type": "rb_start", "x": 30, "y": 30, "next": {"block": {"type": "rb_no_such_block", "x": 30, "y": 140}}}]}}}
    m = re.search(r'(<script type="application/json" id="community-gallery">\n)([\s\S]*?)(\n</script>)', PAGE)
    gallery = json.loads(m.group(2)) + [broken]
    doc = ('<!doctype html><html><head><meta charset=utf8><style>[hidden]{display:none!important}</style></head><body>'
           + PAGE[:m.start(2)] + json.dumps(gallery) + PAGE[m.end(2):] + "</body></html>")

    async def broken_route(r):
        if r.request.url == "http://test/":
            return await r.fulfill(body=doc, content_type="text/html")
        await route(r)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await browser.new_page(viewport={"width": 1400, "height": 1000})
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.route("**/*", broken_route)
        await pg.add_init_script(MOCK)
        await pg.goto("http://test/")
        await pg.wait_for_timeout(1500)
        check(not errors, "the page starts with no page errors" + (f": {errors[:2]}" if errors else ""))
        check(await pg.eval_on_selector_all("#gal-body .gal-card", "e => e.length") == 0,
              "no example card is built until Browse examples is opened")
        await pg.click("#ex-toggle")
        await pg.wait_for_timeout(400)
        cards = await pg.eval_on_selector_all("#gal-body .gal-card", "e => e.length")
        check(cards > 100, f"opening Browse examples builds every card, the broken one included ({cards})")
        card = await pg.evaluate("() => (document.querySelector('.gal-card[data-key=\"g_broken_test\"]') || {}).innerText || ''")
        check("couldn't be loaded" in card and "rb_no_such_block" in card,
              f"the broken program's card says it can't be loaded, and why ({card[:110]!r})")
        check(not errors, "building the cards left no page errors" + (f": {errors[:2]}" if errors else ""))
        # The page works with the broken entry there: Run runs, and every panel opens.
        await pg.select_option("#example", "review")
        await pg.click("#load")
        status = await run_program(pg)
        check(status.startswith("done"), f"Run runs with the broken gallery entry there ({status})")
        for toggle, pid in (("io-export", "io"), ("lib-toggle", "lib"), ("mem-toggle", "mem"), ("ha-toggle", "ha"), ("bk-toggle", "bk"), ("keys-toggle", "keys")):
            await pg.click("#" + toggle)
            await pg.wait_for_timeout(100)
            opened = await pg.evaluate("id => !document.getElementById(id).hidden", pid)
            check(opened, f"the {pid} panel opens as a drawer")
            await pg.keyboard.press("Escape")
            await pg.wait_for_timeout(50)
        # Loading the broken program itself says why, and leaves the canvas as it was.
        blocks_before = await pg.evaluate("Blockly.getMainWorkspace().getAllBlocks(false).length")
        await pg.select_option("#example", "g_broken_test")
        await pg.click("#load")
        await pg.wait_for_timeout(200)
        msg = await pg.inner_text("#status")
        check("couldn't be loaded" in msg and "rb_no_such_block" in msg,
              f"loading it says it couldn't be loaded, and why ({msg[:110]!r})")
        blocks_after = await pg.evaluate("Blockly.getMainWorkspace().getAllBlocks(false).length")
        check(blocks_after == blocks_before and blocks_after > 0,
              f"the canvas is left as it was ({blocks_before} blocks, then {blocks_after})")
        check(not errors, "no page errors at the end" + (f": {errors[:2]}" if errors else ""))
        await browser.close()


def gallery_smoke_tests():
    """tools/smoke_test.py gallery, the real-model run of the gallery, checked here with the stand-in models: it finishes
    programs, stops one at its budget, and skips one with no key."""
    print("Gallery against the models (tools/smoke_test.py gallery)")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        (tmp / "empty.ini").write_text("", encoding="utf-8")
        report = tmp / "report.md"
        base = {k: v for k, v in os.environ.items() if not k.endswith(("_API_KEY", "_TOKEN"))}
        base.update(SECOND_THOUGHT_INI=str(tmp / "empty.ini"), PYTHONIOENCODING="utf-8")

        def run(*args, **env):
            return subprocess.run([sys.executable, str(ROOT / "tools" / "smoke_test.py"), "gallery", *args, "--report", str(report)],
                                  env=dict(base, **env), capture_output=True, text=True, timeout=600)
        r = run("rain", "doctor", "release-notes", "--stand-ins", "--budget", "300")
        text = report.read_text(encoding="utf-8") if report.exists() else ""
        check(r.returncode == 0 and "| rain-window | finished |" in text and "| second-thought-doctor | finished |" in text,
              "it runs gallery programs to the end and writes the report" + ("" if r.returncode == 0 else f": {(r.stderr or r.stdout)[-300:]}"))
        check("| release-notes-writer | stopped by the budget |" in text and "reaches its budget of 300" in text,
              "a program that goes over --budget is stopped, and the report says so")
        check("What the stand-in services were sent: gh" in text, "the programs' connections went to the stand-in services")
        r = run("rain")
        text = report.read_text(encoding="utf-8")
        check(r.returncode == 0 and "| rain-window | skipped |" in text and "needs Claude (ANTHROPIC_API_KEY)" in text,
              "a program for a service with no key is skipped, naming the key it needs")


async def changed_gallery_tests(names):
    """For a pull request that changes only gallery programs (#457): each one it changes is loaded and run on the page,
    exported with tools/export.cjs, and its Python checked with --doctor, without the full page run. CI names the files
    in RB_GALLERY_FILES; the full suite, on main and each night, runs and exports every program as before."""
    import shutil
    import tempfile
    files = [ROOT / "gallery" / n for n in names if (ROOT / "gallery" / n).is_file()]
    print(f"The gallery programs this change touches ({len(files)})")
    if not files:
        return
    node = shutil.which("node")
    check(bool(node), "tools/export.cjs needs Node on the PATH")
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await browser.new_page(viewport={"width": 1400, "height": 1000})
        await pg.route("**/*", route)
        await pg.add_init_script(MOCK)
        await pg.goto("http://test/")
        await pg.wait_for_timeout(1500)
        for f in files:
            key = "g_" + f.stem.replace("-", "_")
            await pg.select_option("#example", key)
            await pg.click("#load")
            status = await run_program(pg)
            check(status.startswith("done"), f"{f.name}: runs on the page ({status})")
        await browser.close()
    if not node:
        return
    with tempfile.TemporaryDirectory() as tmp:
        run = subprocess.run([node, str(ROOT / "tools" / "export.cjs"), *map(str, files), "--out-dir", tmp],
                             capture_output=True, text=True, timeout=300)
        check(run.returncode == 0, "tools/export.cjs exports them" + ("" if run.returncode == 0 else f": {run.stderr.strip()[-300:]}"))
        env = {k: v for k, v in os.environ.items() if not (k.endswith(("_API_KEY", "_TOKEN", "_SECRET", "_PASSWORD")) or k == "HF_TOKEN")}
        env.pop("GITHUB_ACTIONS", None)
        for f in files:
            name = json.loads(f.read_text(encoding="utf-8")).get("name") or f.stem
            prog = pathlib.Path(tmp) / (re.sub(r"\s+", "-", re.sub(r"[^\w\- ]+", "", name.strip())) + ".py")
            if not prog.exists():
                check(False, f"{f.name}: exported as {prog.name}")
                continue
            r = subprocess.run([sys.executable, "-u", str(prog), "--doctor"], env=env, cwd=tmp, capture_output=True,
                               encoding="utf-8", errors="replace", timeout=120)
            check(r.returncode == 1 and "  FAIL  Claude: no key." in r.stdout and "Traceback" not in r.stderr,
                  f"{f.name}: its exported Python's --doctor runs to the end, and with no keys says so (exit {r.returncode}): {(r.stderr or r.stdout)[-300:]!r}")
