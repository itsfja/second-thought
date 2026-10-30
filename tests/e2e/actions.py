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
            await pg.click("#io-toggle")
            await pg.click("#io-gha-save")
            msg = await pg.text_content("#io-export-msg")
            check("can't run on GitHub Actions: it asks you questions" in msg, f"the page says why, instead of saving ({msg})")
            await pg.click("#io-toggle")

            await load_state(pg, sched)
            await pg.click("#io-toggle")
            await pg.fill("#io-name", "my-program")
            files = await pg.evaluate("window.__actionsFiles()")
            await pg.click("#io-gha-save")
            msg = await pg.text_content("#io-export-msg")
            saved = await pg.evaluate("window.__saved")
            check(saved[-1:] == ["my-program-actions.zip"] and "SETUP.md" in msg, f"Save as GitHub Actions saves a zip, and says what to do next ({msg})")
            await pg.click("#io-toggle")
            check(not errors, "no page errors" + (f": {errors[:2]}" if errors else ""))
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


async def paste_gallery(pg, name):
    await pg.click("#io-toggle")
    await paste(pg, (ROOT / "gallery" / f"{name}.json").read_text(encoding="utf-8"))
    await pg.click("#io-load-paste")
    await pg.click("#io-toggle")
