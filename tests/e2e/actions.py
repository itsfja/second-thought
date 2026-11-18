"""End-to-end tests of Save as GitHub Actions: which programs can run there, the workflow and its times, the secrets,
and the exported program running one scheduled script the way the workflow runs it."""
from e2e.common import *  # noqa: F401,F403
from e2e.python_export import drive  # noqa: E402


def when_time(h, m, days, *steps):
    hat = {"type": "rb_when_time", "fields": {"HOUR": h, "MINUTE": m, "DAYS": days}, "x": 400, "y": 20}
    for a, b in zip(steps, steps[1:]):
        a["next"] = {"block": b}
    if steps:
        hat["next"] = {"block": steps[0]}
    return hat


def every(n, unit, *steps):
    hat = when_time(0, 0, "every", *steps)
    hat.update(type="rb_every", fields={"N": n, "UNIT": unit}, y=300)
    return hat


def program(*tops):
    return {"blocks": {"languageVersion": 0, "blocks": list(tops)}}


def workflow(files):
    import yaml
    wf = next(f["text"] for f in files if f["name"].startswith(".github/workflows/"))
    data = yaml.safe_load(wf)
    return wf, data, data.get("on", data.get(True))  # YAML 1.1 reads a bare 'on' as true


async def actions_tests():
    print("Save as GitHub Actions")
    hour = (datetime.datetime.utcnow().hour + 3) % 24  # a time it isn't, so the script isn't due
    sched = program(script(add(tx("started by hand")))["blocks"]["blocks"][0],
                    when_time(hour, 15, "every", add(tx("the scheduled script ran"))),
                    every(30, "m", add(tx("every half hour"))))
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for tz, crons in [("Europe/London", None), ("Asia/Tokyo", ["0 22 * * 0-4"])]:
            ctx = await browser.new_context(viewport={"width": 1400, "height": 1000}, timezone_id=tz)
            pg = await ctx.new_page()
            errors = []
            pg.on("pageerror", lambda e: errors.append(str(e)))
            await pg.route("**/*", route)
            await pg.add_init_script(MOCK)
            await pg.goto("http://test/")
            await pg.wait_for_timeout(1500)
            if tz == "Asia/Tokyo":
                await load_state(pg, program(when_time(7, 0, "weekdays", add(tx("x")))))
                _, _, on = workflow(await pg.evaluate("window.__actionsFiles()"))
                got = [c["cron"] for c in on["schedule"]]
                check(got == crons, f"with no summer time, 07:00 on weekdays in Tokyo is one line, 22:00 UTC Sunday to Thursday ({got})")
                await ctx.close()
                continue

            await load_state(pg, program(when_time(18, 0, "weekdays", add(tx("x"))), every(30, "m", add(tx("y"))), every(2, "m", add(tx("z")))))
            files = await pg.evaluate("window.__actionsFiles()")
            wf, data, on = workflow(files)
            got = [c["cron"] for c in on["schedule"]]
            check(got == ["0 18 * * 1-5", "0 17 * * 1-5", "*/30 * * * *", "*/5 * * * *"],
                  f"18:00 on weekdays in London is 18:00 UTC in winter and 17:00 in summer, and 'every' is GitHub's shortest, 5 minutes ({got})")
            step = data["jobs"]["run"]["steps"][3]
            check(step["env"]["TZ"] == "Europe/London" and step["env"]["RB_APPROVE"] == "no" and "--run-schedule 1" in step["run"]
                  and '"0 17 * * 1-5") python my-program.py --run-schedule 1' in step["run"] and "--now" in step["run"],
                  "each cron line runs its script by number, in the program's time zone; Run workflow runs one now")
            check(on["workflow_dispatch"]["inputs"]["script"]["options"] == ["1: when it's 18:00 (weekdays)", "2: every 30 min", "3: every 2 min"],
                  "Run workflow offers each scheduled script by name")
            check("secrets." not in wf.split("env:")[0] and data["permissions"] == {"contents": "write"}
                  and any("git push" in (s.get("run") or "") for s in data["jobs"]["run"]["steps"]),
                  "what it remembers is committed back to the repository after each run")
            uses = [st_["uses"] for st_ in data["jobs"]["run"]["steps"] if "uses" in st_]
            check(uses == ["actions/checkout@v5", "actions/setup-python@v6"], f"it uses the current actions, which run on Node.js 24 ({uses})")
            check(step["env"].get("ANTHROPIC_WORKSPACE_ID") == "${{ secrets.ANTHROPIC_WORKSPACE_ID }}"
                  and "`ANTHROPIC_WORKSPACE_ID` (if you need it)" in next(f["text"] for f in files if f["name"] == "SETUP.md"),
                  "a Claude key made for a whole organisation can say its workspace, with an optional secret SETUP.md explains")

            await paste_gallery(pg, "rain-window")
            files = await pg.evaluate("window.__actionsFiles()")
            names = [f["name"] for f in files]
            wf, data, on = workflow(files)
            env = data["jobs"]["run"]["steps"][3]["env"]
            setup = next(f["text"] for f in files if f["name"] == "SETUP.md")
            check(names == ["rain-window.py", "requirements.txt", ".github/workflows/rain-window.yml", "SETUP.md", ".gitignore"]
                  and "second-thought.ini" not in names, f"the zip has the program, its workflow and SETUP.md, and no settings file ({names})")
            check(env.get("ANTHROPIC_API_KEY") == "${{ secrets.ANTHROPIC_API_KEY }}" and env.get("TELEGRAM_BOT_TOKEN") == "${{ secrets.TELEGRAM_BOT_TOKEN }}"
                  and "`ANTHROPIC_API_KEY`" in setup and "`TELEGRAM_CHAT_ID`" in setup and "send Telegram messages" in setup,
                  "the keys come from repository secrets, and SETUP.md lists them and what the program can do")
            await paste_gallery(pg, "dep-watcher")
            wf, data, _ = workflow(await pg.evaluate("window.__actionsFiles()"))
            check(data["jobs"]["run"]["steps"][3]["env"].get("GITHUB_TOKEN") == "${{ secrets.ST_GITHUB_TOKEN }}",
                  "the GitHub token comes from a secret GitHub allows the name of")

            for name, why in [("leaving-home-check", "waits for things to happen"), ("family-archivist", "waits for things to happen")]:
                await paste_gallery(pg, name)
                r = await pg.evaluate("window.__actionsFiles()")
                check(isinstance(r, dict) and why in r.get("error", ""), f"{name} is refused: it {why} ({r if isinstance(r, dict) else 'not refused'})")
            await load_state(pg, script(add(tx("x"))))
            r = await pg.evaluate("window.__actionsFiles()")
            check(isinstance(r, dict) and "nothing to run on a schedule" in r.get("error", ""), "a program with no schedule is refused")
            asks = program(when_time(9, 0, "every", blk("rb_broadcast", inputs={"MSG": {"shadow": {"type": "text", "fields": {"TEXT": "go"}}}})),
                           {"type": "rb_receive", "fields": {"MSG": "go"}, "x": 20, "y": 400,
                            "next": {"block": blk("rb_ask_me", inputs={"TEXT": tx("Which one?")})}})
            await load_state(pg, asks)
            r = await pg.evaluate("window.__actionsFiles()")
            check(isinstance(r, dict) and "asks you questions" in r.get("error", ""),
                  "a scheduled script that asks a question, even in the script it starts, is refused")
            await pg.click("#io-export")
            await pg.click("#io-gha-save")
            msg = await pg.text_content("#io-export-msg")
            check("can't run on GitHub Actions: it asks you questions" in msg, f"the page says why, instead of saving ({msg})")
            await pg.click("#io-export")

            # Test cases (#246): a test job, run on push and from Run workflow, never on the schedule.
            with_tests = {"format": "reflection-blocks", "version": 1, "name": "tested", "program": program(when_time(9, 0, "every", add(tx("x")))),
                          "tests": [{"name": "Says x", "value": "", "inputs": {}, "criteria": "It says x."}]}
            await pg.click("#io-export")
            await pg.fill("#io-paste", json.dumps(with_tests))
            await pg.click("#io-load-paste")
            await pg.wait_for_timeout(300)
            await pg.fill("#io-name", "tested")
            await pg.click("#io-export")
            files = await pg.evaluate("window.__actionsFiles()")
            names = [f["name"] for f in files]
            wf, data, on = workflow(files)
            setup = next(f["text"] for f in files if f["name"] == "SETUP.md")
            test_job = data["jobs"].get("test", {})
            check("tested.tests.json" in names and set(on["push"]["paths"]) == {"tested.py", "tested.tests.json", ".github/workflows/tested.yml"},
                  f"a program with test cases brings them, and they run when the program, its tests or the workflow change ({names})")
            check(test_job.get("if") == "github.event_name == 'push' || inputs.script == 'tests: run the test cases'"
                  and "schedule" in data["jobs"]["run"]["if"] and "push" not in data["jobs"]["run"]["if"]
                  and test_job["steps"][-1]["run"] == "python tested.py --test" and test_job["permissions"] == {"contents": "read"},
                  "the test job runs on push and from Run workflow, never on the schedule; the scheduled job never on push")
            check(on["workflow_dispatch"]["inputs"]["script"]["options"][-1] == "tests: run the test cases"
                  and test_job["steps"][-1 - 0]["env"].get("ANTHROPIC_API_KEY") == "${{ secrets.ANTHROPIC_API_KEY }}",
                  "Run workflow offers the tests too, and they get the model keys")
            check("## Test cases" in setup and "never run on the schedule" in setup, "SETUP.md says when they run and what they cost")

            await pg.click("#io-export")
            await pg.fill("#io-paste", json.dumps({"format": "reflection-blocks", "version": 1, "name": "sched", "program": sched}))
            await pg.click("#io-load-paste")  # a block file with no test cases clears them, as it does for a person
            await pg.wait_for_timeout(300)
            await pg.click("#io-export")
            files = await pg.evaluate("window.__actionsFiles()")
            _, data, on = workflow(files)
            check("push" not in on and "test" not in data["jobs"] and "if" not in data["jobs"]["run"],
                  "a program without test cases gets the workflow as before")
            await pg.click("#io-export")
            await pg.fill("#io-name", "my-program")
            files = await pg.evaluate("window.__actionsFiles()")
            await pg.click("#io-gha-save")
            msg = await pg.text_content("#io-export-msg")
            saved = await pg.evaluate("window.__saved")
            check(saved[-1:] == ["my-program-actions.zip"] and "SETUP.md" in msg, f"Save as GitHub Actions saves a zip, and says what to do next ({msg})")
            await pg.click("#io-export")
            check(not errors, "no page errors" + (f": {errors[:2]}" if errors else ""))
            # A scheduled script with a model call in it, for the failure-notice and heartbeat runs below (#433):
            # run without a key, the call raises.
            await load_state(pg, program(every(1, "m", blk("rb_say", None, {"TEXT": {"block": blk("rb_chat", inputs={"TEXT": tx("hi")})}}))))
            await pg.click("#io-export")
            await pg.fill("#io-name", "notices")
            nfiles = await pg.evaluate("window.__actionsFiles()")
            check(any(f["name"] == "notices.py" for f in nfiles), "the notices program exports for the terminal runs")
            # A scheduled *ask me*, once waiting on Telegram (#434) and once with a 0-minute limit and a default.
            await load_state(pg, program(
                every(1, "m", blk("rb_ask_me", None, {"TEXT": tx("What to bake?")}, nxt=add({"block": blk("rb_answer")}))),
                every(2, "m", blk("rb_ask_me", {"MINS": 0, "DEFAULT": "bread"}, {"TEXT": tx("What to bake?")}, nxt=add({"block": blk("rb_answer")})))))
            await pg.click("#io-export")
            await pg.fill("#io-name", "asks")
            afiles = await pg.evaluate("window.__exportFiles()")  # Actions export refuses scheduled scripts that ask; plain Python export doesn't
            check(any(f["name"].endswith(".py") for f in afiles), "the asks program exports for the terminal runs")
            # A program that sends five Telegram messages and then reads the clock, for the allowance runs below (#432).
            astart = script(*[blk("rb_tg_send", None, {"TEXT": tx(f"allowance msg {i}")}) for i in range(5)],
                             add({"block": blk("rb_now", {"PART": "datetime"})}))["blocks"]["blocks"][0]
            await load_state(pg, program(astart))
            await pg.click("#io-export")
            await pg.fill("#io-name", "allowance")
            alfiles = await pg.evaluate("window.__exportFiles()")
            alcode = next(f["text"] for f in alfiles if f["name"] == "allowance.py")
            check("telegram_send" in alcode, "the allowance program exports for the terminal runs")
            # A program with one Telegram send, for the --report/--status runs below (#435).
            await load_state(pg, program(script(blk("rb_tg_send", None, {"TEXT": tx("report msg")}))["blocks"]["blocks"][0]))
            await pg.click("#io-export")
            await pg.fill("#io-name", "reporter")
            rfiles = await pg.evaluate("window.__exportFiles()")
            rcode = next(f["text"] for f in rfiles if f["name"] == "reporter.py")
            check("telegram_send" in rcode, "the reporter program exports for the terminal runs")
            await ctx.close()
        await browser.close()

    # The program, run as the workflow runs it.
    code = next(f["text"] for f in files if f["name"] == "my-program.py")
    env = dict(os.environ, PYTHONPATH=str(HERE / "fakeapi"), PYTHONIOENCODING="utf-8", ANTHROPIC_API_KEY="test", TZ="UTC", RB_LANGUAGE="en")
    with tempfile.TemporaryDirectory() as tmp:
        (pathlib.Path(tmp) / "my-program.py").write_text(code, encoding="utf-8")
        run = lambda *a: drive([sys.executable, "-u", "my-program.py", *a], env, tmp)  # noqa: E731
        rc, out, err = run("--run-schedule", "1", "--now")
        check(rc == 0 and "the scheduled script ran" in out and "started by hand" not in out,
              f"--run-schedule 1 --now runs that scheduled script once (exit {rc}): {(err or out)[-300:]!r}")
        rc, out, err = run("--run-schedule", "1")
        check(rc == 0 and f"Not time for scheduled script 1 ({hour:02d}:15, every day), so nothing was run." in out
              and "the scheduled script ran" not in out, f"at another time it does nothing, and says so: {out[-300:]!r}")
        rc, out, err = run("--run-schedule", "2")
        check(rc == 0 and "every half hour" in out, f"an 'every' script runs whenever it's started ({(err or out)[-200:]!r})")
        rc, out, err = run("--run-schedule", "9")
        check(rc == 1 and "There's no scheduled script 9: this program has 2." in err, f"a number it doesn't have is an error ({err[-200:]!r})")

    # Scheduled-run notices (#433): a failing scheduled run sends one message on the stand-in Telegram, and every
    # finished scheduled run fetches the stand-in heartbeat URL.
    base, svc_log, _tg_add, _imap_port, _smtp_port = fake_services.start()
    ncode = next(f["text"] for f in nfiles if f["name"] == "notices.py")
    with tempfile.TemporaryDirectory() as tmp:
        (pathlib.Path(tmp) / "notices.py").write_text(ncode, encoding="utf-8")
        no_keys = {k: v for k, v in os.environ.items() if not k.endswith(("_API_KEY", "_TOKEN")) and not k.startswith("RB_")}
        nenv = dict(no_keys, PYTHONIOENCODING="utf-8", RB_LANGUAGE="en", RB_APPROVE="no",
                    TELEGRAM_BOT_TOKEN=fake_services.TG_TOKEN, TELEGRAM_CHAT_ID=str(fake_services.TG_CHAT), TELEGRAM_API_URL=base + "/tg",
                    RB_NOTIFY_ON_FAILURE="telegram", RB_HEARTBEAT_URL=base + "/heartbeat")
        rc, out, err = drive([sys.executable, "-u", "notices.py", "--run-schedule", "1", "--now"], nenv, tmp)
        check(rc == 1 and "Run stopped" in (out + err) and len(svc_log["tg_sent"]) == 1 and "needs a key" in svc_log["tg_sent"][0]["text"]
              and svc_log["heartbeats"] == ["/heartbeat"],
              f"a scheduled run that raises sends one Telegram message with the reason, and still fetches the heartbeat "
              f"(exit {rc}; tg={svc_log['tg_sent']}; hb={svc_log['heartbeats']}; {(err or out)[-200:]!r})")
        env_ok = dict(nenv, ANTHROPIC_API_KEY="test", PYTHONPATH=str(HERE / "fakeapi"))
        rc, out, err = drive([sys.executable, "-u", "notices.py", "--run-schedule", "1", "--now"], env_ok, tmp)
        check(rc == 0 and len(svc_log["tg_sent"]) == 1 and svc_log["heartbeats"] == ["/heartbeat", "/heartbeat"],
              f"a scheduled run that finishes fetches the heartbeat and sends no message (exit {rc}; tg={len(svc_log['tg_sent'])}; "
              f"hb={svc_log['heartbeats']}; {(err or out)[-200:]!r})")
        # a heartbeat that can't be reached is only a note, never an error
        rc, out, err = drive([sys.executable, "-u", "notices.py", "--run-schedule", "1", "--now"],
                             dict(env_ok, RB_HEARTBEAT_URL="http://127.0.0.1:9/dead"), tmp)
        check(rc == 0 and "only a note" in (out + err), f"a heartbeat that fails is a note, not an error (exit {rc}; {(err or out)[-160:]!r})")

    # The You blocks on the approve_by channel when nobody's at the keyboard (#434): a scheduled *ask me*
    # answered on the stand-in Telegram, and one whose time limit ran out taking the block's default.
    acode = next(f["text"] for f in afiles if f["name"].endswith(".py"))
    check('R.ask_me("What to bake?", mins=5, default="")' in acode and 'mins=0, default="bread"' in acode,
          "the You blocks export their time limit and default answer")
    with tempfile.TemporaryDirectory() as tmp:
        (pathlib.Path(tmp) / "asks.py").write_text(acode, encoding="utf-8")
        aenv = dict(no_keys, PYTHONIOENCODING="utf-8", RB_LANGUAGE="en", RB_APPROVE="no", RB_APPROVE_BY="telegram",
                    TELEGRAM_BOT_TOKEN=fake_services.TG_TOKEN, TELEGRAM_CHAT_ID=str(fake_services.TG_CHAT), TELEGRAM_API_URL=base + "/tg")
        import threading
        threading.Timer(2.0, lambda: _tg_add("rye flour")).start()  # a reply to the question, while the run waits
        rc, out, err = drive([sys.executable, "-u", "asks.py", "--run-schedule", "1", "--now"], aenv, tmp)
        check(rc == 0 and "rye flour" in out and any("What to bake?" in m.get("text", "") for m in svc_log["tg_sent"]),
              f"a scheduled ask-me is answered on Telegram (exit {rc}; tg={svc_log['tg_sent']}; {(err or out)[-250:]!r})")
        rc, out, err = drive([sys.executable, "-u", "asks.py", "--run-schedule", "2", "--now"], aenv, tmp)
        check(rc == 0 and "bread" in out and "No answer within 0 min" in out,
              f"the time limit running out takes the block's default (exit {rc}): {(err or out)[-250:]!r}")

    # Action allowances (#432): with allow_messages_daily = 3, a program that sends five messages sends three, says the
    # allowance is reached once, and carries on reading; the next run on the same computer is stopped at once.
    with tempfile.TemporaryDirectory() as tmp:
        (pathlib.Path(tmp) / "allowance.py").write_text(alcode, encoding="utf-8")
        lenv = dict(no_keys, PYTHONIOENCODING="utf-8", RB_LANGUAGE="en", RB_APPROVE="no",
                    TELEGRAM_BOT_TOKEN=fake_services.TG_TOKEN, TELEGRAM_CHAT_ID=str(fake_services.TG_CHAT), TELEGRAM_API_URL=base + "/tg",
                    RB_ALLOW_MESSAGES_DAILY="3")
        sent = lambda: [m for m in svc_log["tg_sent"] if "allowance msg" in m["text"]]  # noqa: E731
        rc, out, err = drive([sys.executable, "-u", "allowance.py"], lenv, tmp)
        check(rc == 0 and len(sent()) == 3 and out.count("Allowance reached") == 1 and "Added to result" in out,
              f"a program that sends five messages stops at the allowance of 3, says so once, and carries on reading "
              f"(exit {rc}; tg={len(sent())}; {(err or out)[-300:]!r})")
        rc, out, err = drive([sys.executable, "-u", "allowance.py"], lenv, tmp)
        check(rc == 0 and len(sent()) == 3 and out.count("Allowance reached") == 1 and "Added to result" in out,
              f"the next run on the same computer sends nothing and is stopped at once (exit {rc}; tg={len(sent())}; {(err or out)[-300:]!r})")
    # --report and --status (#435): the weekly account read from the saved log, the receipt and the spending record.
    with tempfile.TemporaryDirectory() as tmp:
        (pathlib.Path(tmp) / "reporter.py").write_text(rcode, encoding="utf-8")
        renv = dict(no_keys, PYTHONIOENCODING="utf-8", RB_LANGUAGE="en", RB_APPROVE="no", RB_SAVE_LOG="yes",
                    TELEGRAM_BOT_TOKEN=fake_services.TG_TOKEN, TELEGRAM_CHAT_ID=str(fake_services.TG_CHAT), TELEGRAM_API_URL=base + "/tg")
        rc, out, err = drive([sys.executable, "-u", "reporter.py"], renv, tmp)
        check(rc == 0 and "Log saved to" in out, f"a run with save_log = yes saves a log (exit {rc}; {(err or out)[-200:]!r})")
        rc, out, err = drive([sys.executable, "-u", "reporter.py", "--report"], renv, tmp)
        check(rc == 0 and "Report for reporter, last 7 days:" in out and "Runs: 1 saved logs" in out
              and "1 without a review" in out and "Actions done, from the receipts of the last 7 days: 1." in out
              and "The chain is intact" in out,
              f"--report reads the log, the receipt and the spending record (exit {rc}): {(err or out)[-400:]!r})")
        rc, out, err = drive([sys.executable, "-u", "reporter.py", "--status"], renv, tmp)
        check(rc == 0 and len(out.strip().splitlines()) == 1 and out.startswith("reporter: 1 runs")
              and "1 actions done" in out and "0 refused" in out,
              f"--status says the same in one line (exit {rc}): {out!r})")


async def paste_gallery(pg, name):
    await pg.click("#io-export")
    await paste(pg, (ROOT / "gallery" / f"{name}.json").read_text(encoding="utf-8"))
    await pg.click("#io-load-paste")
    await pg.click("#io-export")
