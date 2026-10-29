"""End-to-end tests of exported Python: every example run as a program, --doctor, approvals, connections."""
from e2e.common import *  # noqa: F401,F403


PROMPTS = ("Approve? [y/n] > ", "Number > ", "Path > ", "Press Enter to continue > ", "> ")


def drive(cmd, env, cwd, timeout=120, approve="y"):
    """Run an exported program, answering whatever it asks in the terminal (approve: the answer to every Approve? [y/n])."""
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=cwd)
    os.set_blocking(proc.stdout.fileno(), False)
    out, deadline, buf = [], time.time() + timeout, ""
    while proc.poll() is None and time.time() < deadline:
        try:
            chunk = proc.stdout.read()
        except BlockingIOError:
            chunk = None
        if chunk:
            text = chunk.decode("utf-8", "replace")
            out.append(text)
            buf = (buf + text)[-2000:]
            prompt = next((p for p in PROMPTS if buf.endswith(p)), None)
            if prompt:
                if prompt == "Path > ":
                    reply = str(FIX / ("crumb.png" if buf.rfind("Choose a picture") > buf.rfind("Choose a file") else "notes.txt"))
                else:
                    reply = {"Approve? [y/n] > ": approve, "Number > ": "1", "Press Enter to continue > ": ""}.get(prompt, "rye bread for beginners")
                proc.stdin.write((reply + "\n").encode())
                proc.stdin.flush()
                buf = ""
        else:
            time.sleep(0.02)
    if proc.poll() is None:
        proc.kill()
    rest = proc.stdout.read() if proc.stdout else b""
    out.append((rest or b"").decode("utf-8", "replace"))
    return proc.wait(), "".join(out), proc.stderr.read().decode("utf-8", "replace")


def doctor_tests(codes, env, tmp, llama_url, llama_calls, ha_calls):
    """--doctor checks what a program uses, reading only, and says what to fix."""
    print("--doctor")
    base = llama_url.rsplit("/v1", 1)[0]
    env = dict(env, ANTHROPIC_BASE_URL=base, GEMINI_BASE_URL=base)
    prog = pathlib.Path(tmp) / "doc_doorbell.py"
    prog.write_text(codes["ha_doorbell"][0], encoding="utf-8")
    before = len(ha_calls)
    r = subprocess.run([sys.executable, "-u", str(prog), "--doctor"], env=env, cwd=tmp, capture_output=True, encoding="utf-8", errors="replace", timeout=120)
    out = r.stdout
    check(r.returncode == 0 and "Only reading: nothing is sent" in out and "  ok    Claude: the key works (" in out
          and "  ok    Home Assistant: reached Home Assistant" in out and "  ok    First run: approve = no" in out
          and "Everything checked is ready." in out and len(ha_calls) == before and "Gemini" not in out,
          f"--doctor checks a Home Assistant program's key and connection, switching nothing (exit {r.returncode}): {out[-400:]!r}")
    r = subprocess.run([sys.executable, "-u", str(prog), "--doctor"], env=dict(env, ANTHROPIC_API_KEY="bad", HA_TOKEN="wrong"),
                       cwd=tmp, capture_output=True, encoding="utf-8", errors="replace", timeout=120)
    check(r.returncode == 1 and "  FAIL  Claude: refused the key (401). Check ANTHROPIC_API_KEY" in r.stdout
          and "  FAIL  Home Assistant:" in r.stdout and "2 problems to fix" in r.stdout,
          f"a refused key and a wrong Home Assistant token are each a FAIL, and the exit code says so ({r.stdout[-300:]!r})")
    chain = {k: v for k, v in env.items() if k != "ANTHROPIC_API_KEY"}
    chain["PYTHONPATH"] = os.pathsep.join([env["PYTHONPATH"], str(HERE / "fakekeyring")])
    r = subprocess.run([sys.executable, "-u", str(prog), "--doctor"], env=dict(chain, FAKE_KEYCHAIN='{"ANTHROPIC_API_KEY": "test"}'),
                       cwd=tmp, capture_output=True, encoding="utf-8", errors="replace", timeout=120)
    check(r.returncode == 0 and "  ok    Keys: ANTHROPIC_API_KEY (the keychain), " in r.stdout and "HA_TOKEN (the environment)" in r.stdout
          and "  ok    Claude: the key works (" in r.stdout,
          f"with keyring installed, a key missing from the environment and settings comes from the keychain, and --doctor says where each key came from ({r.stdout[-400:]!r})")
    r = subprocess.run([sys.executable, "-u", str(prog), "--doctor"], env=dict(chain, FAKE_KEYCHAIN="broken"),
                       cwd=tmp, capture_output=True, encoding="utf-8", errors="replace", timeout=120)
    check(r.returncode == 1 and "  NOTE  Keychain: keyring is installed but the keychain couldn't be read (NoKeyringError" in r.stdout
          and "  FAIL  Claude: no key." in r.stdout, f"a keychain that can't be read is a note, not a crash ({r.stdout[-400:]!r})")
    llama = pathlib.Path(tmp) / "doc_llama.py"
    llama.write_text(codes["w_llama"][0], encoding="utf-8")
    r = subprocess.run([sys.executable, "-u", str(llama), "--doctor"], env=dict(env, RB_MODEL_TIER="llama-complex", RB_BACKUPS="none"),
                       cwd=tmp, capture_output=True, encoding="utf-8", errors="replace", timeout=120)
    check(r.returncode == 0 and "  NOTE  Llama: the key works, but it doesn't list llama4:16x17b" in r.stdout and "ollama pull llama4:16x17b" in r.stdout,
          f"--doctor notices a Llama model that hasn't been pulled ({r.stdout[-300:]!r})")
    r = subprocess.run([sys.executable, "-u", str(prog), "--doctor"], env=dict(env, MODEL_DEFAULT="claude-sonnet-5"),
                       cwd=tmp, capture_output=True, encoding="utf-8", errors="replace", timeout=120)
    check(r.returncode == 0 and "  NOTE  Claude: the key works, but it doesn't list claude-sonnet-5, which this program uses. It may have been retired."
          in r.stdout and "such as MODEL_DEFAULT = claude-sonnet-5-5." in r.stdout,
          f"--doctor says a model may have been retired, and names the setting and a model the service lists ({r.stdout[-400:]!r})")
    mcp = pathlib.Path(tmp) / "doc_mcp.py"
    mcp.write_text(EXTRA["t_ag_mcp"], encoding="utf-8")
    log = pathlib.Path(tmp) / "doc-mcp.log"
    r = subprocess.run([sys.executable, "-u", str(mcp), "--doctor"], env=dict(env, FAKE_MCP_LOG=str(log),
                       MCP_BAKERY=f'"{sys.executable}" "{HERE / "fake_mcp.py"}" legacy'), cwd=tmp, capture_output=True, encoding="utf-8", errors="replace", timeout=120)
    sent = [json.loads(x).get("method") for x in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []
    check(r.returncode == 0 and "  ok    MCP server \u201cbakery\u201d: 4 tools, MCP 2025-11-25" in r.stdout and "tools/list" in sent and "tools/call" not in sent,
          f"--doctor lists an MCP server's tools without calling any ({r.stdout[-300:]!r})")
    old = pathlib.Path(tmp) / "doc_old.py"
    old.write_text(codes["review"][0].replace(", can=CAN)", ")"), encoding="utf-8")
    r = subprocess.run([sys.executable, "-u", str(old), "--doctor"], env=env, cwd=tmp, capture_output=True, encoding="utf-8", errors="replace", timeout=120)
    check(r.returncode in (0, 1) and "  ok    Claude: the key works" in r.stdout and "Traceback" not in r.stderr,
          f"--doctor also checks a program exported before CAN: whatever is set up ({(r.stderr or r.stdout)[-300:]!r})")
    # Every community gallery program: --doctor runs to its summary, once with the test services and once with no keys at all.
    gallery = sorted(k for k in codes if k.startswith("g_"))
    check(len(gallery) == len(list((ROOT / "gallery").glob("*.json"))), f"every gallery program was exported ({len(gallery)})")
    no_keys = {k: v for k, v in env.items() if not (k.endswith(("_API_KEY", "_TOKEN", "_SECRET", "_PASSWORD")) or k == "HF_TOKEN")}
    for key in gallery:
        prog = pathlib.Path(tmp) / f"doc_{key}.py"
        prog.write_text(codes[key][0], encoding="utf-8")
        for label, run_env, want in (("set up", env, (0, 1)), ("with no keys", no_keys, (1,))):
            r = subprocess.run([sys.executable, "-u", str(prog), "--doctor"], env=run_env, cwd=tmp, capture_output=True,
                               encoding="utf-8", errors="replace", timeout=120)
            summary = "Everything checked is ready." in r.stdout or "to fix: the line" in r.stdout
            check(r.returncode in want and summary and "Only reading: nothing is sent" in r.stdout and "Traceback" not in r.stderr
                  and (label == "set up" or "  FAIL  Claude: no key." in r.stdout),
                  f"--doctor checks gallery program {key[2:]} {label}, and says what to fix (exit {r.returncode}): {(r.stderr or r.stdout)[-300:]!r}")


def approval_tests(codes, env, tmp):
    """A program that can act lists what it can do and asks once before its first run; one that only reads doesn't."""
    print("Asking before the first run")
    prog = pathlib.Path(tmp) / "gate_bedtime.py"
    prog.write_text(codes["a_bedtime"][0], encoding="utf-8")
    approved = pathlib.Path(tmp) / ".gate_bedtime.approved"
    code_, out, err = drive([sys.executable, "-u", str(prog)], env, tmp)
    check(code_ == 0 and "This program can:\n  - control your Home Assistant devices\n  - look at your Home Assistant devices" in out.replace("\r\n", "\n")
          and "It sends what it reads and writes to Claude." in out and approved.exists(),
          "a program that can control devices lists what it can do, asks before its first run, and remembers the yes"
          + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
    code_, out, err = drive([sys.executable, "-u", str(prog)], env, tmp)
    check(code_ == 0 and "This program can:" not in out, "the next run doesn't ask again")
    prog.write_text(codes["a_bedtime"][0] + "\n# edited\n", encoding="utf-8")
    r = subprocess.run([sys.executable, "-u", str(prog), "--schedule"], env=env, cwd=tmp, capture_output=True, encoding="utf-8", errors="replace", timeout=60,
                       stdin=subprocess.DEVNULL)
    check(r.returncode == 1 and "nobody is here to ask" in r.stdout and "approve = no" in r.stdout,
          f"once the file changes, a scheduled run with nobody there stops and says how to allow it (exit {r.returncode})")
    r = subprocess.run([sys.executable, "-u", str(prog)], env=env, cwd=tmp, capture_output=True, encoding="utf-8", errors="replace", timeout=60, input="n\n")
    check(r.returncode == 1 and "Not allowed, so it didn't run." in r.stdout and "RESULT" not in r.stdout, "answering n stops it before it does anything")
    reader = pathlib.Path(tmp) / "gate_reader.py"
    reader.write_text(codes["a_house"][0], encoding="utf-8")
    code_, out, err = drive([sys.executable, "-u", str(reader)], env, tmp)
    check(code_ == 0 and "This program can:" not in out and not (pathlib.Path(tmp) / ".gate_reader.approved").exists(),
          "a program that only looks at things runs without asking")


def python_tests(codes):
    print("Exported Python runs")
    ha_url, ha_calls = fake_ha.start()
    llama_url, llama_calls = fake_llama.start()
    # RB_APPROVE=no: these programs are run unattended many times over; approval_tests() checks the first-run question.
    env = dict(os.environ, RB_APPROVE="no", PYTHONPATH=str(HERE / "fakeapi"), PYTHONIOENCODING="utf-8", ANTHROPIC_API_KEY="test", GEMINI_API_KEY="test",
               HA_URL=ha_url, HA_TOKEN=fake_ha.TOKEN, LLAMA_BASE_URL=llama_url,
               DEEPSEEK_BASE_URL=llama_url, DEEPSEEK_API_KEY="test",
               XAI_BASE_URL=llama_url, XAI_API_KEY="test",
               OPENAI_BASE_URL=llama_url, OPENAI_API_KEY="test",
               MISTRAL_BASE_URL=llama_url, MISTRAL_API_KEY="test", QWEN_BASE_URL=llama_url, DASHSCOPE_API_KEY="test",
               MOONSHOT_BASE_URL=llama_url, MOONSHOT_API_KEY="test",
               PERPLEXITY_BASE_URL=llama_url.rsplit("/v1", 1)[0], PERPLEXITY_API_KEY="test",
               HF_BASE_URL=llama_url, HF_TOKEN="test", GROQ_BASE_URL=llama_url, GROQ_API_KEY="test",
               ZAI_BASE_URL=llama_url, ZAI_API_KEY="test", MINIMAX_BASE_URL=llama_url, MINIMAX_API_KEY="test",
               OPENROUTER_BASE_URL=llama_url, OPENROUTER_API_KEY="test")
    svc_url, svc_log, tg_add, imap_port, smtp_port = fake_services.start()
    broker, mqtt_port = fake_mqtt.start(retained={"zigbee2mqtt/leak_sensor_sink": '{"water_leak": false, "battery": 87}', "zigbee2mqtt/oven_plug": '{"state": "ON", "power": 41}'})
    env.update(HOMEY_URL=svc_url + "/homey", HOMEY_API_KEY=fake_services.HOMEY_KEY)
    env.update(MQTT_HOST="127.0.0.1", MQTT_PORT=str(mqtt_port), MQTT_USERNAME=fake_mqtt.USER, MQTT_PASSWORD=fake_mqtt.PASSWORD)
    env.update(DISCORD_API_URL=svc_url + "/discord", DISCORD_BOT_TOKEN=fake_services.DISCORD_TOKEN, DISCORD_CHANNEL_ID=fake_services.DISCORD_CHANNEL,
               SLACK_API_URL=svc_url + "/slack", SLACK_BOT_TOKEN=fake_services.SLACK_TOKEN, SLACK_CHANNEL_ID=fake_services.SLACK_CHANNEL)
    env.update(RB_FEEDS=f"{svc_url}/feeds/baking.rss {svc_url}/feeds/tech.atom", GITHUB_API_URL=svc_url + "/gh", GITHUB_TOKEN=fake_services.GH_TOKEN,
               TELEGRAM_API_URL=svc_url + "/tg", TELEGRAM_BOT_TOKEN=fake_services.TG_TOKEN, TELEGRAM_CHAT_ID=str(fake_services.TG_CHAT),
               EMAIL_ADDRESS=fake_services.MAIL_USER, EMAIL_PASSWORD=fake_services.MAIL_PASS, EMAIL_IMAP_HOST="127.0.0.1", EMAIL_SMTP_HOST="127.0.0.1",
               EMAIL_IMAP_PORT=str(imap_port), EMAIL_SMTP_PORT=str(smtp_port), EMAIL_SSL="no", CALENDAR_URL=svc_url + "/calendar.ics")
    with tempfile.TemporaryDirectory() as tmp:
        approval_tests(codes, {k: v for k, v in env.items() if k != "RB_APPROVE"}, tmp)
        doctor_tests(codes, env, tmp, llama_url, llama_calls, ha_calls)
        mcp_serve_tests(codes, env, tmp)
        for ex, (code, _) in codes.items():
            path = pathlib.Path(tmp) / f"{ex}.py"
            path.write_text(code, encoding="utf-8")
            code_, stdout, stderr = drive([sys.executable, "-u", str(path)], env, tmp)
            r = SimpleNamespace(returncode=code_, stdout=stdout, stderr=stderr)
            ok = r.returncode == 0 and ("RESULT" in r.stdout or "Done" in r.stdout)
            check(ok, f"{ex}.py" + ("" if ok else f" (exit {r.returncode}): {(r.stderr or r.stdout)[-300:]}"))
            if ex in ("w_llama", "w_judges", "ha_private"):
                done = [l for l in r.stdout.splitlines() if l.startswith("Done")]
                used = bool(done) and "Llama:" in done[-1]
                check(used, f"{ex}.py used Llama" + ("" if used else f": {done[-1] if done else r.stdout[-200:]}"))
                if ex == "w_judges":
                    check(used and all(w in done[-1] for w in ("Claude:", "Gemini:", "DeepSeek:", "xAI:", "OpenAI:")), "w_judges.py asked Claude, Gemini, Llama, DeepSeek, Grok and OpenAI")
            if ex == "w_gptcheck":
                done = [l for l in r.stdout.splitlines() if l.startswith("Done")]
                gpt = [c for c in llama_calls if str(c["model"]).startswith("gpt-")]
                check(bool(done) and "OpenAI:" in done[-1] and "Claude:" in done[-1] and gpt,
                      "w_gptcheck.py asked Claude and OpenAI (and OpenAI accepted the request)" + ("" if done else f": {r.stdout[-200:]}"))
            if ex == "w_worldpanel":
                done = [l for l in r.stdout.splitlines() if l.startswith("Done")]
                ok3 = bool(done) and all(w in done[-1] for w in ("Mistral:", "Qwen:", "Kimi:", "GLM:", "MiniMax:", "Claude:"))
                check(ok3, "w_worldpanel.py asked Mistral, Qwen, Kimi, GLM, MiniMax and Claude" + ("" if ok3 else f": {done[-1] if done else r.stdout[-200:]}"))
            if ex == "w_worldpanel":
                check("<think>" not in r.stdout and "private reasoning" not in r.stdout, "w_worldpanel.py hid MiniMax's thinking")
            if ex == "w_groqstorm":
                done = [l for l in r.stdout.splitlines() if l.startswith("Done")]
                check(bool(done) and "Groq:" in done[-1], "w_groqstorm.py asked Groq" + ("" if done else f": {r.stdout[-200:]}"))
            if ex == "c_openonly":
                done = [l for l in r.stdout.splitlines() if l.startswith("Done")]
                only = bool(done) and "Hugging Face:" in done[-1] and "Claude:" not in done[-1]
                check(only, "c_openonly.py used only Hugging Face" + ("" if only else f": {done[-1] if done else r.stdout[-200:]}"))
            if ex == "r_anymodel":
                done = [l for l in r.stdout.splitlines() if l.startswith("Done")]
                models = {c["model"] for c in llama_calls}
                anym = bool(done) and "OpenRouter:" in done[-1] and {"openrouter/auto", "meta-llama/llama-3.3-70b-instruct"} <= models
                check(anym, "r_anymodel.py asked OpenRouter's auto-pick and the named model" + ("" if anym else f": {done[-1] if done else r.stdout[-200:]}"))
            if ex == "r_sourced":
                done = [l for l in r.stdout.splitlines() if l.startswith("Done")]
                srcd = bool(done) and "Perplexity:" in done[-1] and "Sources:" in r.stdout and "https://example.com/test" in r.stdout
                check(srcd, "r_sourced.py asked Perplexity and showed its sources" + ("" if srcd else f": {r.stdout[-300:]}"))
            if ex == "r_second":
                done = [l for l in r.stdout.splitlines() if l.startswith("Done")]
                check(bool(done) and "DeepSeek:" in done[-1] and "Claude:" in done[-1], "r_second.py asked Claude and DeepSeek")
            if ex == "a_bake":
                check("▸ Agent step 1/8: ask_me" in r.stdout and "▸ Agent: finished in 2 steps" in r.stdout and "▸ Agent plan" in r.stdout,
                      "a_bake.py runs the agent loop, planning first")
            if ex == "a_tool":
                out_ = r.stdout.replace("\r\n", "\n")
                check("▸ Agent step 1/6: hydration" in out_ and "    Result:\n    170\n" in out_, "a_tool.py calls the My Block as a tool and gets 170 back")
            if ex == "gemini":
                done = [l for l in r.stdout.splitlines() if l.startswith("Done")]
                both = bool(done) and "Gemini:" in done[-1] and "Claude:" in done[-1]
                check(both, "gemini.py used both Claude and Gemini" + ("" if both else f": {done[-1] if done else r.stdout[-200:]}"))
    print("Settings file")
    import configparser
    cp = configparser.ConfigParser(interpolation=None, inline_comment_prefixes=(";", "#"))
    cp.read_string(EXPORTS["w_judges"]["second-thought.ini"])
    check(cp.has_section("keys") and cp.has_option("keys", "OPENAI_API_KEY"), "the exported ini is a valid settings file")
    with tempfile.TemporaryDirectory() as tmp:
        folder = pathlib.Path(tmp) / "My Programs" / "judges"  # a folder name with a space, like Windows ones
        folder.mkdir(parents=True)
        for name, text in EXPORTS["w_judges"].items():
            (folder / name).write_bytes(text.encode("utf-8"))
        ini = folder / "second-thought.ini"
        filled = ini.read_text(encoding="utf-8")
        for k in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "DEEPSEEK_API_KEY", "XAI_API_KEY", "OPENAI_API_KEY"):
            filled = filled.replace(k + " = ", k + " = test")
        filled = filled.replace("LLAMA_BASE_URL = http://localhost:11434/v1", "LLAMA_BASE_URL = " + llama_url)
        ini.write_bytes(("\ufeff" + filled).encode("utf-8"))  # with the marker Notepad sometimes adds
        bare = {k: v for k, v in env.items() if not k.endswith(("_API_KEY", "_TOKEN")) and k != "LLAMA_BASE_URL"}
        bare.update(DEEPSEEK_BASE_URL=llama_url, XAI_BASE_URL=llama_url, OPENAI_BASE_URL=llama_url, HA_TOKEN="")
        elsewhere = pathlib.Path(tmp)  # run from another folder: the ini is found next to the program, not here
        code_, out, err = drive([sys.executable, "-u", str(folder / "w_judges.py")], bare, elsewhere)
        done = [l for l in out.splitlines() if l.startswith("Done")]
        ok = code_ == 0 and bool(done) and all(w in done[-1] for w in ("Claude:", "Gemini:", "Llama:", "DeepSeek:", "xAI:", "OpenAI:"))
        check(ok, "with the keys only in second-thought.ini, every model is reached" + ("" if ok else f": {(done[-1] if done else (err or out)[-300:])}"))
        ini.write_text(filled.replace("OPENAI_API_KEY = test", "OPENAI_API_KEY = "), encoding="utf-8")
        code_, out, err = drive([sys.executable, "-u", str(folder / "w_judges.py")], bare, elsewhere)
        check(code_ != 0 and "OPENAI_API_KEY = your-key in " in (out + err) and "second-thought.ini" in (out + err),
              "a missing key says exactly which line to fill in, and in which file")
        ini.write_text("[keys\nbroken", encoding="utf-8")
        code_, out, err = drive([sys.executable, "-u", str(folder / "w_judges.py")], bare, elsewhere)
        check(code_ != 0 and "mistake in" in (out + err), "a broken ini file gets a clear message")

    if os.name != "nt" and shutil.which("sh"):
        print("Linux scripts")
        with tempfile.TemporaryDirectory() as tmp:
            folder = pathlib.Path(tmp) / "My Programs" / "ha morning"
            folder.mkdir(parents=True)
            for name, text in EXPORTS["review"].items():
                (folder / name).write_bytes(text.encode("utf-8"))
            ini = folder / "second-thought.ini"
            ini.write_text(ini.read_text().replace("ANTHROPIC_API_KEY = ", "ANTHROPIC_API_KEY = test"))
            bare = {k: v for k, v in env.items() if not k.endswith(("_API_KEY", "_TOKEN"))}
            code_, out, err = drive(["sh", str(folder / "run.sh")], bare, tmp, timeout=300)
            done = [l for l in out.splitlines() if l.startswith("Done")]
            check(code_ == 0 and bool(done) and (folder / ".venv" / "bin" / "python").exists(),
                  "sh run.sh sets up its own Python folder, installs, and runs the program" + ("" if done else f": {(err or out)[-400:]}"))
            code_, out, err = drive(["sh", str(folder / "run.sh")], bare, tmp, timeout=120)
            check(code_ == 0 and "First run" not in out, "the second run skips the setup")
            for name, text in EXPORTS["ha_morning"].items():
                (folder / name).write_bytes(text.encode("utf-8"))
            fake = pathlib.Path(tmp) / "fakebin"
            fake.mkdir()
            (fake / "sudo").write_text('#!/bin/sh\nif [ "$1" = install ]; then cp "$4" "$FAKE_UNIT"; else echo "$*" >> "$FAKE_LOG"; fi\n')
            (fake / "systemctl").write_text("#!/bin/sh\nexit 0\n")
            for f in fake.iterdir():
                f.chmod(0o755)
            unit, log = pathlib.Path(tmp) / "unit.service", pathlib.Path(tmp) / "sudo.log"
            senv = dict(bare, PATH=str(fake) + os.pathsep + bare.get("PATH", ""), FAKE_UNIT=str(unit), FAKE_LOG=str(log))
            r = subprocess.run(["sh", str(folder / "install-service.sh")], env=senv, cwd=tmp, capture_output=True, text=True, timeout=60)
            u = unit.read_text() if unit.exists() else ""
            ok = (r.returncode == 0 and f"WorkingDirectory={folder}" in u and f'ExecStart=/bin/sh "{folder}/run-on-schedule.sh"' in u
                  and "User=" in u and "enable --now second-thought-ha_morning" in (log.read_text() if log.exists() else ""))
            check(ok, "install-service.sh writes a systemd service for this folder and turns it on" + ("" if ok else f": {r.stdout[-200:]} {r.stderr[-200:]} {u[:300]}"))
            # On a Mac it uses launchd instead, with no password
            (fake / "uname").write_text("#!/bin/sh\necho Darwin\n")
            (fake / "launchctl").write_text('#!/bin/sh\necho "$*" >> "$FAKE_LOG"\n')
            for f in fake.iterdir():
                f.chmod(0o755)
            home = pathlib.Path(tmp) / "home"
            home.mkdir()
            log.write_text("")
            r = subprocess.run(["sh", str(folder / "install-service.sh")], env=dict(senv, HOME=str(home)), cwd=tmp, capture_output=True, text=True, timeout=60)
            plists = list((home / "Library" / "LaunchAgents").glob("*.plist"))
            import plistlib
            pl = plistlib.loads(plists[0].read_bytes()) if plists else {}
            ok = (r.returncode == 0 and pl.get("ProgramArguments") == ["/bin/sh", f"{folder}/run-on-schedule.sh"]
                  and pl.get("WorkingDirectory") == str(folder) and pl.get("RunAtLoad") is True
                  and "bootstrap" in log.read_text() and "sudo" not in log.read_text())
            check(ok, "on a Mac, install-service.sh sets up a launchd agent instead" + ("" if ok else f": {r.stdout[-200:]} {r.stderr[-200:]} {pl}"))
    if os.name == "nt":
        print("Windows scripts")
        with tempfile.TemporaryDirectory() as tmp:
            folder = pathlib.Path(tmp) / "My Programs" / "ha morning"
            folder.mkdir(parents=True)
            for name, text in EXPORTS["ha_morning"].items():
                (folder / name).write_bytes(text.encode("utf-8"))
            appdata = pathlib.Path(tmp) / "AppData"
            r = subprocess.run(["cmd", "/c", str(folder / "install-startup.bat")], env=dict(os.environ, APPDATA=str(appdata)),
                               input="\n", capture_output=True, text=True, timeout=60)
            entries = list((appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup").glob("*.cmd"))
            text = entries[0].read_text() if entries else ""
            ok = r.returncode == 0 and f'""{folder}\\run-on-schedule.bat""' in text and "/min" in text
            check(ok, "install-startup.bat adds the program to the Startup folder" + ("" if ok else f": {r.stdout[-300:]} {r.stderr[-200:]} {text}"))

    print("Backup models in Python")
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "backup.py"
        path.write_text(codes["review"][0], encoding="utf-8")
        before = len(llama_calls)
        env2 = dict(env, RB_MODEL_TIER="openai-default", OPENAI_API_KEY="", RB_BACKUPS="mistral-default,default")
        code_, out, err = drive([sys.executable, "-u", str(path)], env2, tmp)
        done = [l for l in out.splitlines() if l.startswith("Done")]
        took = bool(done) and code_ == 0 and "Mistral:" in done[-1] and "OpenAI:" not in done[-1] and "a backup answered" in done[-1]
        check(took, "with no OpenAI key, the Mistral backup answers every step" + ("" if took else f": {(done[-1] if done else out[-300:])}"))
        check("▸ Backup" in out and "OPENAI_API_KEY" in out, "the run log says the backup stepped in, and why")
        check(all(c["model"] == "mistral-medium-latest" for c in llama_calls[before:]), "nothing was sent to OpenAI")
        env3 = dict(env, RB_MODEL_TIER="openai-default", OPENAI_API_KEY="", RB_BACKUPS="xai-default", XAI_API_KEY="")
        code_, out, err = drive([sys.executable, "-u", str(path)], env3, tmp)
        check(code_ != 0 and "its backup failed" in (out + err), "when the backup fails too, the run stops with a clear message")
        env4 = dict(env, RB_MODEL_TIER="openai-default", OPENAI_API_KEY="", RB_BACKUPS="")
        code_, out, err = drive([sys.executable, "-u", str(path)], env4, tmp)
        check(code_ != 0 and "OPENAI_API_KEY = your-key" in (out + err) and "▸ Backup" not in out, "with no backups, the primary's own error is shown")

    print("New features in Python")
    with tempfile.TemporaryDirectory() as tmp:
        for name, code in EXTRA.items():
            (pathlib.Path(tmp) / f"{name}.py").write_text(code, encoding="utf-8")
        code_, out, err = drive([sys.executable, "-u", str(pathlib.Path(tmp) / "t_program.py")], env, tmp)
        out = out.replace("\r\n", "\n")  # Windows prints \r\n
        ok = code_ == 0 and "▸ Program: shout" in out and "hi\n\nfrom sub\n\nmain done" in out
        check(ok, "t_program.py runs the saved program inside it" + ("" if ok else f" (exit {code_}): {(err or out)[-300:]!r}"))
        code_, out, err = drive([sys.executable, "-u", str(pathlib.Path(tmp) / "t_agent.py")], env, tmp)
        out = out.replace("\r\n", "\n")
        check(code_ == 0 and "Allow this? let the agent use hydration" in out and "▸ Agent: finished in 2 steps" in out,
              "t_agent.py asks before using the tool, then finishes" + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        print("Structured replies in Python")
        (pathlib.Path(tmp) / "t_json.py").write_text(EXTRA["t_json"], encoding="utf-8")
        log = pathlib.Path(tmp) / "fake.log"
        code_, out, err = drive([sys.executable, "-u", str(pathlib.Path(tmp) / "t_json.py")],
                                dict(env, FAKE_LOG=str(log), FAKE_JSON_SCRIPT=json.dumps(["this is not json", '{"number": 7}', '{"num": 1}', '{"number": 8}'])), tmp)
        out = out.replace("\r\n", "\n")
        check(code_ == 0 and out.count("▸ Unreadable reply  [repair]") == 2 and "RESULT\n" + "=" * 60 + "\n7\n\n8\n" in out,
              "t_json.py repairs an unreadable reply and a wrong-shaped one" + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        check(log.exists() and log.read_text().count("SCHEMA ok") >= 2, "Claude is sent each reply's shape (and the shapes are ones the API accepts)")
        code_, out, err = drive([sys.executable, "-u", str(pathlib.Path(tmp) / "t_json.py")], dict(env, FAKE_REJECT_SCHEMA="1"), tmp)
        check(code_ == 0 and out.count("▸ Structured replies  [note]") == 1, "if a model refuses reply shapes, the run carries on without them, and says so once")
        print("Review loop and checkpoints in Python")
        for name in ("t_bestdraft", "t_checkpoint"):
            (pathlib.Path(tmp) / f"{name}.py").write_text(EXTRA[name], encoding="utf-8")
        reviews = [json.dumps({"approved": False, "problems": p_}) for p_ in (["a", "b"], ["a"], ["a", "b", "c"], ["a", "b"])]
        code_, out, err = drive([sys.executable, "-u", str(pathlib.Path(tmp) / "t_bestdraft.py")], dict(env, FAKE_JSON_SCRIPT=json.dumps(reviews)), tmp)
        out = out.replace("\r\n", "\n")
        check(code_ == 0 and "▸ Kept the best draft  [best draft]" in out and "RESULT (best effort)\n" + "=" * 60 + "\nv2\n\na\n" in out,
              "t_bestdraft.py keeps round 2's draft" + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        code_, out, err = drive([sys.executable, "-u", str(pathlib.Path(tmp) / "t_checkpoint.py")], env, tmp)
        out = out.replace("\r\n", "\n")
        check(code_ == 0 and "RESULT\n" + "=" * 60 + "\nr1\n\ngood 1\n" in out, "t_checkpoint.py goes back to its checkpoint, twice" + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        print("Cut-off replies and streaming in Python")
        (pathlib.Path(tmp) / "t_long.py").write_text(EXTRA["t_long"], encoding="utf-8")
        def long_py(**e):
            c, o, er = drive([sys.executable, "-u", str(pathlib.Path(tmp) / "t_long.py")], dict(env, **e), tmp)
            return c, o.replace("\r\n", "\n"), er  # Windows prints \r\n
        code_, out, err = long_py(FAKE_TRUNCATE="1")
        res = out.split("=" * 60 + "\n")[-1] if "RESULT" in out else ""
        check(code_ == 0 and "▸ Reply continued  [continued]" in out and "RESULT\n" in out and res.count("TEXT[") == 2 and "Cut short" not in out,
              "t_long.py continues a cut-off reply once and joins the parts" + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        code_, out, err = long_py(FAKE_TRUNCATE="2")
        check(code_ == 0 and "▸ Cut short  [warn]" in out and "RESULT (best effort)" in out, "a reply still cut off is flagged and marked best effort")
        log = pathlib.Path(tmp) / "stream.log"
        code_, out, err = long_py(RB_STREAM="yes", FAKE_LOG=str(log))
        check(code_ == 0 and log.exists() and "STREAM" in log.read_text() and "… writing: " in out and "RESULT\n" in out,
              "stream = yes streams Claude's reply with a progress line" + ("" if code_ == 0 and "RESULT\n" in out else f": {(err or out)[-300:]!r}"))
        log.unlink(missing_ok=True)
        code_, out, err = long_py(FAKE_LOG=str(log))
        check(code_ == 0 and "STREAM" not in (log.read_text() if log.exists() else "") and "writing:" not in out,
              "when the output isn't a terminal, replies aren't streamed by default")
        check("; stream = yes" in EXPORTS["review"]["second-thought.ini"], "the exported ini explains the stream setting")
        print("Native JSON modes in Python")
        for name in ("t_json_mistral", "t_json_gemini"):
            (pathlib.Path(tmp) / f"{name}.py").write_text(EXTRA[name], encoding="utf-8")
        run_json = lambda name, **e: drive([sys.executable, "-u", str(pathlib.Path(tmp) / f"{name}.py")], dict(env, **e), tmp)  # noqa: E731
        before = len(llama_calls)
        code_, out, err = run_json("t_json_mistral")
        modes = [c["json"] for c in llama_calls[before:]]
        check(code_ == 0 and modes == ["json_schema", "json_schema"] and "RESULT" in out, f"an OpenAI-style service is asked for the reply's JSON Schema ({modes})")
        fake_llama.REFUSE_JSON.update({"json_schema"})
        before = len(llama_calls)
        code_, out, err = run_json("t_json_mistral")
        modes = [c["json"] for c in llama_calls[before:]]
        check(code_ == 0 and modes == ["json_schema", "json_object", "json_object"] and out.count("▸ Structured replies  [note]") == 1,
              f"a service that refuses the schema falls back to plain JSON mode, remembers it, and says so once ({modes})")
        fake_llama.REFUSE_JSON.update({"json_object"})
        before = len(llama_calls)
        code_, out, err = run_json("t_json_mistral")
        modes = [c["json"] for c in llama_calls[before:]]
        check(code_ == 0 and modes == ["json_schema", "json_object", None, None] and "RESULT" in out,
              f"a service with no JSON mode at all is asked without one, and still works ({modes})")
        fake_llama.REFUSE_JSON.clear()
        log = pathlib.Path(tmp) / "gemini.log"
        code_, out, err = run_json("t_json_gemini", FAKE_LOG=str(log))
        lines = [json.loads(l[7:]) for l in (log.read_text().splitlines() if log.exists() else []) if l.startswith("GEMINI ")]
        check(code_ == 0 and lines and all(l["json"] == "application/json" for l in lines), "Gemini is asked to reply in JSON")
        print("Resuming after a stop")
        folder = pathlib.Path(tmp) / "resume"
        folder.mkdir()
        prog = folder / "t_resume.py"
        prog.write_text(EXTRA["t_resume"], encoding="utf-8")
        journal = folder / ".t_resume.resume.jsonl"
        def resume_run(**e):
            log = folder / "fake.log"
            log.unlink(missing_ok=True)
            c, o, er = drive([sys.executable, "-u", str(prog)], dict(env, FAKE_LOG=str(log), **e), str(folder))
            return c, o.replace("\r\n", "\n"), (log.read_text().count("CREATE") if log.exists() else 0)
        notes = lambda: sum(1 for c in ha_calls if c[0] == "persistent_notification.create" and c[1].get("message") == "Half way there.")  # noqa: E731
        code_, out, made = resume_run(FAKE_FAIL_AT="3")
        check(code_ != 0 and journal.exists() and "Run the program again to pick up where it stopped." in out, "a run that stops part-way keeps a journal and says how to pick up")
        sent = notes()
        code_, out, made = resume_run(RB_RESUME="yes")
        check(code_ == 0 and made == 1 and "? What bread?" not in out and notes() == sent and "▸ Resuming  [resume]" in out
              and "Already sent before the stop" in out and "reused from the run that stopped: no new call" in out and "▸ Caught up" in out
              and out.split("RESULT\n" + "=" * 60 + "\n")[-1].count("TEXT[") == 3 and not journal.exists(),
              f"picking up reuses the saved answers, asks nothing twice, sends nothing twice, and makes only the missing call ({made} new call(s))")
        resume_run(FAKE_FAIL_AT="3")
        code_, out, made = resume_run(RB_RESUME="no")
        check(code_ == 0 and made == 3 and "? What bread?" in out and not journal.exists(), "resume = no starts afresh")
        resume_run(FAKE_FAIL_AT="3")
        code_, out, made = resume_run()
        check(code_ == 0 and made == 3 and "Set resume = yes" in out, "with nobody to ask and no setting, it starts afresh and says how to resume")
        resume_run(FAKE_FAIL_AT="3")
        code_, out, made = resume_run(RB_RESUME="yes", RB_MODEL_TIER="quick")
        check(code_ == 0 and made == 3 and "? What bread?" not in out and "▸ Run differs here" in out,
              "replay stops at the first step that differs (here, a different model), and the rest runs live")
        resume_run(FAKE_FAIL_AT="3")
        prog.write_text(EXTRA["t_resume"] + "\n# edited\n", encoding="utf-8")
        code_, out, made = resume_run(RB_RESUME="yes")
        check(code_ == 0 and made == 3 and "the program has changed since" in out, "if the program has changed, it starts afresh")
        check("; resume = yes" in EXPORTS["review"]["second-thought.ini"], "the exported ini explains the resume setting")
        print("Real-service smoke test (against the stand-ins)")
        smoke_env = {k: v for k, v in env.items() if not k.endswith(("_API_KEY", "_TOKEN")) and k != "LLAMA_BASE_URL"}
        smoke_env.update(HOMEY_API_KEY=fake_services.HOMEY_KEY, ANTHROPIC_API_KEY="test", GEMINI_API_KEY="test", MISTRAL_API_KEY="test", MISTRAL_BASE_URL=llama_url)
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "smoke_test.py")], env=smoke_env, cwd=tmp, capture_output=True, text=True, timeout=180)
        out = r.stdout.replace("\r\n", "\n")
        check("PASS  Homey: reading your devices and flows  (12 devices, 6 zones, 3 flows)" in out,
              "the smoke test reads your Homey's devices, zones and flows" + ("" if "Homey:" in out else f": {out[-300:]!r}"))
        check(r.returncode == 0 and "PASS  Claude: cut-off reply continued" in out and "PASS  Claude: agent called a typed tool and answered" in out
              and "NOTE  Mistral: JSON mode it accepts  (the full JSON Schema)" in out and "SKIP  OpenAI: all checks" in out,
              "tools/smoke_test.py runs every check and reports each service" + ("" if r.returncode == 0 else f": {(r.stderr or out)[-400:]!r}"))
        print("Connections in Python")
        sent_before = len(svc_log["tg_sent"]), len(svc_log["mail_sent"])
        check(sent_before[0] >= 2 and sent_before[1] >= 1 and any("Got:" not in m["text"] for m in svc_log["tg_sent"]),
              f"the examples sent Telegram messages ({sent_before[0]}) and emails ({sent_before[1]}) through the stand-ins")
        for name in ("t_cn_gh", "t_cn_comment", "t_cn_gh_more", "t_cn_issue", "t_cn_tg", "t_cn_mail", "t_cn_cal", "t_cn_feed"):
            (pathlib.Path(tmp) / f"{name}.py").write_text(EXTRA[name], encoding="utf-8")
        run_cn = lambda name: drive([sys.executable, "-u", str(pathlib.Path(tmp) / f"{name}.py")],  # noqa: E731
                                    dict(env, FAKE_AGENT_SCRIPT=json.dumps(AGENT_SCRIPTS[name])), tmp)
        code_, out, err = run_cn("t_cn_gh")
        out = out.replace("\r\n", "\n")
        check(code_ == 0 and "Waiting for your review: sample-baker/sourdough-chart #41 Add rye flour curve · pull request by crumb-shot" in out
              and "- src/curves.js (+24 −2) @@" in out and "Comments: - crumb-shot: Num" in out
              and "isn't a GitHub project" in out and "sample-baker/oven-timer: A Home Assistant timer card" in out,
              "Python's GitHub tools read pull requests, files, comments and projects" + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        before = len(svc_log["gh"])
        code_, out, err = run_cn("t_cn_comment")
        posted = [c for c in svc_log["gh"][before:] if c.startswith("POST ")]
        check(code_ == 0 and "Allow this? let the agent use comment_on_github" in out and posted == ["POST /repos/sample-baker/oven-timer/issues/7/comments"]
              and out.count("Allow this?") == 1, "Python asks once, then posts the GitHub comment" + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        code_, out, err = run_cn("t_cn_gh_more")
        out = " ".join(out.split())
        check(code_ == 0 and 0 <= out.find("old-d3-v5 · last commit 311 days ago by toast-rack") < out.find("main · last commit 24 h ago by sample-baker · default branch")
              and "rye-curve · last commit 24 h ago by crumb-shot · open pull request #41" in out
              and "a41c9e2 · " in out and "3e8a52c" in out and "77d3e0a" not in out and "isn't a time to start from" in out
              and "| `--starter` | starter percentage" in out and "is a folder: chart.js cli.js curves.js" in out and "is a folder: README.md package.json src/" in out,
              "Python lists branches and commits and reads files and folders, as the page does" + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        before = len(svc_log["gh"])
        code_, out, err = run_cn("t_cn_issue")
        posted = [c for c in svc_log["gh"][before:] if c.startswith("POST ")]
        out = " ".join(out.split())
        check(code_ == 0 and posted == ["POST /repos/sample-baker/sourdough-chart/issues/40/labels", "POST /repos/sample-baker/sourdough-chart/issues"]
              and "has no label safari" in out and "Labelled sample-baker/sourdough-chart #40: bug, urgent." in out
              and "Opened sample-baker/sourdough-chart #44: https://github.com/sample-baker/sourdough-chart/issues/44" in out and "needs a title" in out
              and out.count("Allow this?") == 4, f"Python labels with the project's own labels and opens an issue, asking before each use ({posted})"
              + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        (pathlib.Path(tmp) / "recipes").mkdir(exist_ok=True)
        for name in ("rye.pdf", "focaccia.txt"):
            (pathlib.Path(tmp) / "recipes" / name).write_text("x", encoding="utf-8")
        (pathlib.Path(tmp) / "t_folder_check.py").write_text(EXTRA["t_folder_check"], encoding="utf-8")
        code_, out, err = drive([sys.executable, "-u", str(pathlib.Path(tmp) / "t_folder_check.py")], env, tmp)
        out = out.replace("\r\n", "\n")
        check(code_ == 0 and "rye.pdf" in out and "focaccia.txt" not in out and "Only reading: nothing is sent" in out and "  ok    Python: " in out,
              "in Python, 'files in folder' lists the matching files next to the program, and the setup check gives --doctor's report mid-run"
              + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        before = len(svc_log["tg_sent"])
        code_, out, err = run_cn("t_cn_tg")
        check(code_ == 0 and "Remind me to feed the starter at 8 tonight" in out and "Someone else's message" not in out
              and [m["text"] for m in svc_log["tg_sent"][before:]] == ["Feed the starter at 8"] and "set TELEGRAM_CHAT_ID = 999" in out,
              "Python's Telegram tools search only your chats and send after asking" + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        before = len(svc_log["mail_sent"])
        code_, out, err = run_cn("t_cn_mail")
        mails = svc_log["mail_sent"][before:]
        check(code_ == 0 and "Subject: Your flour order has shipped" in out and "Attachments: starter-notes.txt" in out and "x()" not in out
              and len(mails) == 1 and "<sam@example.com>" in mails[0]["to"] and "Yes, see you at 2!" in mails[0]["data"] and "isn't an email address" in out,
              "Python's email tools search and read the inbox, and send one email after asking" + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        code_, out, err = run_cn("t_cn_cal")
        out = out.replace("\r\n", "\n")
        try:  # the baking club is at 14:00 London time: shown in this computer's own time zone
            from zoneinfo import ZoneInfo
            day = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=3)
            club = [(day + datetime.timedelta(hours=h)).replace(tzinfo=ZoneInfo("Europe/London")).astimezone().strftime("%H:%M") for h in (14, 17)]
        except Exception:  # no time zone data (Windows without tzdata): the runtime treats the time as local
            club = ["14:00", "17:00"]
        check(code_ == 0 and "10:00–11:00 Dentist (High Street, No. 4)" in out and "15:30–16:00 Call with the web designer" in out
              and "all day Flour delivery" in out and f"{club[0]}–{club[1]} Baking club" in out and "Cancelled lunch" not in out and "18:00–19:00 Yoga" in out
              and "Free on " in out and "11:00–15:30" in out and "isn't a day" in out,
              "Python's calendar reads iCal: time zones, all-day events, repeats, skipped and cancelled events, and free time" + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        code_, out, err = run_cn("t_cn_feed")
        check(code_ == 0 and "The Loaf Letter (sample feed)" in out and "Small Tools Weekly (sample feed)" in out
              and "not addresses on your own network" in out, "Python reads your RSS and Atom feeds, but not a feed address on your network the agent chose"
              + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        (pathlib.Path(tmp) / "t_tg_when.py").write_text(EXTRA["t_tg_when"], encoding="utf-8")
        before = len(svc_log["tg_sent"])
        tg_add("When should I bake the rye?")
        tg_add("Nothing to see here")
        code_, out, err = drive([sys.executable, "-u", str(pathlib.Path(tmp) / "t_tg_when.py")], env, tmp, timeout=12)
        got = [m["text"] for m in svc_log["tg_sent"][before:]]
        check(got == ["Got: When should I bake the rye?"] and "Telegram message" in out,
              f"t_tg_when.py answers a new Telegram message containing 'bake', and not older ones or others ({got})")

        print("A fooled agent in Python stays inside the gates")
        # As on the page: a model that fell for the hostile email tries the attacker's moves. Every ask is answered no.
        run_no = lambda name: drive([sys.executable, "-u", str(pathlib.Path(tmp) / f"{name}.py")],  # noqa: E731
                                    dict(env, RB_APPROVE="no", FAKE_AGENT_SCRIPT=json.dumps(AGENT_SCRIPTS[name])), tmp, approve="n")
        for name in ("t_inj_mail", "t_inj_leak", "t_inj_ha", "t_inj_mqtt"):
            (pathlib.Path(tmp) / f"{name}.py").write_text(EXTRA[name], encoding="utf-8")
        sent = len(svc_log["mail_sent"])
        code_, out, err = run_no("t_inj_mail")
        check(code_ == 0 and "IMPORTANT INSTRUCTIONS FOR THE AI ASSISTANT" in out and out.count("Allow this?") == 1
              and len(svc_log["mail_sent"]) == sent and "[refused]" in out,
              "Python: a fooled agent's email to the attacker waits for a yes, and a no stops it" + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        code_, out, err = run_no("t_inj_leak")
        check(code_ == 0 and out.count("Allow this?") == 1 and "made this address up" in out and "collect?d=" in out,
              "Python: an agent that can see private things asks before reading an address it made up, not one from a feed"
              + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        before = len(ha_calls)
        code_, out, err = run_no("t_inj_ha")
        called = [c for c in ha_calls[before:]]
        check(code_ == 0 and out.count("Approve? [y/n]") == 3 and not any(x in str(called) for x in ("script.turn_on", "cover.toggle", "homeassistant"))
              and "light" in str(called),
              f"Python: with 'control devices (no asking)', scripts and opening actions still ask, and a no stops them ({called})"
              + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        before = len(broker.published)
        code_, out, err = run_no("t_inj_mqtt")
        check(code_ == 0 and broker.published[before:] == [("zigbee2mqtt/kitchen_light/set", "ON", False)] and out.count("Allow this?") == 1,
              f"Python: with 'publish (no asking)', an unlock message asks and a no stops it; an ordinary one goes ({broker.published[before:]})"
              + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))

        print("Listeners in Python")
        (pathlib.Path(tmp) / "t_ls_mqtt.py").write_text(EXTRA["t_ls_mqtt"], encoding="utf-8")
        before = len(broker.published)
        code_, out, err = run_cn("t_ls_mqtt")
        check(code_ == 0 and "zigbee2mqtt/leak_sensor_sink: {\"water_leak\": false, \"battery\": 87}" in out and "zigbee2mqtt/oven_plug: {\"state\": \"ON\"" in out
              and broker.published[before:] == [("zigbee2mqtt/oven_plug/set", "OFF", False)] and "can't publish to a topic with + or #" in out,
              "Python's MQTT tools read kept messages with wildcards, and publish after asking" + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        (pathlib.Path(tmp) / "t_listen.py").write_text(EXTRA["t_listen"], encoding="utf-8")
        import socket
        import urllib.request as ureq
        with socket.socket() as so:
            so.bind(("127.0.0.1", 0))
            hook_port = so.getsockname()[1]
        hook = {}

        def poke():
            """Once the program is listening, make one of each thing arrive."""
            broker.wait_for_subscriber("home/proofer/temperature")
            time.sleep(1.5)
            broker.publish("home/proofer/temperature", "27.9")
            broker.publish("home/kitchen/temperature", "19")  # a topic nobody listens to
            for _ in range(100):
                try:
                    hook["refused"] = ureq.urlopen(ureq.Request(f"http://127.0.0.1:{hook_port}/bake-done", data=b"{}", method="POST"), timeout=5).status
                except urllib.error.HTTPError as e:
                    hook["refused"] = e.code
                    break
                except OSError:
                    time.sleep(0.2)
            req = ureq.Request(f"http://127.0.0.1:{hook_port}/bake-done?key=hook-secret", data=json.dumps({"loaf": "spelt"}).encode(), method="POST")
            hook["ok"] = ureq.urlopen(req, timeout=5).status
            svc_log["add_mail"]("Mill & Co <orders@example.com>", "More flour on the way", "Your rye flour arrives Tuesday.")
            svc_log["add_mail"]("Someone <x@example.com>", "Unrelated", "Nothing about baking.")
            svc_log["add_feed_item"]("Brand new: steam in home ovens", "https://example.com/baking/steam")
            svc_log["add_review"]("Add a spelt recipe")
            svc_log["add_issue"]("sample-baker/sourdough-chart", "Chart legend overlaps on mobile")
            svc_log["add_release"]("sample-baker/sourdough-chart", "v1.5.0", "Rye curve")
            svc_log["discord_add"](fake_services.DISCORD_CHANNEL, "Is the bake-along still on?", "crumb_shot")
            svc_log["discord_add"](fake_services.DISCORD_CHANNEL, "A bot announcing something", "OtherBot", bot=True)
            svc_log["discord_add"]("999", "Message in someone else's channel", "stranger")
            svc_log["slack_add"](fake_services.SLACK_CHANNEL, "Proving baskets are back on the shelf", "U123")
            svc_log["slack_add"]("C999", "Other workspace channel", "U999")
            (pathlib.Path(tmp) / "drop").mkdir(exist_ok=True)
            (pathlib.Path(tmp) / "drop" / "notes.txt").write_text("Spelt loaf: 500 g spelt, 350 g water.", encoding="utf-8")
            (pathlib.Path(tmp) / "drop" / ".hidden").write_text("ignored", encoding="utf-8")
        ha_seen = {}

        def ha_poke():
            """Send Home Assistant events as soon as the program subscribes (its own thread, so the other pokes can't delay it)."""
            start = time.time()
            while not fake_ha.subscribers and time.time() - start < 28:
                time.sleep(0.1)
            ha_seen["subscribed_after"] = round(time.time() - start, 1) if fake_ha.subscribers else None
            time.sleep(1.5)  # as with MQTT: give the program a moment after subscribing (on Windows, events in its first second were sometimes missed)
            ha_seen["sent"] = [fake_ha.fire_event("zha_event", {"device_name": "Hall remote", "command": "on"}),  # another remote
                               fake_ha.fire_event("call_service", {"domain": "light", "service": "turn_on"}),  # another kind of event
                               fake_ha.fire_event("zha_event", {"device_name": "Kitchen remote", "command": "on"})]
        before = len(broker.published)
        pk = threading.Thread(target=poke, daemon=True)
        pk.start()
        threading.Thread(target=ha_poke, daemon=True).start()
        code_, out, err = drive([sys.executable, "-u", str(pathlib.Path(tmp) / "t_listen.py")],
                                dict(env, RB_POLL_SECONDS="0.5", WEBHOOK_PORT=str(hook_port), WEBHOOK_SECRET="hook-secret",
                                     CALENDAR_URL=svc_url + "/calendar-soon.ics"), tmp, timeout=30)
        out = out.replace("\r\n", "\n")
        notes = [l.strip() for l in out.split("\n") if re.match(r"\s+(mqtt|webhook|email|feed|folder|github_issue|github_release|github|calendar|telegram|discord|slack|ha_event): ", l)]
        got = {n.split(":", 1)[0] for n in notes}
        check(got >= {"mqtt", "webhook", "email", "feed", "folder", "github", "github_issue", "github_release", "calendar", "discord", "slack", "ha_event"},
              f"t_listen.py: every listener started its script when something arrived ({', '.join(sorted(got)) or 'none'})" + ("" if got else f": {(err or out)[-400:]!r}"))
        if not got >= {"mqtt", "webhook", "email", "feed", "folder", "github", "github_issue", "github_release", "calendar", "discord", "slack", "ha_event"}:
            # It has failed now and then on Windows only, with the program gone within a couple of seconds. Show the
            # traceback in full, each line marked "error:" so the CI summary keeps it, and how long the program lasted.
            tb = (err or "").splitlines()
            start = max((i for i, l in enumerate(tb) if l.startswith("Traceback")), default=None)
            for l in (tb[start:start + 40] if start is not None else tb[-15:]):
                print("  error: t_listen stderr: " + l.rstrip()[:250])
            print(f"  error: t_listen exit code {code_}; last output lines: " + " | ".join(out.strip().splitlines()[-6:])[:600])
        check("mqtt: 27.9" in notes and not any("19" == n.split(": ", 1)[1] for n in notes if n.startswith("mqtt")) and ("home/proofer/ack", "seen 27.9", False) in broker.published[before:],
              "the MQTT listener reacts to its own topic only, and its script can publish a reply")
        check(hook.get("refused") == 403 and hook.get("ok") == 200 and any(n.startswith("webhook: ") and "spelt" in n for n in notes),
              f"a web request without the key is refused; with it, the script gets what was sent ({hook})")
        ha_notes = [n for n in notes if n.startswith("ha_event: ")]
        check(len(ha_notes) == 1 and "Kitchen remote" in ha_notes[0] and ha_notes[0].startswith("ha_event: zha_event: "),
              f"the Home Assistant event listener reacts to its own remote's event only, at once ({ha_notes})"
              + ("" if len(ha_notes) == 1 else f" {ha_seen}"))
        if len(ha_notes) != 1:  # short lines the CI summary keeps (it shows lines with 'error:', cut at 300 characters)
            for l in [l for l in out.split("\n") if l.strip().startswith("(") or "Listening" in l or "Home Assistant" in l][-12:] + (err or "").splitlines()[-8:]:
                print("  error: t_listen said: " + l.strip()[:250])
            for entry in fake_ha.ws_log[-12:]:
                print(f"  error: fake Home Assistant: {entry}")
        check("Subject: More flour on the way" in out and "Subject: Unrelated" not in out and "Subject: Your flour order has shipped" not in out,
              "the email listener only reacts to new emails that match")
        check(any("steam in home ovens" in n for n in notes) and not any("nail varnish" in n for n in notes), "the feed listener only reacts to new items")
        check(any(n.startswith("folder: Spelt loaf") for n in notes) and not any("ignored" in n for n in notes), "the folder listener reads new files and skips hidden ones")
        check(any("Add a spelt recipe" in n for n in notes) and not any("#41" in n for n in notes), "the GitHub listener reacts to new review requests only")
        gh_new = [n for n in notes if n.startswith(("github_issue: ", "github_release: "))]
        check(len(gh_new) == 2 and any(n.startswith("github_issue: sample-baker/sourdough-chart #") and n.endswith(": Chart legend overlaps on mobile (by toast-rack)") for n in gh_new)
              and "github_release: sample-baker/sourdough-chart v1.5.0: Rye curve" in gh_new,
              f"the new-issue and release listeners react to new ones only, not the issues and releases already there ({gh_new})")
        check(any(n.startswith("calendar: Feed the starter at ") and "(Kitchen)" in n for n in notes), "the calendar listener gives warning before an event")
        check([n for n in notes if n.startswith("discord: ")] == ["discord: Is the bake-along still on?"],
              f"the Discord listener reacts to new messages in your channels only: not old ones, bots, or other channels ({[n for n in notes if n.startswith('discord')]})")
        check([n for n in notes if n.startswith("slack: ")] == ["slack: Proving baskets are back on the shelf"],
              f"the Slack listener reacts to new messages in your channels only ({[n for n in notes if n.startswith('slack')]})")
        chat = r"""
import asyncio, json, os, sys
ns = {"__name__": "rt", "__file__": sys.argv[1]}
exec(compile(open(sys.argv[1], encoding="utf-8").read(), "rt", "exec"), ns)
R = ns["Runtime"](); R.reset(); R.log = lambda *a, **k: None
out = {}
async def go():
    out["d_search"] = await R.chat_search("discord", "bake-along")
    out["s_search"] = await R.chat_search("slack", "")
    out["d_sent"] = await R.chat_send("discord", "Hello Discord")
    out["s_sent"] = await R.chat_send("slack", "x" * 3600)
    for svc, ch in (("discord", "999"), ("slack", "C999")):
        try:
            await R.chat_send(svc, "sneaky", ch); out[svc + "_other"] = "sent"
        except ns["RunError"] as e:
            out[svc + "_other"] = str(e)
    os.environ["SLACK_BOT_TOKEN"] = "wrong"
    try:
        await R.chat_search("slack"); out["bad_token"] = "worked"
    except ns["RunError"] as e:
        out["bad_token"] = str(e)
asyncio.run(go())
print(json.dumps(out))
"""
        sent_before = len(svc_log["discord_sent"]), len(svc_log["slack_sent"])
        r = subprocess.run([sys.executable, "-c", chat, str(ROOT / "python" / "runtime.py")], capture_output=True, text=True, timeout=60, env=env)
        got = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 and r.stdout.strip() else {}
        check("Bake-along is Sunday" in got.get("d_search", "") and "bake-along cancelled" not in got.get("d_search", "") and "Bot's own" not in got.get("d_search", "")
              and "Oven's free from 2pm" in got.get("s_search", "") and "oven broken" not in got.get("s_search", ""),
              f"Python searches your Discord and Slack channels only, skipping bots ({got or r.stderr[-300:]})")
        new_d, new_s = svc_log["discord_sent"][sent_before[0]:], svc_log["slack_sent"][sent_before[1]:]
        check(got.get("d_sent") is True and new_d == [(fake_services.DISCORD_CHANNEL, "Hello Discord")]
              and [len(t) for c, t in new_s] == [3500, 100] and all(c == fake_services.SLACK_CHANNEL for c, t in new_s),
              f"Python posts in your first channel, splitting long Slack messages ({new_d}, {[(c, len(t)) for c, t in new_s]})")
        check("isn't in DISCORD_CHANNEL_ID" in got.get("discord_other", "") and "isn't in SLACK_CHANNEL_ID" in got.get("slack_other", "")
              and "bot token was refused" in got.get("bad_token", ""),
              "Python won't post in a channel that isn't in your settings, and says plainly when a token is wrong")

        page_prog = EXTRA["t_page"].replace("http://127.0.0.1:1/watch.html", svc_url + "/watch.html")
        (pathlib.Path(tmp) / "t_page.py").write_text(page_prog, encoding="utf-8")
        watched = pathlib.Path(tmp) / "watched-pages.json"
        if watched.exists():
            watched.unlink()

        def page_poke():
            time.sleep(3)  # the first checks only remember the page
            svc_log["page"]["visitors"] = 18  # outside the Price part: only the whole-page watcher sees it
            time.sleep(2.5)
            svc_log["page"]["price"] = "£2.65"
        svc_log["page"].update(price="£2.40", visitors=17)
        threading.Thread(target=page_poke, daemon=True).start()
        code_, out, err = drive([sys.executable, "-u", str(pathlib.Path(tmp) / "t_page.py")], dict(env, RB_POLL_SECONDS="0.5"), tmp, timeout=10)
        out = out.replace("\r\n", "\n")
        part = re.findall(r"    page-part: (.*)\n    (.*)\n", out)
        whole = re.findall(r"    page-all: (.*)\n    (.*)\n", out)
        check(part == [("- £2.40", "+ £2.65")] and ("- Visitors today: 17", "+ Visitors today: 18") in whole and ("- £2.40", "+ £2.65") in whole,
              f"t_page.py: the whole-page watcher sees both changes, the 'Price' watcher only the price ({part}, {whole})" + ("" if part else f": {(err or out)[-300:]!r}"))
        check(watched.exists() and "£2.65" in watched.read_text(encoding="utf-8"), "the last copy of each watched page is kept in watched-pages.json")
        code_, out, err = drive([sys.executable, "-u", str(pathlib.Path(tmp) / "t_page.py")], dict(env, RB_POLL_SECONDS="0.5"), tmp, timeout=4)
        check("page-part:" not in out and "page-all:" not in out and "Watching " in out, "after a restart, an unchanged page doesn't count as changed")

        print("Homey in Python")
        for name in ("t_hm_agent", "t_hm_blocks", "t_hm_listen"):
            (pathlib.Path(tmp) / f"{name}.py").write_text(EXTRA[name], encoding="utf-8")
        before = len(svc_log["homey"])
        code_, out, err = run_cn("t_hm_agent")
        calls = svc_log["homey"][before:]
        check(code_ == 0 and "Kitchen light (Kitchen, light): onoff=on, dim=0.8" in out and "PUT /devices/device/d-kitchen-light/capability/onoff" in calls
              and "PUT /devices/device/d-front-lock/capability/locked" in calls and "f-goodnight" in svc_log["homey_flows"] and out.count("Allow this?") == 5
              and "no Homey device called “Toaster”" in out and "isn't a number" in out and "Baking mode (advanced)" in out,
              "Python's Homey tools use the local API: find, switch, unlock asking once, start a flow" + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        code_, out, err = drive([sys.executable, "-u", str(pathlib.Path(tmp) / "t_hm_blocks.py")], env, tmp)
        res = out.replace("\r\n", "\n").split("RESULT")[-1]
        check(code_ == 0 and "26.4" in res and "0.25" in res and "Feed the starter" in res and "f-bake" in svc_log["homey_flows"],
              "t_hm_blocks.py reads and sets devices and variables, and starts an advanced flow" + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))

        def homey_poke():
            time.sleep(4)
            svc_log["homey_change"]("Washing machine", "measure_power", 1.5)
            svc_log["homey_change"]("Garden motion", "alarm_motion", True)
        threading.Thread(target=homey_poke, daemon=True).start()
        code_, out, err = drive([sys.executable, "-u", str(pathlib.Path(tmp) / "t_hm_listen.py")], dict(env, RB_POLL_SECONDS="0.5"), tmp, timeout=12)
        notes = [l.strip() for l in out.replace("\r\n", "\n").split("\n") if l.strip().startswith("homey: ")]
        check(len(notes) == 1 and notes[0].startswith("homey: Washing machine measure_power: ") and notes[0].endswith("→ 1.5"),
              f"t_hm_listen.py starts its script when the washing machine's power changes, and not for other devices ({notes})")

        print("Safety and robustness (from the code review)")
        unit = r"""
import json, os, socket, sys, threading, asyncio, zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
for k in list(os.environ):
    if k.lower().endswith("_proxy"):
        del os.environ[k]
sys.modules["anthropic"] = None  # as if the SDK weren't installed
hits = []
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        hits.append(self.path); self.send_response(200); self.send_header("Content-Length", "2"); self.end_headers(); self.wfile.write(b"ok")
srv = ThreadingHTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
port = srv.server_address[1]
out = {}
ns = {"__name__": "rt", "__file__": sys.argv[1]}
exec(compile(open(sys.argv[1], encoding="utf-8").read(), "rt", "exec"), ns)
out["calc"] = ns["calc_text"]("6 * 7")
real_lookup, lookups = socket.getaddrinfo, []
def lookup(host, *a, **k):
    if host == "rebind.example":  # public the first time it's asked, this computer the second time
        lookups.append(1)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.215.14" if len(lookups) == 1 else "127.0.0.1", port))]
    return real_lookup(host, *a, **k)
socket.getaddrinfo = lookup
real_connect = socket.socket.connect
def connect(self, addr):
    if addr[0] == "93.184.215.14":
        raise ConnectionRefusedError("test: no internet here")
    return real_connect(self, addr)
socket.socket.connect = connect
try:
    ns["get_url"](f"http://rebind.example:{port}/secret")
    out["rebind"] = "fetched"
except ns["RunError"] as e:
    out["rebind"] = str(e)
out["hits"], out["lookups"] = len(hits), len(lookups)
try:
    ns["get_url"](f"http://127.0.0.1:{port}/direct")
    out["direct"] = "fetched"
except ns["RunError"] as e:
    out["direct"] = str(e)
os.environ["ANTHROPIC_API_KEY"] = "x"
R = ns["Runtime"](); R.reset()
try:
    asyncio.run(R._call_claude("m", "hi", None, None, False))
    out["sdk"] = "called"
except ns["RunError"] as e:
    out["sdk"] = str(e)
d = sys.argv[2]
open(os.path.join(d, "fake.docx"), "w").write("not a zip at all")
with zipfile.ZipFile(os.path.join(d, "empty.docx"), "w") as z:
    z.writestr("other.xml", "<x/>")
for name in ("fake.docx", "empty.docx"):
    try:
        ns["read_text_file"](os.path.join(d, name)); out[name] = "read"
    except ns["RunError"] as e:
        out[name] = str(e)
print(json.dumps(out))
"""
        r = subprocess.run([sys.executable, "-c", unit, str(ROOT / "python" / "runtime.py"), tmp], capture_output=True, text=True, timeout=120,
                           env={k: v for k, v in env.items() if k != "PYTHONPATH"})
        got = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 and r.stdout.strip() else {}
        check(got.get("calc") == "6 * 7 = 42" and "needs the Anthropic SDK" in got.get("sdk", ""),
              "the runtime loads without the Anthropic SDK, and says plainly when Claude needs it" + ("" if got else f": {r.stderr[-300:]!r}"))
        check(got.get("hits") == 0 and got.get("lookups") == 1 and "couldn't reach" in got.get("rebind", ""),
              f"a name that changes its answer (DNS rebinding) can't reach this computer: looked up once, connected only to the checked address ({got})")
        check("not addresses on your own network" in got.get("direct", ""), "an address on your own network is still refused")
        r = subprocess.run([sys.executable, "-c", PROXY_REDIRECT, str(ROOT / "python" / "runtime.py")], capture_output=True, text=True, timeout=60,
                           env={k: v for k, v in env.items() if k != "PYTHONPATH"})
        px = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 and r.stdout.strip() else {}
        check(px.get("start_hits") == 1 and px.get("admin_hits") == 0 and "not addresses on your own network" in px.get("proxied", ""),
              f"behind a proxy, a redirect from a public page to this computer is refused before it's followed ({px or r.stderr[-200:]})")
        check("Word file couldn't be read" in got.get("fake.docx", "") and "Word file couldn't be read" in got.get("empty.docx", ""),
              "a damaged or mislabelled Word file gives a plain message, not a crash")
        sys.path.insert(0, str(ROOT / "tools"))
        import sync as sync_tool
        try:
            sync_tool.build("<html>no tags</html>")
            msg = ""
        except SystemExit as e:
            msg = str(e)
        check("has no '<script type=\"text/plain\" id=\"py-runtime\">' tag" in msg, f"tools/sync.py explains a missing tag instead of a traceback ({msg[:80]})")
        (pathlib.Path(tmp) / "t_maxsec.py").write_text(EXTRA["t_maxsec"], encoding="utf-8")
        t0 = time.time()
        code_, out, err = drive([sys.executable, "-u", str(pathlib.Path(tmp) / "t_maxsec.py")], dict(env, RB_MAX_SECONDS="2"), tmp, timeout=40)
        check(code_ == 1 and "took longer than 2 seconds" in out and "too late" not in out and time.time() - t0 < 20,
              f"max_seconds stops a run that takes too long ({time.time() - t0:.0f} s)" + ("" if code_ == 1 else f": {(err or out)[-200:]!r}"))
        log = pathlib.Path(tmp) / "client.log"
        (pathlib.Path(tmp) / "review.py").write_text(codes["review"][0], encoding="utf-8")
        code_, out, err = drive([sys.executable, "-u", str(pathlib.Path(tmp) / "review.py")],
                                dict(env, FAKE_LOG=str(log), RB_CALL_TIMEOUT="45", MODEL_DEFAULT="claude-override-test"), tmp)
        text = log.read_text() if log.exists() else ""
        check(code_ == 0 and '"timeout": 45.0' in text and "claude-override-test |" in text,
              "call_timeout reaches the Claude client, and MODEL_DEFAULT swaps the model a tier uses" + ("" if code_ == 0 else f": {(err or out)[-200:]!r}"))
        code_, out, err = drive([sys.executable, "-u", str(pathlib.Path(tmp) / "review.py")], dict(env, FAKE_LOG=str(log)), tmp)
        check('"timeout": 300' in log.read_text(), "each Claude call gives up after 300 seconds unless call_timeout says otherwise")
        code_, out, err = drive([sys.executable, "-u", str(pathlib.Path(tmp) / "review.py")], dict(env, FAKE_LOG=str(log), RB_CALL_TIMEOUT="0"), tmp)
        check(code_ == 0 and '"timeout": null' in log.read_text().split("CLIENT ")[-1],
              "call_timeout = 0 means no timeout, like max_seconds = 0" + ("" if code_ == 0 else f": {(err or out)[-200:]!r}"))
        for bad in (dict(RB_MAX_SECONDS="banana"), dict(RB_CALL_TIMEOUT="ten"), dict(RB_BUDGET="-5")):
            code_, out, err = drive([sys.executable, "-u", str(pathlib.Path(tmp) / "review.py")], dict(env, **bad), tmp)
            name = {"RB_MAX_SECONDS": "max_seconds", "RB_CALL_TIMEOUT": "call_timeout", "RB_BUDGET": "budget"}[next(iter(bad))]
            check(code_ != 0 and f"{name} must be" in (out + err) and f"“{next(iter(bad.values()))}”" in (out + err),
                  f"a mistyped {name} stops the program and says which setting is wrong, instead of being ignored")
        tg_race = r"""
import asyncio, json, os, sys
ns = {"__name__": "rt", "__file__": sys.argv[1]}
exec(compile(open(sys.argv[1], encoding="utf-8").read(), "rt", "exec"), ns)
ns["TELEGRAM_FILE"] = os.path.join(sys.argv[2], "tg-race.json")
R = ns["Runtime"](); R.reset()
async def go():
    a, b = await asyncio.gather(R.tg_fetch(), R.tg_fetch())
    return len(a), len(b)
a, b = asyncio.run(go())
store = json.load(open(ns["TELEGRAM_FILE"], encoding="utf-8"))
texts = [m["text"] for m in store["messages"]]
R2 = ns["Runtime"](); R2.reset()  # made outside any event loop, as exported programs do
inside, most = [0], [0]
async def slow_fetch(wait):
    inside[0] += 1; most[0] = max(most[0], inside[0])
    await asyncio.sleep(0.05)
    inside[0] -= 1
    return []
R2._tg_fetch = slow_fetch
async def three():
    await asyncio.gather(R2.tg_fetch(), R2.tg_fetch(), R2.tg_fetch())
asyncio.run(three())
print(json.dumps({"a": a, "b": b, "dupes": len(texts) - len(set(texts)), "kept": len(texts),
                  "most_at_once": most[0], "same_lock": list(R2.__dict__.get("_locks", {})) == ["telegram"]}))
"""
        tg_add("Race check one")
        tg_add("Race check two")
        r = subprocess.run([sys.executable, "-c", tg_race, str(ROOT / "python" / "runtime.py"), tmp], capture_output=True, text=True, timeout=60, env=env)
        got = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 and r.stdout.strip() else {}
        check(got.get("dupes") == 0 and got.get("kept", 0) > 0 and 0 in (got.get("a"), got.get("b")),
              f"two scripts fetching Telegram at once take turns: no message is stored twice ({got or r.stderr[-200:]})")
        check(got.get("most_at_once") == 1 and got.get("same_lock") is True,
              f"three Telegram fetches at once share one lock and go one at a time, with the runtime made before the loop ({got or r.stderr[-200:]})")
        rt_path = str(ROOT / "python" / "runtime.py")
        r = subprocess.run([sys.executable, "-c", MEM_RACE, rt_path], capture_output=True, text=True, timeout=180, env=env)
        got = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 and r.stdout.strip() else {}
        check(got.get("kept") == 100 and got.get("unique") == 100 and got.get("tmp_left") == 0 and not got.get("errors"),
              f"four programs adding to one shared memory list at once keep all 100 items ({got or r.stderr[-200:]})")
        r = subprocess.run([sys.executable, "-c", HA_EVENTS, rt_path, str(ROOT / "tests")], capture_output=True, text=True, timeout=60, env=env)
        got = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 and r.stdout.strip() else {}
        check("refused the token" in (got.get("bad") or "") and got.get("fired") == [{"command": "on", "device": "Kitchen remote", "note": 70000, "type": "zha_event"}],
              f"Home Assistant events: a wrong token is said plainly, and a 70 KB event arrives whole ({got or r.stderr[-300:]})")
        r = subprocess.run([sys.executable, "-c", TG_MERGE, rt_path], capture_output=True, text=True, timeout=60, env=env)
        got = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 and r.stdout.strip() else {}
        check(got.get("new") == ["second"] and got.get("stored") == ["first", "second"] and got.get("offset") == 1003,
              f"a Telegram message another program already saved isn't stored or acted on twice ({got or r.stderr[-200:]})")
        (pathlib.Path(tmp) / "t_listen.py").write_text(EXTRA["t_listen"], encoding="utf-8")
        import socket
        with socket.socket() as so:
            so.bind(("127.0.0.1", 0))
            closed_port = so.getsockname()[1]
        knock = {}

        def knock_knock():
            time.sleep(5)
            try:
                socket.create_connection(("127.0.0.1", closed_port), timeout=2).close()
                knock["result"] = "open"
            except OSError:
                knock["result"] = "closed"
        threading.Thread(target=knock_knock, daemon=True).start()
        code_, out, err = drive([sys.executable, "-u", str(pathlib.Path(tmp) / "t_listen.py")],
                                dict(env, WEBHOOK_SECRET="", WEBHOOK_PORT=str(closed_port), RB_POLL_SECONDS="0.5"), tmp, timeout=9)
        check(knock.get("result") == "closed" and "doesn't listen for them" in out,
              f"without WEBHOOK_SECRET, the web request port isn't opened at all ({knock.get('result')})")
        check(re.search(r"Web requests, \d\d:\d\d: still not listening", out) is not None,
              "the not-listening notice is said again later (hourly), so it doesn't scroll away for good")

        print("Agent paths in Python")
        for name in ("t_ag_bad", "t_ag_repeat", "t_ag_out", "t_ag_ha", "t_ag_plan"):
            (pathlib.Path(tmp) / f"{name}.py").write_text(EXTRA[name], encoding="utf-8")
        run_ag = lambda name: drive([sys.executable, "-u", str(pathlib.Path(tmp) / f"{name}.py")],  # noqa: E731
                                    dict(env, FAKE_AGENT_SCRIPT=json.dumps(AGENT_SCRIPTS[name])), tmp)
        (pathlib.Path(tmp) / "t_typed.py").write_text(EXTRA["t_typed"], encoding="utf-8")
        code_, out, err = run_ag("t_typed")
        out = out.replace("\r\n", "\n")
        check(code_ == 0 and "▸ Agent step 1/6: hydration  [bad input]" in out and "should be a number, not \"lots\"" in out
              and "▸ Agent step 2/6: hydration  [done]" in out and "    Result:\n    70\n" in out,
              "t_typed.py refuses a wrong-typed input, then runs the corrected one" + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        for name in ("t_ag_calc", "t_ag_time", "t_ag_review", "t_ag_hist", "t_ag_file", "t_ag_page"):
            (pathlib.Path(tmp) / f"{name}.py").write_text(EXTRA[name], encoding="utf-8")
        code_, out, err = run_ag("t_ag_calc")
        out = out.replace("\r\n", "\n")
        check(code_ == 0 and all(f"    Result:\n    {w}\n" in out for w in ("(350 / 500) * 100 = 70", "round(1000 * 0.02, 1) = 20", "2^3^2 - -2^2 = 516",
                                                                       "1/3 = 0.333333333333", "min(3, 1) * sqrt(16) = 4"))
              and "▸ Agent step 6/10: calculate  [tool error]" in out and "I don't know “flour”" in out,
              "Python's calculate gives the same answers as the page" + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        code_, out, err = run_ag("t_ag_time")
        out = out.replace("\r\n", "\n")
        check(code_ == 0 and all(f"    Result:\n    {w}\n" in out for w in ("08:00 (next day)", "2026-10-11 08:00 (Sunday)", "22:30 (3 days earlier)", "21:45"))
              and "isn't a real date" in out and re.search(r"    Result:\n    \w+day \d{4}-\d\d-\d\d \d\d:\d\d\n", out),
              "Python's time_plus and current_time match the page" + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        code_, out, err = run_ag("t_ag_review")
        check(code_ == 0 and "▸ Check: short; friendly" in out and ("Passes every criterion." in out or "Doesn't pass yet. Problems:" in out),
              "Python's review_text asks a separate reviewer" + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        code_, out, err = run_ag("t_ag_hist")
        check(code_ == 0 and "▸ Agent step 1/6: device_history  [done]" in out, "Python's device_history reads Home Assistant's history"
              + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        code_, out, err = run_ag("t_ag_file")
        check(code_ == 0 and "(The agent wants a file: to check the hydration)" in out and "Order rye flour." in out,
              "Python's read_file asks for a file, saying why, and reads it" + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        code_, out, err = run_ag("t_ag_page")
        check(code_ == 0 and "▸ Agent step 1/6: read_page  [tool error]" in out and "not addresses on your own network" in out
              and "starting with http:// or https://" in out, "Python's read_page won't read addresses on your own network, or anything but web pages"
              + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        snippet = ("import json, sys; ns = {'__name__': 'rt', '__file__': sys.argv[1]}; exec(compile(open(sys.argv[1], encoding='utf-8').read(), 'rt', 'exec'), ns); "
                   "print(json.dumps(ns['page_text']('<html><head><title>Rye &amp; wheat</title><style>p{}</style></head><body><h1>Rye</h1>"
                   "<script>steal()</script><p>Holds&nbsp;water</p><!-- note --><p>Ferments fast</p></body></html>', 'text/html')))")
        r = subprocess.run([sys.executable, "-c", snippet, str(ROOT / "python" / "runtime.py")], env=env, capture_output=True, text=True, timeout=60)
        got = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else None
        check(got == ["Rye & wheat", "Rye\nHolds water\nFerments fast"], f"read_page keeps a page's words and drops its scripts, styles and tags ({got or r.stderr[-200:]})")
        (pathlib.Path(tmp) / "t_steps.py").write_text(EXTRA["t_steps"], encoding="utf-8")
        code_, out, err = run_ag("t_steps")
        out = out.replace("\r\n", "\n")
        statuses = [l.split(": ", 1)[1] for l in out.split("RESULT")[-1].splitlines() if l.startswith("status: ")]
        check(code_ == 0 and statuses == ["done", "done", "repeat", "answer"] and "tool: recall" in out,
              "t_steps.py gives the agent's steps as records" + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        check("▸ Agent summary  [4 steps]" in out and '    2. recall  [done]  {"name": "s"} → rye' in out and "    4. final answer  [answer]" in out,
              "Python sums up the agent's steps, one line each")
        check(re.search(r"▸ Agent step 1/6: remember  \[done\]\n(    .*\n)*    · Claude, \w+ · \d+\.\d s · \d+ in, \d+ out\n", out),
              "Python prints each step's model, time and exact tokens")
        code_, out, err = run_ag("t_ag_bad")
        check(code_ == 0 and "▸ Agent step 1/6  [unreadable]" in out and "▸ Agent: finished in 2 steps" in out, "t_ag_bad.py survives an unreadable reply" + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        code_, out, err = run_ag("t_ag_repeat")
        check(code_ == 0 and "▸ Agent step 2/6: recall  [repeat]" in out and "▸ Agent: stopped, repeating itself" in out, "t_ag_repeat.py stops an agent that repeats itself")
        code_, out, err = run_ag("t_ag_out")
        check(code_ == 0 and "▸ Agent step 2/2  [not a tool]" in out and "▸ Agent: out of steps  [best effort]" in out, "t_ag_out.py runs out of steps cleanly")
        (pathlib.Path(tmp) / "t_ag_memsearch.py").write_text(EXTRA["t_ag_memsearch"], encoding="utf-8")
        code_, out, err = run_ag("t_ag_memsearch")
        check(code_ == 0 and "Notes matching \u201chydration rye\u201d, best first" in out and "- rye loaf (saved " in out,
              "t_ag_memsearch.py: search_memory finds the note in Python too" + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        code_, out, err = run_ag("t_ag_plan")
        out = out.replace("\r\n", "\n")
        check(code_ == 0 and "▸ Agent plan  [planned]\n    1. save it\n    2. check it" in out and out.count("▸ Agent: plan changed") == 1
              and "▸ Agent: finished in 4 steps" in out, "t_ag_plan.py plans, changes its plan once, then finishes" + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        (pathlib.Path(tmp) / "t_ag_mcp.py").write_text(EXTRA["t_ag_mcp"], encoding="utf-8")
        mcp_log = pathlib.Path(tmp) / "mcp.log"
        code_, out, err = drive([sys.executable, "-u", str(pathlib.Path(tmp) / "t_ag_mcp.py")],
                                dict(env, FAKE_AGENT_SCRIPT=json.dumps(AGENT_SCRIPTS["t_ag_mcp"]), FAKE_MCP_LOG=str(mcp_log),
                                     MCP_BAKERY=f'"{sys.executable}" "{HERE / "fake_mcp.py"}" legacy'), tmp)
        out = out.replace("\r\n", "\n")
        loaves = (pathlib.Path(str(mcp_log) + ".loaves").read_text(encoding="utf-8") if pathlib.Path(str(mcp_log) + ".loaves").exists() else "")
        check(code_ == 0 and "MCP server \u201cbakery\u201d  [connected]" in out and "4 tools: list_loaves, add_loaf, fail, bake_in" in out
              and out.count("Allow this? let the agent use bakery_add_loaf") == 1 and "Allow this? let the agent use bakery_list_loaves" not in out
              and loaves == "Rye (900 g)\n",
              "t_ag_mcp.py starts its MCP server, asks before the tool that changes things (not the read-only one), and calls it"
              + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        before = len(ha_calls)
        code_, out, err = run_ag("t_ag_ha")
        check(code_ == 0 and "Allow this? let the agent use call_service" in out and any(c[0] == "light.turn_off" and c[1].get("entity_id") == "light.kitchen" for c in ha_calls[before:]),
              "t_ag_ha.py asks in the terminal, then turns the real (test) light off" + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        code_, out, err = drive([sys.executable, "-u", str(pathlib.Path(tmp) / "t_budget.py")], env, tmp)
        check(code_ != 0 and "reaches its budget of 5" in out, "t_budget.py stops at its budget, using the exact counts" + ("" if code_ else f": {out[-200:]}"))
        code_, out, err = drive([sys.executable, "-u", str(pathlib.Path(tmp) / "t_budget.py")], dict(env, RB_BUDGET="7"), tmp)
        check(code_ != 0 and "budget of 5" in out, "a budget block wins over budget in the settings")
        code_, out, err = drive([sys.executable, "-u", str(pathlib.Path(tmp) / "t_askfirst.py")], dict(env, RB_SAVE_LOG="yes"), tmp)
        saved = pathlib.Path(tmp) / "outputs" / "ask-first-note.txt"
        check(code_ == 0 and "Allow this? save" in out and saved.exists(), "t_askfirst.py asks before saving the file, then saves it" + ("" if code_ == 0 else f": {(err or out)[-300:]}"))
        logs = list((pathlib.Path(tmp) / "logs").glob("t_askfirst-*.md"))
        text = logs[0].read_text(encoding="utf-8") if logs else ""
        check("## 1. Ask first" in text and "## Result" in text and "Model calls:" in text, "save_log = yes writes the run's log to the logs folder")
        ini = EXPORTS["review"]["second-thought.ini"]
        check("[run]" in ini and "; budget = " in ini and "; save_log = yes" in ini, "the exported ini explains budget and save_log")
    services = {c[0] for c in ha_calls}
    check({"light.turn_off", "persistent_notification.create"} <= services and "lock.lock" in services,
          f"exported programs called Home Assistant ({len(ha_calls)} service calls: {', '.join(sorted(services))})")


def mcp_session(path, env, cwd, requests):
    """Talks to `python <path> --mcp` as an MCP client would: one JSON-RPC request per line, one answer per request."""
    proc = subprocess.Popen([sys.executable, "-u", str(path), "--mcp"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env=env, cwd=cwd, text=True, encoding="utf-8")
    answers = []
    try:
        for i, (method, params) in enumerate(requests):
            msg = {"jsonrpc": "2.0", "method": method, "params": params}
            if method.startswith("notifications/"):
                proc.stdin.write(json.dumps(msg) + "\n")
                proc.stdin.flush()
                continue
            msg["id"] = i + 1
            proc.stdin.write(json.dumps(msg) + "\n")
            proc.stdin.flush()
            answers.append(json.loads(proc.stdout.readline()))
        proc.stdin.close()
        proc.wait(timeout=60)
    finally:
        if proc.poll() is None:
            proc.kill()
    return proc.returncode, answers, proc.stderr.read()


def mcp_serve_tests(codes, env, tmp):
    """python my-program.py --mcp: the program as one MCP tool, for Claude and other agents."""
    print("Serving a program as an MCP tool")
    prog = pathlib.Path(tmp) / "mcp_review.py"
    prog.write_text(codes["review"][0], encoding="utf-8")
    call = ("tools/call", {"name": "mcp_review", "arguments": {"value": "rye"}})
    code, ans, err = mcp_session(prog, env, tmp, [("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test"}}),
                                                  ("notifications/initialized", {}), ("tools/list", {}), call, call, ("nope", {})])
    init, listed, first, second, unknown = ans
    tool = listed.get("result", {}).get("tools", [{}])[0]
    check(init.get("result", {}).get("protocolVersion") == "2025-06-18" and init["result"]["serverInfo"]["name"] == "mcp_review"
          and tool.get("name") == "mcp_review" and "value" in tool.get("inputSchema", {}).get("properties", {}),
          f"--mcp answers initialize and lists one tool named after the program, taking a value ({ans[:2]})")
    text = (first.get("result", {}).get("content") or [{}])[0].get("text", "")
    check(first.get("result", {}).get("isError") is False and len(text) > 20 and second.get("result", {}).get("isError") is False
          and "=== MCP call" in err and "===" not in json.dumps(ans),
          f"each call runs the program and gives back its result; the run log goes to stderr, never into the protocol ({first})")
    check(unknown.get("error", {}).get("code") == -32601 and code == 0, "an unknown method is an error, and the server ends when the client closes")

    asks = next((k for k, (c, _) in codes.items() if "R.ask_me(" in c and "START_SCRIPTS = [when_run" in c), None)
    if asks:
        path = pathlib.Path(tmp) / "mcp_asks.py"
        path.write_text(codes[asks][0], encoding="utf-8")
        _, ans, _ = mcp_session(path, env, tmp, [("tools/call", {"name": "mcp_asks", "arguments": {}})])
        res = ans[0].get("result", {})
        check(res.get("isError") is True and "no one to type it" in res["content"][0]["text"],
              f"a program that asks a question fails the call, with the reason ({asks}: {res})")
    def can(code):
        m = re.search(r"^CAN = (\{.*\})$", code, re.M)
        return json.loads(m.group(1)).get("can", []) if m else []
    acts = next(k for k, (c, _) in codes.items() if "telegram_send" in can(c) and "START_SCRIPTS = [when_run" in c)
    path = pathlib.Path(tmp) / "mcp_acts.py"
    path.write_text(codes[acts][0], encoding="utf-8")
    _, ans, _ = mcp_session(path, {k: v for k, v in env.items() if k != "RB_APPROVE"}, tmp, [("tools/call", {"name": "mcp_acts", "arguments": {}})])
    res = ans[0].get("result", {})
    check(res.get("isError") is True and "hasn't been allowed to without asking" in res["content"][0]["text"],
          f"a program that can act, never approved, refuses every call and says how to allow it ({acts}: {res})")
    r = subprocess.run([sys.executable, "-u", str(prog), "--doctor"], env=env, cwd=tmp, capture_output=True, encoding="utf-8", errors="replace", timeout=120)
    check("  ok    MCP tool: with --mcp, it serves one tool, “mcp_review”" in r.stdout, f"--doctor names the tool it would serve ({r.stdout[-300:]!r})")
