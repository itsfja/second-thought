"""End-to-end tests of the copy on GitHub Pages (#245): the site tools/pages.py builds, opened with no Claude, as a
browser would on github.io. It loads, says what it can and can't do there, saves files as ordinary downloads,
loads another language, and stops a run saying why."""
import sys

from e2e.common import *  # noqa: F401,F403

sys.path.insert(0, str(ROOT / "tools"))
import pages as pages_tool  # noqa: E402


async def pages_tests():
    print("The copy on GitHub Pages")
    with tempfile.TemporaryDirectory() as tmp:
        site = pages_tool.build(pathlib.Path(tmp) / "_site")
        index = (site / "index.html").read_text(encoding="utf-8")
        langs = sorted(p.name for p in (site / "lang").glob("*.js"))
        check(index.startswith("<!doctype html>") and '<meta charset="utf-8">' in index and 'name="viewport"' in index
              and len(langs) == len(list((ROOT / "lang").glob("*.js"))) and (site / ".nojekyll").exists(),
              f"tools/pages.py builds index.html as a whole document, with every language beside it ({len(langs)})")

        async def serve(r):
            u = r.request.url
            if u.startswith("http://pages.test/"):
                rel = u[len("http://pages.test/"):].split("?")[0].split("#")[0] or "index.html"
                path = site / rel
                if path.is_file():
                    kind = "text/html" if rel.endswith(".html") else "application/javascript"
                    return await r.fulfill(path=str(path), content_type=kind)
                return await r.fulfill(status=404, body="")
            return await route(r)  # Blockly and the fonts, as for the page on claude.ai

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            ctx = await browser.new_context(viewport={"width": 1400, "height": 1000}, accept_downloads=True)
            pg = await ctx.new_page()
            errors = []
            pg.on("pageerror", lambda e: errors.append(str(e)))
            await pg.route("**/*", serve)
            await pg.goto("http://pages.test/")
            await pg.wait_for_timeout(1500)
            mode = await pg.evaluate("document.compatMode")
            check(mode == "CSS1Compat", f"the page renders in standards mode, not quirks mode ({mode})")
            text = await pg.text_content("#offsite") if await pg.is_visible("#offsite") else ""
            href = await pg.get_attribute("#offsite-link", "href")
            check("can't run them with Claude" in text and href == "https://claude.ai/artifact/XmNRmDbYLY3bo7o31nvdzN",
                  f"with no Claude, it says what it can do here, and links to the page on claude.ai ({text[:90]})")

            await pg.click("#io-toggle")
            await pg.fill("#io-name", "pages-test")
            async with pg.expect_download() as got:
                await pg.click("#io-save")
            download = await got.value
            data = json.loads(pathlib.Path(await download.path()).read_text(encoding="utf-8"))
            check(download.suggested_filename == "pages-test.json" and data.get("program"),
                  f"Save gives an ordinary browser download of the block file ({download.suggested_filename})")
            async with pg.expect_download() as got:
                await pg.click("#io-py-save")
            check((await got.value).suggested_filename == "pages-test.zip", "and Save Python gives the zip")
            await pg.click("#io-toggle")

            await pg.click("#run")
            await pg.wait_for_timeout(800)
            banner = await pg.text_content("#banner")
            check("Running needs Claude" in (banner or ""), f"Run stops before starting, and says it needs Claude ({banner})")

            await pg.select_option("#lang", "de")
            await pg.wait_for_timeout(2000)
            loaded = await pg.evaluate("!!(window.ST_I18N && window.ST_I18N.name)")
            check(loaded and await pg.text_content("#run") != "Run",
                  "another language loads from lang/ beside the page, as on claude.ai")
            check(not errors, "no page errors" + (f": {errors[:2]}" if errors else ""))
            await browser.close()
