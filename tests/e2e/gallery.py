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
        entries = await pg.evaluate("window.__gallery()")
        check(sorted(e["file"] for e in entries) == sorted(files), f"every file in gallery/ is in the page ({len(entries)} entries)")
        groups = await pg.eval_on_selector_all("#example optgroup", "e => e.map(g => g.label)")
        files_by_key = {"g_" + name[:-5].replace("-", "_"): d for name, d in files.items()}
        want = {"github": "Community: GitHub", "coding": "Community: code and data", "news": "Community: news", "money": "Community: money",
                "calendar": "Community: calendar and email", "home": "Community: home and baking", "odds": "Community: odds and ends"}
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
            await pg.click("#io-toggle")
            await paste(pg, text)
            await pg.click("#io-load-paste")
            msg = await pg.text_content("#io-import-msg")
            check(msg.startswith("Loaded") and caps[acts[0]["can"][0]][1] in msg,
                  f"a gallery file imports like any block file, saying what it can do ({msg})")
        check(not errors, "no page errors with the gallery" + (f": {errors[:2]}" if errors else ""))
        await browser.close()
