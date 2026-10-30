"""End-to-end tests of test cases for programs: a good run's answers are kept with what its result must do, Run tests
replays them on the page with a strict check, and exported Python runs the same cases with --test, acting on nothing."""
from e2e.common import *  # noqa: F401,F403
from e2e.python_export import drive  # noqa: E402


def program():
    return script(blk("rb_ask_me", inputs={"TEXT": tx("What should I write about?")}),
                  blk("rb_task", inputs={"TEXT": {"block": {"type": "text_join", "extraState": {"itemCount": 2},
                                                           "inputs": {"ADD0": tx("A short note about "), "ADD1": val(blk("rb_answer"))}}}}),
                  blk("rb_generate"),
                  blk("rb_tg_send", inputs={"TEXT": val(blk("rb_draft"))}),
                  blk("rb_result"))


async def program_test_tests():
    print("Test cases for programs")
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await browser.new_page(viewport={"width": 1400, "height": 1000})
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.route("**/*", route)
        await pg.add_init_script(MOCK)
        await pg.goto("http://test/")
        await pg.wait_for_timeout(1500)
        await load_state(pg, program())
        check(not await pg.is_visible("#log-tests"), "with no test cases there's no Run tests button")

        await pg.click("#run")
        await pg.wait_for_selector(".ask textarea")
        await pg.fill(".ask textarea", "rye bread")
        await pg.click(".ask button.primary")
        await pg.wait_for_selector(".result")
        await pg.click(".result-actions button:has-text('Save as test case')")
        await pg.click(".test-form button.primary")
        msg = await pg.text_content(".test-form .msg")
        check("Say what the result must do first." in msg, "a test case needs criteria")
        await pg.fill(".test-form textarea", "mentions rye bread; under 100 words")
        await pg.click(".test-form button.primary")
        msg = await pg.text_content(".test-form .msg")
        label = await pg.text_content("#log-tests")
        check("Saved." in msg and label == "Run tests (1)", f"Save as test case keeps the run's answers with the criteria ({msg}; {label})")

        await pg.evaluate("r => { window.__jsonScript = r; }", [{"approved": True, "problems": []}])
        await pg.click("#log-tests")
        await pg.wait_for_function("[...document.querySelectorAll('.step-name')].some(e => e.textContent === 'Tests')", timeout=20000)
        bodies = await pg.eval_on_selector_all(".step", "e => e.map(x => x.innerText)")
        check(any("Test answer" in b and "rye bread" in b for b in bodies) and not await pg.is_visible(".ask textarea")
              and any("PASS  Test 1" in b for b in bodies) and "1 of 1 passed." in (await pg.text_content("#status")),
              f"Run tests replays the saved answer instead of asking, then checks the result ({bodies[-1:]})")
        await pg.evaluate("r => { window.__jsonScript = r; }", [{"approved": False, "problems": ["it never mentions rye"]}])
        await pg.click("#log-tests")
        await pg.wait_for_function("[...document.querySelectorAll('.step-name')].some(e => e.textContent === 'Tests')", timeout=20000)
        bodies = await pg.eval_on_selector_all(".step", "e => e.map(x => x.innerText)")
        check(any("FAIL  Test 1" in b and "it never mentions rye" in b for b in bodies) and "0 of 1 passed." in (await pg.text_content("#status")),
              "a result that misses its criteria fails, with the reviewer's problems")

        files = {f["name"]: f["text"] for f in await pg.evaluate("window.__exportFiles()")}
        cases = json.loads(files.get("my-program.tests.json", "[]"))
        check(len(cases) == 1 and cases[0]["inputs"]["answer"] == ["rye bread"] and cases[0]["criteria"] == "mentions rye bread; under 100 words",
              f"the exported zip has the test cases next to the program ({sorted(files)})")
        await pg.click("#io-toggle")
        await pg.click("#io-copy")
        block_file = json.loads(await pg.input_value("#io-export-text"))
        check(block_file.get("tests") == cases, "the block file carries its test cases")
        await pg.click("#io-toggle")
        await pg.evaluate("() => { const s = document.getElementById('example'); s.value = s.options[0].value; document.getElementById('load').click(); }")
        check(not await pg.is_visible("#log-tests"), "loading another program leaves its tests behind")
        await pg.click("#io-toggle")
        await paste(pg, json.dumps(block_file))
        await pg.click("#io-load-paste")
        await pg.click("#io-toggle")
        check(await pg.text_content("#log-tests") == "Run tests (1)", "importing the block file brings its test cases back")
        check(not errors, "no page errors" + (f": {errors[:2]}" if errors else ""))
        await browser.close()

    env = dict(os.environ, PYTHONPATH=str(HERE / "fakeapi"), PYTHONIOENCODING="utf-8", ANTHROPIC_API_KEY="test", RB_LANGUAGE="en",
               TELEGRAM_BOT_TOKEN="123:test", TELEGRAM_CHAT_ID="1", TELEGRAM_API_URL="http://127.0.0.1:9/never")
    with tempfile.TemporaryDirectory() as tmp:
        prog = pathlib.Path(tmp) / "my-program.py"
        prog.write_text(files["my-program.py"], encoding="utf-8")
        (pathlib.Path(tmp) / "my-program.tests.json").write_text(json.dumps(cases * 2), encoding="utf-8")
        code, out, err = drive([sys.executable, "-u", str(prog), "--test"], env, tmp)
        check("rye bread" in out and "? What should I write about?" not in out and "Not done, because this is a test: send a Telegram message" in out,
              f"--test replays the answers and acts on nothing ({(err or out)[-400:]!r})")
        check(code == 1 and "1 of 2 passed." in out and "PASS  Test 1" in out and "FAIL  Test 1" in out and "too vague" in out,
              f"--test checks each result and says which passed, with an exit code for scripts ({out[-300:]!r})")
        (pathlib.Path(tmp) / "my-program.tests.json").write_text(json.dumps([dict(cases[0], inputs={})]), encoding="utf-8")
        code, out, _ = drive([sys.executable, "-u", str(prog), "--test"], env, tmp)
        check(code == 1 and "The test case has no answer for this step (What should I write about?)" in out,
              f"a test case missing an answer fails that case, saying which step ({out[-300:]!r})")
        (pathlib.Path(tmp) / "my-program.tests.json").unlink()
        code, out, _ = drive([sys.executable, "-u", str(prog), "--test"], env, tmp)
        check(code == 1 and "No tests:" in out, "with no tests file, --test says how to make one")
