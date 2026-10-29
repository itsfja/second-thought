"""End-to-end tests of Describe a program: Claude (the stand-in) builds the blocks, the page says what they can do and
what was left out before loading them, follow-up changes send the current program, and unknown blocks are refused."""
from e2e.common import *  # noqa: F401,F403

WASHING = {"blocks": {"languageVersion": 0, "blocks": [
    {"type": "rb_when_time", "fields": {"HOUR": 18, "MINUTE": 0, "DAYS": "weekdays"},
     "next": {"block": {"type": "rb_tg_send", "inputs": {"TEXT": {"block": {"type": "rb_ask", "inputs": {"TEXT": {"block": {"type": "rb_longtext",
              "fields": {"TEXT": "The best two hours this weekend to dry washing in London"}}}}}}}}}},
    {"type": "rb_start", "next": {"block": {"type": "variables_set", "fields": {"VAR": {"name": "town"}},
              "inputs": {"VALUE": {"block": {"type": "text", "fields": {"TEXT": "London"}}}}}}}]}}


async def describe_tests():
    print("Describe a program")
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await browser.new_page(viewport={"width": 1400, "height": 1000})
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.route("**/*", route)
        await pg.add_init_script(MOCK)
        await pg.goto("http://test/")
        await pg.wait_for_timeout(1500)
        await load_state(pg, script(add(tx("the program I had"))))

        await pg.click("#describe-build")
        msg = await pg.text_content("#describe-msg")
        check("Describe what the program should do first." in msg, f"an empty description asks for one ({msg})")

        await pg.evaluate("r => { window.__jsonScript = r; window.__jsonPrompts = []; }",
                          [{"program": WASHING, "summary": "Every weekday at 6pm it texts you the best drying time.", "unmapped": ["checking the pollen count"]}])
        await pg.fill("#describe-text", "every Friday at 6pm, find the best two hours this weekend to dry washing and send it to me on Telegram")
        await pg.click("#describe-build")
        await pg.wait_for_function("!document.getElementById('describe-load').hidden || document.getElementById('describe-msg').className.includes('bad')")
        msg = await pg.text_content("#describe-msg")
        prompt = (await pg.evaluate("window.__jsonPrompts"))[-1]
        check("Every weekday at 6pm it texts you" in msg and "7 blocks." in msg and "send Telegram messages" in msg
              and "Left out: checking the pollen count." in msg and await pg.is_visible("#describe-load"),
              f"before loading, it says what the program does, its size, what it can do and what was left out ({msg})")
        check("DESCRIPTION:\nevery Friday at 6pm" in prompt and "rb_tg_send" in prompt and "THE PROGRAM NOW" not in prompt,
              "the prompt has the description and the block list")
        types = await pg.evaluate("Blockly.getMainWorkspace().getAllBlocks(false).map(b => b.type)")
        check("rb_tg_send" not in types, "nothing loads until you say so")

        await pg.click("#describe-load")
        types = await pg.evaluate("Blockly.getMainWorkspace().getAllBlocks(false).map(b => b.type)")
        names = await pg.evaluate("Blockly.getMainWorkspace().getAllVariables().map(v => v.name)")
        msg = await pg.text_content("#describe-msg")
        check("rb_tg_send" in types and "rb_when_time" in types and "town" in names and await pg.is_visible("#describe-undo")
              and "Loaded Claude's program (7 blocks). Check the blocks before running." in msg,
              f"Load it puts the blocks on the canvas, with Undo ({msg})")

        await pg.evaluate("r => { window.__jsonScript = r; window.__jsonPrompts = []; }", [{"program": WASHING, "summary": "Also emails it.", "unmapped": []}])
        await pg.fill("#describe-text", "also email it to me")
        await pg.click("#describe-change")
        await pg.wait_for_function("!document.getElementById('describe-load').hidden || document.getElementById('describe-msg').className.includes('bad')")
        prompt = (await pg.evaluate("window.__jsonPrompts"))[-1]
        now = prompt.split("THE PROGRAM NOW:\n")[-1].split("\n\nCHANGE IT LIKE THIS")[0]
        check("CHANGE IT LIKE THIS (keep everything else as it is):\nalso email it to me" in prompt and '"rb_tg_send"' in now
              and '{"name": "town"}' in now.replace('{"name":"town"}', '{"name": "town"}') and '"id"' not in now,
              "Change this program sends the program on the canvas (variables by name, no ids) with the change")
        await pg.click("#describe-discard")
        check(not await pg.is_visible("#describe-out"), "Discard drops Claude's version")

        await pg.evaluate("r => { window.__jsonScript = r; }", [{"program": {"blocks": {"languageVersion": 0, "blocks": [{"type": "rb_teleport"}]}}}])
        await pg.fill("#describe-text", "teleport me")
        await pg.click("#describe-build")
        await pg.wait_for_function("document.getElementById('describe-msg').className.includes('bad')")
        msg = await pg.text_content("#describe-msg")
        check("rb_teleport" in msg and "nothing was loaded" in msg and not await pg.is_visible("#describe-load"),
              f"a program with blocks the page doesn't have is refused, as for imports ({msg})")
        await pg.evaluate("r => { window.__jsonScript = r; }", [{"summary": "no program"}])
        await pg.click("#describe-build")
        await pg.wait_for_function("document.getElementById('describe-msg').textContent.includes(\"wasn't a block program\")")
        check(True, "a reply with no program says so")

        await pg.click("#describe-undo") if await pg.is_visible("#describe-undo") else None
        await load_state(pg, script(add(tx("before"))))
        await pg.evaluate("r => { window.__jsonScript = r; }", [{"program": WASHING, "summary": "s", "unmapped": []}])
        await pg.fill("#describe-text", "washing")
        await pg.click("#describe-build")
        await pg.wait_for_selector("#describe-load:not([hidden])")
        await pg.click("#describe-load")
        await pg.click("#describe-undo")
        types = await pg.evaluate("Blockly.getMainWorkspace().getAllBlocks(false).map(b => b.type)")
        check("rb_tg_send" not in types and "rb_add_result" in types, "Undo puts the previous program back")
        check(not errors, "no page errors" + (f": {errors[:2]}" if errors else ""))
        await browser.close()
