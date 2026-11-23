"""The offline page (#314): tools/offline.py's one file, opened from disk with the network cut off. It loads, shows the
examples, builds and exports, and switches language, all with nothing fetched; its Content-Security-Policy blocks
nothing it uses."""
import sys

from e2e.common import *  # noqa: F401,F403

sys.path.insert(0, str(ROOT / "tools"))
import offline as offline_tool  # noqa: E402


async def offline_tests():
    print("The offline page")
    with tempfile.TemporaryDirectory() as tmp:
        path = offline_tool.build(pathlib.Path(tmp) / "second-thought-offline.html")
        text = path.read_text(encoding="utf-8")
        # The file holds every language's words, so it grows with each language (#426, #448, #469-#473, #459): about
        # 4 MB for the page and libraries and under 0.5 MB a language (an ancient script's letters take four bytes
        # each, and Windows' CRLF line endings add a little), so the bound grows with the languages instead of being
        # raised by hand each time one is added.
        limit = 5e6 + 0.5e6 * len(list((ROOT / "lang").glob("*.js")))
        check(path.stat().st_size < limit and 'http-equiv="Content-Security-Policy"' in text and "lang/" not in re.findall(r'<script src="([^"]+)"', text),
              f"tools/offline.py builds one file with the libraries and languages inside, and a security policy ({path.stat().st_size / 1e6:.1f} MB, under {limit / 1e6:.1f} MB)")
        fetched = []

        async def no_network(r):
            if r.request.url.startswith("file:"):
                return await r.continue_()
            fetched.append(r.request.url)
            await r.abort()

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            ctx = await browser.new_context(viewport={"width": 1400, "height": 1000}, accept_downloads=True)
            await ctx.route("**/*", no_network)
            pg = await ctx.new_page()
            errors, blocked = [], []
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.on("console", lambda m: "Content Security Policy" in m.text and blocked.append(m.text))
            await pg.goto(path.as_uri())
            await pg.wait_for_timeout(2000)
            blocks = await pg.evaluate("document.querySelectorAll('.blocklyDraggable').length")
            check(blocks > 0 and await pg.is_visible("#offsite"), f"it opens from disk with no network, blocks on the canvas, saying runs need a key ({blocks} blocks)")

            # The three typefaces are inside the file as data: URIs and load with no network (#453)
            faces = await pg.evaluate("""async () => { await document.fonts.ready;
                return ['Atkinson Hyperlegible', 'Bricolage Grotesque', 'JetBrains Mono'].map(f => document.fonts.check('16px "' + f + '"')); }""")
            font_fetches = [u for u in fetched if "fonts.g" in u]
            check(all(faces) and not font_fetches,
                  f"its own typefaces are inside the file and load with no network (faces {faces}, fetched {font_fetches[:2]})")

            await load_state(pg, script(add(val(blk("rb_ask", inputs={"TEXT": tx("What rhymes with rye?")})))))
            await pg.click("#io-export")
            await pg.fill("#io-name", "offline-test")
            async with pg.expect_download() as got:
                await pg.click("#io-py-save")
            zipped = pathlib.Path(await (await got.value).path()).read_bytes()
            await pg.click("#io-export")
            check(zipped[:2] == b"PK" and b"What rhymes with rye?" in zipped, "it exports a program to Python with no network")

            await pg.select_option("#lang", "de")
            await pg.wait_for_timeout(2500)
            german = await pg.evaluate("!!(window.ST_I18N && window.ST_I18N.name === 'Deutsch') && Blockly.Msg.CONTROLS_IF_MSG_IF")
            run_label = await pg.text_content("#run")
            check(german and german != "if" and run_label != "Run",
                  f"it switches to German, Blockly's own words too, from inside the file ({german}, {run_label})")
            await pg.select_option("#lang", "en")
            await pg.wait_for_timeout(1500)
            libs = [u for u in fetched if "jsdelivr" in u or "/lang/" in u]
            check(not libs, f"nothing it needs was fetched: libraries and languages came from inside ({libs[:3]})")
            check(not errors, "no page errors" + (f": {errors[:2]}" if errors else ""))
            check(not blocked, "the Content-Security-Policy blocked nothing the page uses" + (f": {blocked[:2]}" if blocked else ""))
            await browser.close()
