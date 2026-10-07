#!/usr/bin/env python3
"""End-to-end tests for Second Thought.

Runs the page in a headless browser with stand-ins for Claude, account storage
and downloads, then exports every example to Python and runs that too, against
a stand-in Anthropic SDK (tests/fakeapi). Nothing calls the real API.

    bash tests/setup.sh          # once
    python tests/run_tests.py    # every time
"""
import asyncio
import os
import shutil
import pathlib
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import fake_ha  # noqa: E402
import fake_llama  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
VENDOR = HERE / "vendor"
FIX = HERE / "fixtures"
PAGE = (ROOT / "second-thought.html").read_text(encoding="utf-8")
DOC = '<!doctype html><html><head><meta charset=utf8><style>[hidden]{display:none!important}</style></head><body>' + PAGE + "</body></html>"

for _stream in (sys.stdout, sys.stderr):  # Windows consoles: never crash printing a result
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

EXAMPLES = []  # read from the page's Example menu, so every example is always tested
EXPORTS = {}   # example -> {file name: text} of the exported zip

# Stand-ins for the page's runtime capabilities (Claude, storage, user, downloads).
MOCK = r"""(function(){
const store = {}, subs = [];
const fire = () => subs.forEach(([pre, fn]) => { const docs = Object.keys(store).filter(k => k.startsWith(pre + '/'))
  .map(k => ({ id:k.split('/').pop(), exists:true, data:() => store[k] })); fn({ docs, size:docs.length, empty:!docs.length, docChanges:() => [], metadata:{} }); });
const col = path => ({ limit(){ return this; }, onSnapshot(fn){ subs.push([path, fn]); setTimeout(fire, 10); return () => {}; },
  doc(id){ const k = path + '/' + id; return { set:async d => { store[k] = JSON.parse(JSON.stringify(d)); setTimeout(fire, 5); },
                                              delete:async () => { delete store[k]; setTimeout(fire, 5); } }; } });
const SVG = '<svg viewBox="0 0 100 80"><rect width="100" height="80" fill="#c96"/><circle cx="50" cy="40" r="20" fill="#fff"/></svg>';
let reviews = 0;
window.__saved = [];
window.claude = { use: async n => {
  if (n === 'db') return { collection:col };
  if (n === 'user') return { id:async () => 'test-user' };
  if (n === 'downloads') return { save:async r => { window.__saved.push(r.filename); (window.__savedData = window.__savedData || {})[r.filename] = r.data; return { status:'saved' }; } };
  if (n !== 'sample') return null;
  const lastText = input => Array.isArray(input) ? input[input.length - 1].content : input;
  const down = o => { if (window.__failTier && o && o.modelTier === window.__failTier) throw new Error('service unavailable (test)'); };
  const f = async (input, o = {}) => { down(o); const p = lastText(input);
    const t = p.includes('Reply with only the SVG') ? SVG : 'ANSWER(' + p.slice(0, 24).replace(/\n/g, ' ') + ')';
    o.onText && o.onText({ text:t, delta:t }); return { text:t, truncated:false }; };
  f.json = async (input, o = {}) => { down(o); const p = lastText(input);
    if (p.includes('"approved"')) { reviews++; return { approved:reviews % 2 === 0, problems:reviews % 2 ? ['too vague'] : [] }; }
    if (p.includes('JSON array of objects')) return [{ title:'A', score:4 }, { title:'B', score:9 }];
    if (p.includes('JSON array')) return ['idea one', 'idea two', 'idea three'];
    if (p.includes('"answer"')) return { answer:true };
    if (p.includes('"number"')) return { number:7 };
    if (p.includes('"score"')) return { score:6 };
    if (p.includes('"pick"')) return { pick:2, reason:'clearer' };
    return {}; };
  f.limits = async () => ({ maxPromptBytes:262144, images:{ maxCount:5, maxInputBytes:20000000, mediaTypes:['image/jpeg','image/png','image/webp','image/gif'] } });
  return f; } };
})();"""

failures = []


def check(cond, label):
    print(("  ok    " if cond else "  FAIL  ") + label)
    if not cond:
        failures.append(label)


async def route(r):
    u = r.request.url
    files = {
        "pdf.worker.min.js": VENDOR / "pdfjs-dist/package/build/pdf.worker.min.js",
        "pdf.min.js": VENDOR / "pdfjs-dist/package/build/pdf.min.js",
        "field-multilineinput": VENDOR / "field-multilineinput/package/dist/index.js",
        "blockly.min.js": VENDOR / "blockly/package/blockly.min.js",
    }
    for key, path in files.items():
        if key in u:
            return await r.fulfill(path=str(path), content_type="application/javascript")
    if u.startswith("http://test/"):
        return await r.fulfill(body=DOC, content_type="text/html")
    await r.abort()


async def run_program(pg, timeout_s=30):
    """Click Run, answer anything the program asks, wait for it to finish."""
    await pg.click("#run")
    answered_back = False
    for _ in range(int(timeout_s / 0.15)):
        await pg.wait_for_timeout(150)
        pick = await pg.query_selector(".pickfile")
        if pick:
            accept = await pick.get_attribute("accept") or ""
            await pick.set_input_files(str(FIX / ("crumb.png" if accept.startswith("image") else "notes.txt")))
            for _ in range(40):
                await pg.wait_for_timeout(100)
                if await pg.is_enabled(".ask button.primary"):
                    break
            await pg.click(".ask button.primary")
            continue
        ta = await pg.query_selector(".ask textarea")
        if ta:
            await ta.fill("rye bread")
            await pg.click(".ask button.primary")
            continue
        buttons = await pg.query_selector_all(".ask button")
        if buttons:
            labels = [await b.inner_text() for b in buttons]
            if "Send back" in labels and not answered_back:
                answered_back = True
                await buttons[labels.index("Send back")].click()
            else:
                await buttons[0].click()
            continue
        if await pg.is_enabled("#run"):
            break
    return await pg.inner_text("#status")


EXTRA = {}  # name -> exported Python for the new-feature programs below


def blk(type_, fields=None, inputs=None, nxt=None):
    b = {"type": type_}
    if fields:
        b["fields"] = fields
    if inputs:
        b["inputs"] = inputs
    if nxt:
        b["next"] = {"block": nxt}
    return b


def tx(t):
    return {"block": {"type": "text", "fields": {"TEXT": t}}}


def nm(n):
    return {"block": {"type": "math_number", "fields": {"NUM": n}}}


def val(b):
    return {"block": b}


def script(*steps):
    """A 'when Run is clicked' script running the given statement blocks in order."""
    for a, b in zip(steps, steps[1:]):
        a["next"] = {"block": b}
    start = {"type": "rb_start", "x": 20, "y": 20}
    if steps:
        start["next"] = {"block": steps[0]}
    return {"blocks": {"languageVersion": 0, "blocks": [start]}}


def add(value):
    return blk("rb_add_result", inputs={"TEXT": value})


async def load_state(pg, state):
    await pg.evaluate("s => { const w = Blockly.getMainWorkspace(); w.clear(); Blockly.serialization.workspaces.load(s, w); }", state)


async def run_and_answer(pg, answer_label, timeout_s=30):
    """Click Run and press the button labelled answer_label whenever the run asks."""
    await pg.click("#run")
    for _ in range(int(timeout_s / 0.15)):
        await pg.wait_for_timeout(150)
        for b in await pg.query_selector_all(".ask button"):
            if (await b.inner_text()) == answer_label:
                await b.click()
                break
        if await pg.is_enabled("#run"):
            break
    return await pg.inner_text("#status")


async def step_texts(pg):
    return await pg.eval_on_selector_all(".step", "e => e.map(x => [x.querySelector('.step-name').textContent, x.querySelector('.pill').textContent, x.querySelector('.step-body').innerText])")


async def save_program(pg, name, state):
    await load_state(pg, state)
    opened = not await pg.is_visible("#lib-name")
    if opened:
        await pg.click("#lib-toggle")
    await pg.fill("#lib-name", name)
    await pg.click("#lib-save")
    if "Replace" in (await pg.text_content("#lib-save")):
        await pg.click("#lib-save")
    await pg.wait_for_timeout(150)
    msg = await pg.text_content("#lib-msg")
    if opened:
        await pg.click("#lib-toggle")
    return msg


async def export_python(pg, name):
    opened = not await pg.is_visible("#io-name")
    if opened:
        await pg.click("#io-toggle")
    await pg.fill("#io-name", name)
    await pg.click("#io-py-show")
    code = await pg.input_value("#io-export-text")
    await pg.click("#io-py-show")
    if opened:
        await pg.click("#io-toggle")
    return code


async def new_feature_page_tests(pg):
    print("Token budget and usage")
    await pg.select_option("#example", "review")
    await pg.click("#load")
    await run_program(pg)
    usage = await pg.text_content(".result-usage") if await pg.query_selector(".result-usage") else ""
    status = await pg.inner_text("#status")
    check(usage.startswith("About ") and "estimated" in usage and "tokens" in status,
          f"the result shows an estimated token count ({status} | {usage[:60]})")
    budget = script(blk("rb_budget", inputs={"TOKENS": nm(5)}), add(val(blk("rb_ask", inputs={"TEXT": tx("first question")}))),
                    add(val(blk("rb_ask", inputs={"TEXT": tx("second question")}))))
    await load_state(pg, budget)
    status = await run_program(pg)
    steps = await step_texts(pg)
    stopped = [t for n, p_, t in steps if n == "Run stopped"]
    asked = sum(1 for n, *_ in steps if n.startswith("Ask Claude") or n.startswith("Claude"))
    check(status == "error" and stopped and "budget of 5" in stopped[0],
          f"a run over its budget stops before the next call ({status}: {stopped[0][:90] if stopped else steps[-1:]})")
    EXTRA["t_budget"] = await export_python(pg, "t_budget")
    budget_ok = script(blk("rb_budget", inputs={"TOKENS": nm(1000000)}), add(val(blk("rb_ask", inputs={"TEXT": tx("q")}))),
                       add(val(blk("rb_tokens_used"))))
    await load_state(pg, budget_ok)
    status = await run_program(pg)
    items = await pg.eval_on_selector_all(".result-text", "e => e.map(x => x.textContent)")
    check(status.startswith("done") and len(items) == 2 and items[1].isdigit() and int(items[1]) > 0,
          f"'tokens used so far' gives a number, and a roomy budget lets the run finish ({status}, {items[-1:]})")

    print("Saving the run log")
    await pg.click("#log-save")
    await pg.wait_for_timeout(300)
    saved = [n for n in await pg.evaluate("window.__saved") if "-log-" in n and n.endswith(".md")]
    data = (await pg.evaluate("window.__savedData"))[saved[-1]] if saved else ""
    check(bool(saved) and "## 1. Budget" in data and "took " in data and "## Result" in data and "Tokens: about" in data,
          f"Save log downloads the steps with timings and the result ({saved[-1:] or 'nothing saved'})")

    print("Ask me before")
    ask_first = script(blk("rb_ask_first", fields={"WHAT": "messages"}),
                       blk("rb_ha_notify", inputs={"TARGET": tx("persistent_notification"), "TEXT": tx("The door is open.")}),
                       blk("rb_ha_call", inputs={"SERVICE": tx("light.turn_off"), "ENTITY": tx("light.kitchen"), "DATA": tx("")}),
                       add(tx("carried on")))
    await load_state(pg, ask_first)
    status = await run_and_answer(pg, "Don't")
    steps = await step_texts(pg)
    names = [n for n, *_ in steps]
    check(status.startswith("done") and "Not done" in names and not any(n.startswith("Notification") for n in names)
          and "Home Assistant: light.turn_off" in names,
          f"saying no skips the message, but actions it doesn't cover still run ({status})")
    status = await run_and_answer(pg, "Allow")
    names = [n for n, *_ in await step_texts(pg)]
    check(status.startswith("done") and any(n.startswith("Notification") for n in names) and "Not done" not in names,
          f"saying yes sends the message ({status})")
    files_first = script(blk("rb_ask_first", fields={"WHAT": "files"}),
                         blk("rb_file_save", fields={"EXT": "txt"}, inputs={"VALUE": tx("hello from the test"), "NAME": tx("ask first note")}),
                         add(tx("saved it")))
    await load_state(pg, files_first)
    EXTRA["t_askfirst"] = await export_python(pg, "t_askfirst")

    print("Programs as blocks")
    sub = script(add(val(blk("rb_msg_value"))), add(tx("from sub")))
    msg = await save_program(pg, "shout", sub)
    check(msg.startswith("Saved"), f"a program can be saved to the list ({msg})")
    main = script(add(val(blk("rb_run_program", fields={"NAME": "shout"}, inputs={"VALUE": tx("hi")}))), add(tx("main done")))
    await load_state(pg, main)
    status = await run_program(pg)
    items = await pg.eval_on_selector_all(".result-text", "e => e.map(x => x.textContent)")
    check(status.startswith("done") and items == ["hi\n\nfrom sub", "main done"],
          f"'run program' gives back the program's result, and its own result stays separate ({status}, {items})")
    EXTRA["t_program"] = await export_python(pg, "t_program")
    check("async def program_shout" in EXTRA["t_program"] and 'R.run_program("shout", program_shout' in EXTRA["t_program"],
          "exported Python includes a copy of the saved program")
    loop = script(add(val(blk("rb_run_program", fields={"NAME": "loop"}, inputs={"VALUE": tx("x")}))))
    await save_program(pg, "loop", loop)
    await load_state(pg, loop)
    status = await run_program(pg)
    stopped = [t for n, p_, t in await step_texts(pg) if n == "Run stopped"]
    check(status == "error" and stopped and "runs itself" in stopped[0], f"a program that runs itself is stopped with a clear message ({status})")
    missing = script(add(val(blk("rb_run_program", fields={"NAME": "not saved anywhere"}, inputs={"VALUE": tx("")}))))
    await load_state(pg, missing)
    status = await run_program(pg)
    stopped = [t for n, p_, t in await step_texts(pg) if n == "Run stopped"]
    check(status == "error" and stopped and "no saved program" in stopped[0], "a missing program gets a clear message")
    with_broadcast = script(blk("rb_broadcast", inputs={"MSG": tx("go")}))
    await save_program(pg, "talker", with_broadcast)
    await load_state(pg, script(add(val(blk("rb_run_program", fields={"NAME": "talker"}, inputs={"VALUE": tx("")})))))
    status = await run_program(pg)
    stopped = [t for n, p_, t in await step_texts(pg) if n == "Run stopped"]
    check(status == "error" and stopped and "broadcasts" in stopped[0], "a saved program that broadcasts says why it can't run as a block")


async def page_tests():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await browser.new_page(viewport={"width": 1400, "height": 1000})
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.route("**/*", route)
        await pg.add_init_script(MOCK)
        await pg.goto("http://test/")
        await pg.wait_for_timeout(1500)

        EXAMPLES.extend(await pg.eval_on_selector_all("#example option", "e => e.map(o => o.value)"))
        print(f"Examples in the page ({len(EXAMPLES)})")
        for ex in EXAMPLES:
            await pg.select_option("#example", ex)
            await pg.click("#load")
            status = await run_program(pg)
            has_result = await pg.query_selector(".result") is not None
            check(status.startswith("done") and has_result, f"{ex}: {status}")
            if ex == "gemini":
                labelled = await pg.eval_on_selector_all(".step-name", "e => e.filter(x => x.textContent.includes('standing in for Gemini')).length")
                check(labelled > 0, f"page marks {labelled} step(s) as Claude standing in for Gemini")

        print("Home Assistant panel")
        await pg.select_option("#example", "ha_doorbell")
        await pg.click("#load")
        await pg.click("#ha-toggle")
        await pg.fill("#ha-filter", "doorbell")
        await pg.wait_for_timeout(200)
        inp = await pg.query_selector(".ha-state")
        await inp.fill("on")
        await inp.press("Enter")
        for _ in range(100):
            await pg.wait_for_timeout(150)
            if await pg.is_enabled("#run") and await pg.query_selector(".result"):
                break
        names = await pg.eval_on_selector_all(".step-name", "e => e.map(x => x.textContent)")
        check(any(n.startswith("Snapshot") for n in names) and await pg.query_selector(".result") is not None,
              "changing the doorbell in the panel runs the doorbell script")
        await pg.click("#ha-toggle")

        print("Block search")
        await pg.fill("#block-search", "record")
        await pg.wait_for_timeout(300)
        found = await pg.evaluate("Blockly.getMainWorkspace().getToolbox().getFlyout().getWorkspace().getTopBlocks(false).length")
        check(found >= 5, f"'record' finds {found} blocks")
        await pg.press("#block-search", "Escape")

        print("Backup models")
        await pg.click("#bk-toggle")
        await pg.select_option("#tier", "complex")
        await pg.select_option("#bk-1", "quick")
        await pg.evaluate("window.__failTier = 'complex'")
        await pg.select_option("#example", "review")
        await pg.click("#load")
        status = await run_program(pg)
        names = await pg.eval_on_selector_all(".step-name", "e => e.map(x => x.textContent)")
        check(status.startswith("done") and any(n.startswith("Backup") for n in names),
              f"when the primary fails, the backup answers ({status})")
        label = await pg.text_content("#bk-toggle")
        check(label == "Backups (1)", f"the Backups button shows how many are set ({label})")
        await pg.click("#io-toggle")
        await pg.click("#io-py-show")
        code = await pg.input_value("#io-export-text")
        check('BACKUPS = ["quick"]' in code, "exported Python lists the backup")
        await pg.click("#io-py-show")
        await pg.click("#io-toggle")
        await pg.select_option("#bk-1", "")
        await pg.evaluate("window.__failTier = 'complex'")
        await pg.select_option("#example", "review")
        await pg.click("#load")
        status = await run_program(pg)
        check(not status.startswith("done"), f"with no backups, a failing primary stops the run ({status})")
        await pg.evaluate("window.__failTier = null")
        await pg.select_option("#tier", "default")
        await pg.click("#bk-toggle")

        print("Python export and import")
        await pg.click("#io-toggle")
        codes = {}
        for ex in EXAMPLES:
            await pg.select_option("#example", ex)
            await pg.click("#load")
            n = await pg.evaluate("Blockly.getMainWorkspace().getAllBlocks(false).length")
            await pg.fill("#io-name", ex)
            await pg.click("#io-py-show")
            codes[ex] = (await pg.input_value("#io-export-text"), n)
            await pg.click("#io-py-show")
        print("Exported zip contents")
        for ex in ("review", "w_judges", "ha_doorbell", "ha_morning"):
            await pg.select_option("#example", ex)
            await pg.click("#load")
            await pg.fill("#io-name", ex)
            EXPORTS[ex] = {f["name"]: f["text"] for f in await pg.evaluate("window.__exportFiles()")}
            if ex == "ha_morning":
                import base64, io, zipfile
                zf = zipfile.ZipFile(io.BytesIO(base64.b64decode(await pg.evaluate("window.__zipBase64()"))))
                modes = {i.filename: (i.external_attr >> 16) & 0o777 for i in zf.infolist()}
                check(modes.get("run.sh") == 0o755 and modes.get("install-service.sh") == 0o755 and modes.get("second-thought.ini") == 0o644,
                      f"the zip marks the .sh scripts as runnable ({modes})")
                check(zf.read("second-thought.ini").decode() == EXPORTS[ex]["second-thought.ini"], "the zip unpacks to the same files")
        names = sorted(EXPORTS["review"])
        check(names == ["requirements.txt", "review.py", "run.bat", "run.sh", "second-thought.ini"], f"the zip holds the program, its settings, run.bat and run.sh ({', '.join(names)})")
        check(all(f in EXPORTS["ha_morning"] for f in ("run-on-schedule.bat", "run-on-schedule.sh", "install-service.sh", "install-startup.bat"))
              and "--schedule" in EXPORTS["ha_morning"]["run-on-schedule.sh"],
              "a program with timed scripts also gets run-on-schedule and install-startup / install-service scripts")
        check(all("\r" not in t for f, t in EXPORTS["ha_morning"].items() if f.endswith(".sh")), "the .sh scripts use Linux line endings")
        check(all("\r\n" in t and "\n" not in t.replace("\r\n", "") for f, t in EXPORTS["review"].items() if f.endswith((".bat", ".ini"))),
              "run.bat and second-thought.ini use Windows line endings")
        judges_ini = EXPORTS["w_judges"]["second-thought.ini"]
        check(all(k + " = " in judges_ini for k in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "DEEPSEEK_API_KEY", "XAI_API_KEY", "OPENAI_API_KEY")),
              "the ini asks for every key the program uses")
        check("LLAMA_BASE_URL" in judges_ini and "HA_TOKEN" not in judges_ini, "the ini only has the sections the program needs")
        check("HA_TOKEN = " in EXPORTS["ha_doorbell"]["second-thought.ini"], "a Home Assistant program's ini asks for HA_URL and HA_TOKEN")
        check(not any(l.strip().startswith("export ") for l in EXPORTS["w_judges"]["w_judges.py"].splitlines()[:40]),
              "the program's instructions no longer say 'export'")
        code, n = codes["brainstorm"]
        await pg.select_option("#example", "review")
        await pg.click("#load")
        await pg.fill("#io-paste", code)
        await pg.click("#io-load-paste")
        await pg.wait_for_timeout(300)
        n2 = await pg.evaluate("Blockly.getMainWorkspace().getAllBlocks(false).length")
        check(n == n2, f"exported Python imports back exactly ({n} blocks)")
        await pg.fill("#io-paste", code.replace("R.main(START_SCRIPTS", "R.main(START_SCRIPTS  # edited\n    ", 1))
        await pg.click("#io-load-paste")
        await pg.wait_for_timeout(300)
        choices = await pg.eval_on_selector_all("#io-choice button", "e => e.map(x => x.textContent)")
        check(len(choices) == 2, "edited export is noticed and offers a choice")

        await new_feature_page_tests(pg)

        check(not errors, "no page errors" + ("" if not errors else ": " + "; ".join(errors[:3])))
        await browser.close()
        return codes


PROMPTS = ("Approve? [y/n] > ", "Number > ", "Path > ", "Press Enter to continue > ", "> ")


def drive(cmd, env, cwd, timeout=120):
    """Run an exported program, answering whatever it asks in the terminal."""
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
                    reply = {"Approve? [y/n] > ": "y", "Number > ": "1", "Press Enter to continue > ": ""}.get(prompt, "rye bread for beginners")
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


def python_tests(codes):
    print("Exported Python runs")
    ha_url, ha_calls = fake_ha.start()
    llama_url, llama_calls = fake_llama.start()
    env = dict(os.environ, PYTHONPATH=str(HERE / "fakeapi"), PYTHONIOENCODING="utf-8", ANTHROPIC_API_KEY="test", GEMINI_API_KEY="test",
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
    with tempfile.TemporaryDirectory() as tmp:
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


def main():
    sync = subprocess.run([sys.executable, str(ROOT / "tools" / "sync.py"), "--check"], capture_output=True, text=True)
    print("Sources")
    check(sync.returncode == 0, sync.stdout.strip())
    if not (VENDOR / "blockly").exists():
        sys.exit("Run tests/setup.sh first.")
    codes = asyncio.run(page_tests())
    python_tests(codes)
    print()
    if failures:
        print(f"{len(failures)} check(s) failed.")
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()
