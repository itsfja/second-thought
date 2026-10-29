"""End-to-end tests of the block file format: every example and gallery program loads and saves with nothing lost, and a
format change is carried by a migration that every way of loading a program runs."""
from e2e.common import *  # noqa: F401,F403

# A program as a page with an older format would have saved it: 'rb_old_say' is a made-up block that the test's
# migration turns into rb_say, as a real one would rename a block or a field.
OLD = {"format": "reflection-blocks", "version": 1, "name": "old-program", "program": {"blocks": {"languageVersion": 0, "blocks": [
    {"type": "rb_start", "x": 20, "y": 20, "next": {"block": {"type": "rb_old_say", "inputs": {"WORDS": {"block": {"type": "text", "fields": {"TEXT": "hello"}}}}}}}]}}}
MIGRATE = """() => window.__setFormat(2, { 1: state => {
  const walk = o => { if (Array.isArray(o)) return o.forEach(walk); if (!o || typeof o !== "object") return;
    if (o.type === "rb_old_say") { o.type = "rb_say"; o.inputs = { TEXT:o.inputs.WORDS }; } Object.values(o).forEach(walk); };
  walk(state); return state; } })"""



async def format_tests():
    print("Block file format")
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await browser.new_page(viewport={"width": 1400, "height": 1000})
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.route("**/*", route)
        await pg.add_init_script(MOCK)
        await pg.goto("http://test/")
        await pg.wait_for_timeout(1500)

        # Every example and gallery program: loaded and saved again, it has the same blocks (nothing dropped on load).
        lost = await pg.evaluate("""() => {
          const ws = Blockly.getMainWorkspace(), out = [];
          const count = s => { const n = {}; const walk = o => { if (Array.isArray(o)) return o.forEach(walk); if (!o || typeof o !== "object") return;
            if (typeof o.type === "string" && Blockly.Blocks[o.type]) n[o.type] = (n[o.type] || 0) + 1; Object.values(o).forEach(walk); }; walk(s.blocks); return n; };
          window.__exampleStates().forEach(([k, s]) => { Blockly.serialization.workspaces.load(s, ws);
            const a = JSON.stringify(Object.entries(count(s)).sort()), b = JSON.stringify(Object.entries(count(Blockly.serialization.workspaces.save(ws))).sort());
            if (a !== b) out.push(k); });
          return { lost:out, n:window.__exampleStates().length }; }""")
        check(not lost["lost"] and lost["n"] > 100, f"every one of the {lost['n']} examples and gallery programs loads and saves with no block lost {lost['lost'][:5]}")

        await pg.click("#io-toggle")
        await pg.click("#io-copy")
        text = await pg.input_value("#io-export-text")
        check('"version": 1' in text, "a saved block file says which block format it has")

        await pg.evaluate(MIGRATE)
        await paste(pg, json.dumps(OLD))
        await pg.click("#io-load-paste")
        msg = await pg.text_content("#io-import-msg")
        got = await pg.evaluate("Blockly.getMainWorkspace().getAllBlocks(false).map(b => b.type)")
        say = await pg.evaluate("(Blockly.getMainWorkspace().getAllBlocks(false).find(b => b.type === 'rb_say') || {getInputTargetBlock:() => null}).getInputTargetBlock('TEXT')?.getFieldValue('TEXT')")
        check("rb_say" in got and say == "hello" and "brought up to date (block format 1 to 2)" in msg,
              f"an older block file is upgraded by the migration as it loads, and the page says so ({msg})")
        await pg.click("#io-copy")
        check('"version": 2' in await pg.input_value("#io-export-text"), "once upgraded, it's saved with the new format")

        newer = dict(OLD, version=3)
        await paste(pg, json.dumps(newer))
        await pg.click("#io-load-paste")
        msg = await pg.text_content("#io-import-msg")
        got = await pg.evaluate("Blockly.getMainWorkspace().getAllBlocks(false).map(b => b.type)")
        check("saved by a newer Second Thought (block format 3; this page reads up to 2)" in msg and "rb_say" in got,
              f"a block file from a newer page is refused, and the canvas is left as it was ({msg})")

        py = await export_python(pg, "old-program")
        await pg.evaluate("() => window.__setFormat(3, { 2: state => state })")
        await paste(pg, py)
        await pg.click("#io-load-paste")
        msg = await pg.text_content("#io-import-msg")
        check("brought up to date (block format 2 to 3)" in msg, f"exported Python carries its format too, and is upgraded when imported ({msg})")
        await pg.evaluate("() => window.__setFormat(1, {})")
        await pg.click("#io-toggle")
        check(not errors, "no page errors" + (f": {errors[:2]}" if errors else ""))
        await browser.close()
