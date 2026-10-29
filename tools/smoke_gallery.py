#!/usr/bin/env python3
"""Runs every community gallery program once against the real models, with your own keys.

    python tools/smoke_test.py gallery                  # every program
    python tools/smoke_test.py gallery rain issue       # only programs whose names contain these words
    python tools/smoke_test.py gallery --budget 10000 --total 200000

Each program is exported to Python exactly as the page exports it, and its 'when Run is clicked' scripts are run once.
Only the models are real. Every connection (GitHub, Telegram, email, calendar, news feeds, Discord, Slack, Homey, Home
Assistant, MQTT, web pages) is the stand-in from tests/fake_services.py, and the folders a program looks in are made
up in a scratch folder, so nothing real is read, sent, posted, switched or charged, and none of your own files are seen.

Model keys come from the environment or a second-thought.ini, as for tools/smoke_test.py; nothing else in the ini
is passed on. A program that uses a service you have no key for is skipped, and the report says which key it needs.
Each program is stopped at --budget tokens (default 20,000), and no new program starts once the run has used --total
tokens (default 400,000). The report goes to smoke-gallery.md. Needs the test setup (tests/setup.sh) for the page.
"""
import argparse
import asyncio
import json
import os
import pathlib
import re
import shutil
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

# Settings that are only about the models, so the only ones passed on to the programs (with the base URLs that point
# a service somewhere else, and MODEL_ names that choose a different model).
MODEL_ENVS = {"ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_BASE_URL"}
USAGE = re.compile(r"([^·:]+?): ([\d,]+) tokens in, ([\d,]+) out")


def model_envs(providers):
    names = set(MODEL_ENVS)
    for name, pv in providers.items():
        if pv.get("key_env"):
            names.add(pv["key_env"])
        if pv.get("base_env"):
            names.add(pv["base_env"])
    return names


def needs(code, providers):
    """The model services a program uses (the CAN line its export ends with), as (service, key setting, have it)."""
    m = re.search(r'^CAN = (\{.*\})$', code, re.M)
    services = json.loads(m.group(1)).get("services", []) if m else ["Claude"]
    out = []
    for s in services:
        if s == "Claude":
            out.append((s, "ANTHROPIC_API_KEY", bool(os.environ.get("ANTHROPIC_API_KEY"))))
        elif s == "Gemini":
            out.append((s, "GEMINI_API_KEY", bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))))
        elif s in providers:
            pv = providers[s]
            env = pv["key_env"] if pv.get("signup") else pv["base_env"]
            out.append((s, env, bool(os.environ.get(env))))
    return out


def make_home(home):
    """The folders gallery programs look in, filled with a few made-up files."""
    fix = ROOT / "tests" / "fixtures"
    for folder in ("Bank statements", "Pictures/Family", "Receipts", "Recipes"):
        d = home / folder
        d.mkdir(parents=True, exist_ok=True)
        shutil.copy(fix / "notes.txt", d / "notes.txt")
        shutil.copy(fix / "hello.pdf", d / "statement-or-receipt.pdf")
        shutil.copy(fix / "crumb.png", d / "crumb-shot.png")
    (home / "Recipes" / "grandmas-loaf.txt").write_text(
        "Grandma's loaf\n2 lb strong white flour\n1 pint warm water\n1 oz fresh yeast\n2 tsp salt\n"
        "Mix, knead 10 minutes, rise until doubled, shape, bake hot for 40 minutes.\n", encoding="utf-8")


async def export_all(names):
    from e2e.common import MOCK, async_playwright, export_python, paste, route
    codes = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await browser.new_page(viewport={"width": 1400, "height": 1000})
        await pg.route("**/*", route)
        await pg.add_init_script(MOCK)
        await pg.goto("http://test/")
        await pg.wait_for_timeout(1500)
        for name in names:
            await pg.click("#io-toggle")
            await paste(pg, (ROOT / "gallery" / f"{name}.json").read_text(encoding="utf-8"))
            await pg.click("#io-load-paste")
            await pg.click("#io-toggle")
            codes[name] = await export_python(pg, name)
        await browser.close()
    return codes


def stand_ins(env, use_fake_models, providers):
    """Starts the stand-in services and points the connections at them (and the models too, for the tests)."""
    import fake_ha
    import fake_mqtt
    import fake_services
    ha_url, _ = fake_ha.start()
    svc_url, svc_log, _tg_add, imap_port, smtp_port = fake_services.start()
    _broker, mqtt_port = fake_mqtt.start(retained={"zigbee2mqtt/leak_sensor_sink": '{"water_leak": false, "battery": 87}'})
    env.update(HA_URL=ha_url, HA_TOKEN=fake_ha.TOKEN, HOMEY_URL=svc_url + "/homey", HOMEY_API_KEY=fake_services.HOMEY_KEY,
               MQTT_HOST="127.0.0.1", MQTT_PORT=str(mqtt_port), MQTT_USERNAME=fake_mqtt.USER, MQTT_PASSWORD=fake_mqtt.PASSWORD,
               DISCORD_API_URL=svc_url + "/discord", DISCORD_BOT_TOKEN=fake_services.DISCORD_TOKEN, DISCORD_CHANNEL_ID=fake_services.DISCORD_CHANNEL,
               SLACK_API_URL=svc_url + "/slack", SLACK_BOT_TOKEN=fake_services.SLACK_TOKEN, SLACK_CHANNEL_ID=fake_services.SLACK_CHANNEL,
               RB_FEEDS=f"{svc_url}/feeds/baking.rss {svc_url}/feeds/tech.atom", GITHUB_API_URL=svc_url + "/gh",
               GITHUB_TOKEN=fake_services.GH_TOKEN, TELEGRAM_API_URL=svc_url + "/tg", TELEGRAM_BOT_TOKEN=fake_services.TG_TOKEN,
               TELEGRAM_CHAT_ID=str(fake_services.TG_CHAT), EMAIL_ADDRESS=fake_services.MAIL_USER, EMAIL_PASSWORD=fake_services.MAIL_PASS,
               EMAIL_IMAP_HOST="127.0.0.1", EMAIL_SMTP_HOST="127.0.0.1", EMAIL_IMAP_PORT=str(imap_port), EMAIL_SMTP_PORT=str(smtp_port),
               EMAIL_SSL="no", CALENDAR_URL=svc_url + "/calendar.ics", RB_LOCAL_PAGES="yes")
    if use_fake_models:
        import fake_llama
        llama_url, _ = fake_llama.start()
        env.update(PYTHONPATH=str(ROOT / "tests" / "fakeapi"), ANTHROPIC_API_KEY="test", GEMINI_API_KEY="test")
        for name, pv in providers.items():
            env[pv["base_env"]] = llama_url.rsplit("/v1", 1)[0] if name == "Perplexity" else llama_url
            env[pv["key_env"]] = "test"
    return svc_url, svc_log


def first_lines(stdout, n=6):
    """The program's answer: the lines after its RESULT heading (or the end of what it printed), and any FAIL lines."""
    lines = [l.rstrip() for l in stdout.splitlines() if l.strip() and not set(l.strip()) <= set("=─-")]
    done = next((i for i in range(len(lines) - 1, -1, -1) if lines[i].startswith("Done")), len(lines))
    head = next((i for i in range(done - 1, -1, -1) if lines[i].strip() == "RESULT"), None)
    body = lines[head + 1:done][:n] if head is not None else lines[:done][-n:]
    fails = [l for l in lines if l.lstrip().startswith("FAIL") and l not in body]
    return [l[:160] for l in body + fails[:3]]


def main(argv, providers, use_fake_models=False, report_path=None):
    ap = argparse.ArgumentParser(prog="smoke_test.py gallery")
    ap.add_argument("only", nargs="*", help="only programs whose names contain these words")
    ap.add_argument("--budget", type=int, default=20000, help="tokens each program may use (default 20,000)")
    ap.add_argument("--total", type=int, default=400000, help="no new program starts after this many tokens (default 400,000)")
    ap.add_argument("--timeout", type=int, default=300, help="seconds each program may run (default 300)")
    ap.add_argument("--stand-ins", action="store_true", help=argparse.SUPPRESS)  # the test models too: a test of this tool
    ap.add_argument("--report", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    use_fake_models = use_fake_models or args.stand_ins
    report_path = report_path or args.report
    names = sorted(p.stem for p in (ROOT / "gallery").glob("*.json"))
    names = [n for n in names if not args.only or any(w.lower() in n for w in args.only)]
    if not names:
        print("No gallery program matches " + " ".join(args.only))
        return 1
    print(f"Second Thought: running {len(names)} gallery program(s) against the " + ("stand-in" if use_fake_models else "real") + " models\n", flush=True)
    print("Exporting from the page…", flush=True)
    codes = asyncio.run(export_all(names))

    from e2e.python_export import drive
    keep = model_envs(providers)
    base = {k: v for k, v in os.environ.items() if k in keep or k.startswith("MODEL_")}
    for k in ("PATH", "SYSTEMROOT", "TEMP", "TMP", "LANG", "LC_ALL", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE",
              "HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "https_proxy", "http_proxy", "no_proxy"):
        if os.environ.get(k):
            base[k] = os.environ[k]
    rows, total = [], 0
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        home = tmp / "home"
        make_home(home)
        (tmp / "empty.ini").write_text("", encoding="utf-8")
        env = dict(base, HOME=str(home), USERPROFILE=str(home), SECOND_THOUGHT_INI=str(tmp / "empty.ini"),
                   RB_APPROVE="no", RB_LANGUAGE="en", RB_STREAM="no", RB_SAVE_LOG="no", PYTHONIOENCODING="utf-8",
                   RB_BUDGET=str(args.budget))
        svc_url, svc_log = stand_ins(env, use_fake_models, providers)
        for name in names:
            code = codes[name].replace("https://example.com/", svc_url + "/feeds/page.html?")
            if total >= args.total:
                rows.append((name, "SKIP", 0, 0, [f"the run had used {total:,} tokens (--total {args.total:,})"]))
                print(f"  SKIP  {name}: over the total", flush=True)
                continue
            missing = [(s, k) for s, k, have in needs(code, providers) if not have]
            if missing and not use_fake_models:
                rows.append((name, "SKIP", 0, 0, ["needs " + ", ".join(f"{s} ({k})" for s, k in missing)]))
                print(f"  SKIP  {name}: needs " + ", ".join(k for _, k in missing), flush=True)
                continue
            path = tmp / f"{name.replace('-', '_')}.py"
            path.write_text(code, encoding="utf-8")
            start = time.time()
            rc, out, err = drive([sys.executable, "-u", str(path)], env, str(tmp), timeout=args.timeout)
            secs = time.time() - start
            done = [l for l in out.splitlines() if l.startswith("Done")]
            used = sum(int(a.replace(",", "")) + int(b.replace(",", "")) for _, a, b in USAGE.findall(done[-1])) if done else 0
            stopped = re.search(r"has used ([\d,]+) tokens", out)
            used = used or (int(stopped.group(1).replace(",", "")) if stopped else 0)
            total += used
            if rc == 0 and done:
                status, lines = "PASS", first_lines(out)
            elif "budget" in (out + err).lower() and "token" in (out + err).lower():
                status, lines = "BUDGET", first_lines(out)
            else:
                status, lines = "FAIL", [l[:160] for l in (err or out).strip().splitlines()[-4:]]
            rows.append((name, status, used, secs, lines))
            print(f"  {status:<6} {name}: {used:,} tokens, {secs:.0f}s", flush=True)
    sent = {k: len(v) for k, v in svc_log.items() if isinstance(v, list) and v}
    write_report(report_path or ROOT / "smoke-gallery.md", rows, total, args, sent, use_fake_models)
    fails = sum(r[1] == "FAIL" for r in rows)
    print(f"\n{sum(r[1] == 'PASS' for r in rows)} finished, {fails} failed, {sum(r[1] == 'BUDGET' for r in rows)} stopped by the budget, "
          f"{sum(r[1] == 'SKIP' for r in rows)} skipped. {total:,} tokens. Report: {report_path or 'smoke-gallery.md'}")
    return 1 if fails else 0


def write_report(path, rows, total, args, sent, fake):
    words = {"PASS": "finished", "FAIL": "failed", "BUDGET": "stopped by the budget", "SKIP": "skipped"}
    out = ["# Gallery programs against " + ("the stand-in models" if fake else "the real models"), "",
           f"Run {time.strftime('%Y-%m-%d %H:%M')}" + (" with the stand-in models (a test of this tool)" if fake else "")
           + f". Budget {args.budget:,} tokens a program; {total:,} tokens used in all.", "",
           "| Program | Result | Tokens | Seconds |", "|---|---|---:|---:|"]
    out += [f"| {n} | {words[s]} | {u:,} | {t:.0f} |" for n, s, u, t, _ in rows]
    out += ["", "What the stand-in services were sent: " + (", ".join(f"{k} {v}" for k, v in sent.items()) or "nothing"), ""]
    for n, s, _, _, lines in rows:
        out += [f"## {n}: {words[s]}", "", "```", *(lines or ["(nothing printed)"]), "```", ""]
    pathlib.Path(path).write_text("\n".join(out), encoding="utf-8")
