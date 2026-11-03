"""End-to-end tests of the copy on GitHub Pages (#245): the site tools/pages.py builds, opened with no Claude, as a
browser would on github.io. It loads, says what it can and can't do there, saves files as ordinary downloads,
loads another language, and stops a run saying why. With your own API key (#293) it runs programs and builds them,
calling a stand-in for Claude's API, and the key stays out of everything it saves; its Content-Security-Policy lets
nothing else run or connect."""
import sys

from e2e.common import *  # noqa: F401,F403

KEY = "sk-ant-api03-" + "x" * 40 + "WXYZ"
BUILT = {"blocks": {"languageVersion": 0, "blocks": [{"type": "rb_start", "next": {"block": {"type": "rb_add_result",
         "inputs": {"TEXT": {"block": {"type": "text", "fields": {"TEXT": "built with my key"}}}}}}}]}}


def sse(*events):
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events)


def api_reply(text, stop="end_turn"):
    """A streamed reply, as Claude's API sends one: the text in two parts, then why it stopped."""
    half = len(text) // 2
    return sse({"type": "message_start", "message": {"id": "msg_test", "role": "assistant", "content": []}},
               {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
               {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text[:half]}},
               {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text[half:]}},
               {"type": "content_block_stop", "index": 0},
               {"type": "message_delta", "delta": {"stop_reason": stop}},
               {"type": "message_stop"})

sys.path.insert(0, str(ROOT / "tools"))
import pages as pages_tool  # noqa: E402


async def pages_tests():
    print("The copy on GitHub Pages")
    with tempfile.TemporaryDirectory() as tmp:
        site = pages_tool.build(pathlib.Path(tmp) / "_site")
        index = (site / "index.html").read_text(encoding="utf-8")
        langs = sorted(p.name for p in (site / "lang").glob("*.js"))
        policy = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', index)
        policy = policy.group(1) if policy else ""
        connect = next((d for d in policy.split("; ") if d.startswith("connect-src")), "")
        check(connect == "connect-src 'self' https://api.anthropic.com" and "'unsafe-inline'" not in policy.split("style-src")[0]
              and policy.count("'sha256-") == len(pages_tool.INLINE_SCRIPT.findall(index)),
              f"the copy has a Content-Security-Policy: connections only to itself and Claude's API, inline scripts by hash ({connect})")
        check(index.startswith("<!doctype html>") and '<meta charset="utf-8">' in index and 'name="viewport"' in index
              and len(langs) == len(list((ROOT / "lang").glob("*.js"))) and (site / ".nojekyll").exists(),
              f"tools/pages.py builds index.html as a whole document, with every language beside it ({len(langs)})")

        calls, api = [], {"status": 200, "reply": None}

        async def serve(r):
            u = r.request.url
            if u == "https://api.anthropic.com/v1/messages":  # a stand-in for Claude's API, which allows browsers that ask
                cors = {"access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "POST"}
                if r.request.method == "OPTIONS":
                    return await r.fulfill(status=204, headers=cors)
                body = json.loads(r.request.post_data or "{}")
                calls.append({"headers": await r.request.all_headers(), "body": body})
                if api["status"] != 200:
                    return await r.fulfill(status=api["status"], headers=cors, content_type="application/json",
                                           body=json.dumps({"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}}))
                prompt = body["messages"][-1]["content"]
                reply = api["reply"] if api["reply"] is not None else "ANSWER(" + str(prompt)[:20] + ")"
                return await r.fulfill(status=200, headers=cors, content_type="text/event-stream", body=api_reply(reply))
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
            errors, blocked = [], []
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.on("console", lambda m: "Content Security Policy" in m.text and blocked.append(m.text))
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
            check("Running needs Claude" in (banner or "") and "your own API key" in banner,
                  f"Run stops before starting, says it needs Claude, and where else it can come from ({banner})")

            # Your own API key (#293)
            check(await pg.is_visible("#own-key") and not await pg.is_visible("#own-key-panel"),
                  "the bar offers 'Use your own API key'")
            await pg.click("#own-key")
            await pg.fill("#own-key-input", "not-a-key")
            await pg.click("#own-key-use")
            msg = await pg.text_content("#own-key-msg")
            check("start with sk-ant-" in msg and await pg.is_visible("#own-key-panel"), f"something that isn't a key is turned down ({msg})")
            await pg.fill("#own-key-input", KEY)
            await pg.click("#own-key-use")
            text = await pg.text_content("#offsite")
            stored = await pg.evaluate("k => [sessionStorage.getItem(k), localStorage.getItem(k)]", "second-thought-anthropic-key")
            check("\u2026WXYZ" in text and KEY not in text and not await pg.is_visible("#own-key-panel")
                  and await pg.is_visible("#own-key-forget") and not await pg.is_visible("#offsite-link"),
                  f"with a key, the bar shows only its last four characters, and offers Forget my key ({text.strip()[:80]})")
            check(stored == [KEY, None], "it's kept for this tab only, unless Remember is ticked")

            await load_state(pg, script(add(val(blk("rb_ask", inputs={"TEXT": tx("What rhymes with rye?")})))))
            status = await run_program(pg)
            results = await pg.eval_on_selector_all(".result-text", "e => e.map(x => x.textContent)")
            h = calls[-1]["headers"] if calls else {}
            check(calls and h.get("x-api-key") == KEY and h.get("anthropic-dangerous-direct-browser-access") == "true"
                  and h.get("anthropic-version") and calls[-1]["body"]["model"] == "claude-sonnet-5-5" and calls[-1]["body"]["stream"]
                  and "What rhymes with rye?" in json.dumps(calls[-1]["body"]["messages"]) and any("ANSWER(" in x for x in results),
                  f"Run calls Claude's API with the key, and the reply comes back as the result ({status}; {results})")

            api["status"] = 401
            await run_program(pg)
            banner = await pg.text_content("#banner") or ""
            steps = json.dumps(await step_texts(pg))
            check("refused your API key" in (banner + steps), f"a refused key says so ({(banner or steps)[:120]})")
            api["status"] = 200

            api["reply"] = json.dumps({"program": BUILT, "summary": "Adds one result.", "unmapped": []})
            await pg.fill("#describe-text", "add a result saying built with my key")
            await pg.click("#describe-build")
            for _ in range(100):  # (wait_for_function evaluates a string, which the policy rightly refuses)
                if await pg.is_visible("#describe-load") or "bad" in (await pg.get_attribute("#describe-msg", "class") or ""):
                    break
                await pg.wait_for_timeout(100)
            msg = await pg.text_content("#describe-msg")
            check("Adds one result." in msg and calls[-1]["body"].get("system", "").startswith("Reply with only the JSON"),
                  f"Build it works with the key too, asking for JSON ({msg[:80]})")
            api["reply"] = None

            await pg.click("#io-toggle")
            async with pg.expect_download() as got:
                await pg.click("#io-py-save")
            zipped = pathlib.Path(await (await got.value).path()).read_bytes()
            async with pg.expect_download() as got:
                await pg.click("#io-save")
            saved = pathlib.Path(await (await got.value).path()).read_text(encoding="utf-8")
            await pg.click("#io-toggle")
            local = await pg.evaluate("JSON.stringify(Object.entries(localStorage))")
            check(KEY.encode() not in zipped and "WXYZ" not in saved and KEY not in local,
                  "the key isn't in the exported Python, the saved block file or what the page keeps in the browser")

            await pg.click("#own-key-forget")
            stored = await pg.evaluate("k => [sessionStorage.getItem(k), localStorage.getItem(k)]", "second-thought-anthropic-key")
            await pg.click("#run")
            await pg.wait_for_timeout(500)
            banner = await pg.text_content("#banner")
            check(stored == [None, None] and await pg.is_visible("#own-key") and "Running needs Claude" in (banner or ""),
                  "Forget my key removes it, and Run needs Claude again")

            await pg.click("#own-key")
            await pg.fill("#own-key-input", KEY)
            await pg.check("#own-key-remember")
            await pg.click("#own-key-use")
            await pg.reload()
            await pg.wait_for_timeout(1500)
            check("\u2026WXYZ" in (await pg.text_content("#offsite")), "with Remember ticked, the key is still there after reloading")
            await pg.click("#own-key-forget")

            await pg.select_option("#lang", "de")
            await pg.wait_for_timeout(2000)
            loaded = await pg.evaluate("!!(window.ST_I18N && window.ST_I18N.name)")
            check(loaded and await pg.text_content("#run") != "Run",
                  "another language loads from lang/ beside the page, as on claude.ai")
            check(not errors, "no page errors" + (f": {errors[:2]}" if errors else ""))
            check(not blocked, "the Content-Security-Policy blocked nothing the page uses" + (f": {blocked[:2]}" if blocked else ""))
            await browser.close()
