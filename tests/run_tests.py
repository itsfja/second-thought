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
import pathlib
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import fake_ha  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
VENDOR = HERE / "vendor"
FIX = HERE / "fixtures"
PAGE = (ROOT / "second-thought.html").read_text(encoding="utf-8")
DOC = '<!doctype html><html><head><meta charset=utf8><style>[hidden]{display:none!important}</style></head><body>' + PAGE + "</body></html>"

EXAMPLES = []  # read from the page's Example menu, so every example is always tested

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
  if (n === 'downloads') return { save:async r => { window.__saved.push(r.filename); return { status:'saved' }; } };
  if (n !== 'sample') return null;
  const lastText = input => Array.isArray(input) ? input[input.length - 1].content : input;
  const f = async (input, o = {}) => { const p = lastText(input);
    const t = p.includes('Reply with only the SVG') ? SVG : 'ANSWER(' + p.slice(0, 24).replace(/\n/g, ' ') + ')';
    o.onText && o.onText({ text:t, delta:t }); return { text:t, truncated:false }; };
  f.json = async input => { const p = lastText(input);
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
    env = dict(os.environ, PYTHONPATH=str(HERE / "fakeapi"), ANTHROPIC_API_KEY="test", GEMINI_API_KEY="test",
               HA_URL=ha_url, HA_TOKEN=fake_ha.TOKEN)
    with tempfile.TemporaryDirectory() as tmp:
        for ex, (code, _) in codes.items():
            path = pathlib.Path(tmp) / f"{ex}.py"
            path.write_text(code, encoding="utf-8")
            code_, stdout, stderr = drive([sys.executable, "-u", str(path)], env, tmp)
            r = SimpleNamespace(returncode=code_, stdout=stdout, stderr=stderr)
            ok = r.returncode == 0 and ("RESULT" in r.stdout or "Done" in r.stdout)
            check(ok, f"{ex}.py" + ("" if ok else f" (exit {r.returncode}): {(r.stderr or r.stdout)[-300:]}"))
            if ex == "gemini":
                done = [l for l in r.stdout.splitlines() if l.startswith("Done")]
                both = bool(done) and "Gemini:" in done[-1] and "Claude:" in done[-1]
                check(both, "gemini.py used both Claude and Gemini" + ("" if both else f": {done[-1] if done else r.stdout[-200:]}"))
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
