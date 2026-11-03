"""Using the page with the keyboard alone, and a screen reader: a run answered from the keyboard, building a program
with Blockly 13's own keyboard navigation, and axe-core finding no serious problems."""
from e2e.common import *  # noqa: F401,F403

AXE = VENDOR / "axe-core/package/axe.min.js"


async def axe_problems(pg):
    """axe-core's serious and critical findings for the page as it is now, as 'rule: element' lines."""
    if not await pg.evaluate("typeof axe !== 'undefined'"):
        await pg.add_script_tag(path=str(AXE))
    found = await pg.evaluate("""axe.run(document, { resultTypes:['violations'] }).then(r => r.violations
        .filter(v => v.impact === 'serious' || v.impact === 'critical')
        .flatMap(v => v.nodes.slice(0, 3).map(n => v.id + ': ' + n.target.join(' '))))""")
    return found


async def tab_to(pg, selector, limit=80):
    """Press Tab until the element is focused, as someone with only a keyboard would."""
    for _ in range(limit):
        if await pg.evaluate("s => document.activeElement && document.activeElement.matches(s)", selector):
            return True
        await pg.keyboard.press("Tab")
    return False


async def access_tests():
    print("Keyboard and screen readers")
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await browser.new_page(viewport={"width": 1400, "height": 1000})
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.route("**/*", route)
        await pg.add_init_script(MOCK)
        await pg.goto("http://test/")
        await pg.wait_for_timeout(1500)

        problems = await axe_problems(pg)
        check(not problems, f"axe-core finds no serious problems on the page as it opens {problems or ''}")
        lang = await pg.evaluate("document.documentElement.lang")
        check(lang.split("-")[0] == "en", f"the page says what language it's in ({lang})")
        for toggle in ("ex-toggle", "io-toggle", "lib-toggle", "mem-toggle", "ha-toggle", "bk-toggle", "keys-toggle"):
            await pg.click("#" + toggle)
        await pg.wait_for_timeout(300)
        problems = await axe_problems(pg)
        check(not problems, f"or with every panel open {problems or ''}")
        for toggle in ("ex-toggle", "io-toggle", "lib-toggle", "mem-toggle", "ha-toggle", "bk-toggle", "keys-toggle"):
            await pg.click("#" + toggle)

        # A run, from the keyboard alone: Tab to Run, Enter, and the question takes the focus.
        await load_state(pg, script(blk("rb_ask_me", inputs={"TEXT": tx("Which bread should I bake?")}),
                                    add(join(tx("Baking: "), val(blk("rb_answer"))))))
        await pg.evaluate("document.activeElement && document.activeElement.blur()")
        check(await tab_to(pg, "#run"), "Tab reaches Run")
        await pg.keyboard.press("Enter")
        await pg.wait_for_selector(".ask textarea", timeout=10000)
        await pg.wait_for_timeout(100)
        focused = await pg.evaluate("""(() => { const a = document.activeElement, g = a.closest('[role=group]');
            const named = g && g.getAttribute('aria-labelledby').split(' ').map(id => document.getElementById(id).textContent).join(' ');
            return { tag:a.tagName, label:a.getAttribute('aria-label'), group:named }; })()""")
        check(focused["tag"] == "TEXTAREA" and focused["label"] == "Your answer" and "Which bread should I bake?" in (focused["group"] or ""),
              f"the question takes the focus, and its box is named by the question ({focused})")
        problems = await axe_problems(pg)
        check(not problems, f"axe-core finds no serious problems while the run waits for an answer {problems or ''}")
        await pg.emulate_media(color_scheme="dark")
        problems = await axe_problems(pg)
        check(not problems, f"nor in the dark theme {problems or ''}")
        await pg.emulate_media(color_scheme="light")
        await pg.keyboard.type("rye bread")
        await pg.keyboard.press("Control+Enter")
        await pg.wait_for_function("document.getElementById('run').disabled === false", timeout=15000)
        log = await pg.inner_text("#steps")
        check("Baking: rye bread" in log, "Ctrl+Enter sends the answer, and the run finishes with it")
        check(await pg.get_attribute("#steps", "role") == "log" and await pg.get_attribute("#status", "role") == "status",
              "the run log's new steps and the run's status are read out as they happen")

        # Building a program with the keyboard (Blockly 13's own, #242): the ? button says how, then Tab to the
        # block editor, T for the blocks, the arrows to a block, Enter to add it and Enter again to place it.
        await pg.evaluate("document.activeElement && document.activeElement.blur()")
        check(await tab_to(pg, "#keys-toggle"), "Tab reaches the keyboard help (?)")
        await pg.keyboard.press("Enter")
        help_text = await pg.inner_text("#keys") if await pg.is_visible("#keys") else ""
        check(await pg.evaluate("document.activeElement.id") == "keys-title" and "T opens the blocks" in help_text and "Ctrl+Shift+K" not in help_text,
              "it opens the keyboard help, with the focus on it, listing Blockly's keys")
        await pg.keyboard.press("Escape")
        check(await tab_to(pg, ".injectionDiv"), "Tab reaches the block editor")
        before = await pg.evaluate("Blockly.getMainWorkspace().getAllBlocks(false).length")
        heard = []
        named = """() => { const a = document.activeElement; return [a.getAttribute('role'), a.getAttribute('aria-label') || a.textContent.trim().slice(0, 60)]; }"""
        for key in ("t", "ArrowDown", "ArrowRight", "ArrowDown", "Enter"):
            await pg.keyboard.press(key)
            await pg.wait_for_timeout(150)
            heard.append(await pg.evaluate(named))
        await pg.keyboard.press("Enter")  # puts it where it is
        await pg.wait_for_timeout(150)
        after = await pg.evaluate("Blockly.getMainWorkspace().getAllBlocks(false).length")
        check(after > before, f"T, a category, a block and Enter add the block to the program ({before} blocks, then {after})")
        check(heard[0][0] == "treeitem" and heard[0][1] and heard[2][0] == "option" and heard[2][1],
              f"a screen reader hears each category and block as the keys reach it ({heard[:3]})")
        check(not await pg.evaluate("typeof window.NavigationController") == "function", "no keyboard plugin: it's Blockly's own")
        check(not errors, "no page errors" + (f" ({errors})" if errors else ""))
        await browser.close()
