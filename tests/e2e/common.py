"""Shared setup for the end-to-end tests: paths, the page with stand-ins for Claude, the CDN stand-in, check(),
and helpers for building and running programs."""
import asyncio
import base64
import datetime
import re
import json
import os
import shutil
import pathlib
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
import urllib.error
from types import SimpleNamespace

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))  # tests/, for the fake services
import fake_ha  # noqa: E402
import fake_llama  # noqa: E402
import fake_services  # noqa: E402
import fake_mqtt  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent.parent  # tests/
ROOT = HERE.parent
VENDOR = HERE / "vendor"
FIX = HERE / "fixtures"
# Fonts a language names for a script most computers lack, served from tests/vendor in place of Google Fonts:
# family -> (its file, a character of that script, a regex for that script, whether exported programs print a transcription instead).
FONTS = {
    "Noto Sans Linear B": (VENDOR / "@fontsource/noto-sans-linear-b/package/files/noto-sans-linear-b-linear-b-400-normal.woff2",
                           "\U00010000", "[\\u{10000}-\\u{100FF}]", True),
    "Noto Sans Devanagari": (VENDOR / "@fontsource/noto-sans-devanagari/package/files/noto-sans-devanagari-devanagari-400-normal.woff2",
                             "\u0915", "[\\u0900-\\u097F]", False),
    "Noto Sans Cuneiform": (VENDOR / "@fontsource/noto-sans-cuneiform/package/files/noto-sans-cuneiform-cuneiform-400-normal.woff2",
                            "\U00012000", "[\\u{12000}-\\u{123FF}]", True),
}
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
  const f = async (input, o = {}) => { down(o); const p = lastText(input); (window.__textPrompts = window.__textPrompts || []).push(p);
    const t = p.includes('Reply with only the SVG') ? SVG : 'ANSWER(' + p.slice(0, 24).replace(/\n/g, ' ') + ')';
    const cut = (window.__truncate || 0) > 0; if (cut) window.__truncate--;
    o.onText && o.onText({ text:t, delta:t }); return { text:t, truncated:cut }; };
  f.json = async (input, o = {}) => { down(o); const p = lastText(input);
    (window.__jsonPrompts = window.__jsonPrompts || []).push(p);
    if (window.__jsonScript && window.__jsonScript.length) {  // a test's script of replies for JSON calls; "BAD" can't be read
      const r = window.__jsonScript.shift();
      if (r === 'BAD') throw { code:'invalid_json', message:'test: unreadable', text:'this is not json at all' };
      return JSON.parse(JSON.stringify(r));
    }
    if (p.includes('one step at a time, using tools')) {
      (window.__agentPrompts = window.__agentPrompts || []).push(p);
      const steps = (p.match(/\nStep \d+: /g) || []).length;
      if (window.__agentScript) {  // a test's script: one reply per step; "BAD" is an unreadable reply
        const r = window.__agentScript[Math.min(steps, window.__agentScript.length - 1)];
        if (r === 'BAD') throw { code:'invalid_json', message:'test: unreadable', text:'this is not json at all' };
        return JSON.parse(JSON.stringify(r));
      }
      const m = /TOOLS:\n- ([a-z0-9_]+)\(([^)]*)\)/.exec(p);
      if (steps || !m || p.includes('This is your last step')) return { done:true, answer:'AGENT ANSWER after ' + steps + ' step(s)' };
      const input = {}; m[2].split(',').map(x => x.trim()).filter(Boolean).forEach((k, i) => input[k] = String(500 + i * 350));
      return Object.assign({ tool:m[1], input, why:'test' }, p.includes('Planning is on') ? { plan:['test plan step'] } : {});
    }
    if (p.includes('"approved"')) { reviews++; return { approved:reviews % 2 === 0, problems:reviews % 2 ? ['too vague'] : [] }; }
    if (p.includes('"items": [<objects')) return [{ title:'A', score:4 }, { title:'B', score:9 }];
    if (p.includes('"items": [<short strings>]')) return ['idea one', 'idea two', 'idea three'];
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
        "keyboard-navigation": VENDOR / "keyboard-navigation/package/dist/index.js",
    }
    for family, (font_file, *_) in FONTS.items():  # a script's font, for the language that names it
        slug = family.lower().replace(" ", "-")
        if "fonts.googleapis.com/css2?family=" + family.replace(" ", "+") in u:
            return await r.fulfill(body=f"@font-face{{font-family:'{family}';src:url(https://fonts.gstatic.com/test/{slug}.woff2) format('woff2')}}",
                                   content_type="text/css")
        if u == f"https://fonts.gstatic.com/test/{slug}.woff2":
            return await r.fulfill(path=str(font_file), content_type="font/woff2")
    m = re.search(r"/blockly@[^/]+/msg/([a-z-]+)\.js$", u)
    if m and (VENDOR / "blockly/package/msg" / (m.group(1) + ".js")).exists():  # Blockly's own words for a language
        return await r.fulfill(path=str(VENDOR / "blockly/package/msg" / (m.group(1) + ".js")), content_type="application/javascript")
    for key, path in files.items():
        if key in u:
            return await r.fulfill(path=str(path), content_type="application/javascript")
    m = re.fullmatch(r"http://test/lang/([a-z]+)\.js", u)
    if m:  # a language's words, published next to the page
        path = ROOT / "lang" / (m.group(1) + ".js")
        return await (r.fulfill(path=str(path), content_type="application/javascript") if path.is_file() else r.fulfill(status=404, body=""))
    if u.startswith("http://test/"):
        return await r.fulfill(body=DOC, content_type="text/html")
    await r.abort()


async def paste(pg, text):
    """Puts text in the import box. Setting it directly is quicker than typing a whole exported program in."""
    await pg.evaluate("v => { const t = document.getElementById('io-paste'); t.value = v; t.dispatchEvent(new Event('input')); }", text)


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


# Several programs sharing memory.json and the Telegram store (issue #25).
MEM_RACE = r"""
import json, os, subprocess, sys, tempfile
# Four programs at once each add 25 items to one remembered list in a shared memory file: all 100 must be kept.
rt, d = sys.argv[1], tempfile.mkdtemp()
mem = os.path.join(d, "shared-memory.json")
worker = r'''
import os, sys
ns = {"__name__": "rt", "__file__": sys.argv[1]}
exec(compile(open(sys.argv[1], encoding="utf-8").read(), "rt", "exec"), ns)
R = ns["Runtime"](); R.reset(); R.log = lambda *a, **k: None
for i in range(25):
    R.remember_add(f"{sys.argv[2]}-{i}", "shared list", "permanent")
'''
env = dict(os.environ, RB_MEMORY_FILE=mem)
ps = [subprocess.Popen([sys.executable, "-c", worker, rt, f"p{n}"], env=env, stderr=subprocess.PIPE, text=True) for n in range(4)]
errs = [p.communicate(timeout=120)[1] for p in ps]
data = json.load(open(mem, encoding="utf-8"))
items = data["shared list"]["value"]
left = [f for f in os.listdir(d) if f.endswith(".tmp")]
print(json.dumps({"kept": len(items), "unique": len(set(items)), "tmp_left": len(left), "errors": [e[-200:] for e in errs if e.strip()]}))
"""
TG_MERGE = r"""
import asyncio, json, os, sys, tempfile
# Another program sharing the bot saved message 1001 while this one waited on Telegram: this one adds only 1002.
os.environ["TELEGRAM_CHAT_ID"] = "42"
ns = {"__name__": "rt", "__file__": sys.argv[1]}
exec(compile(open(sys.argv[1], encoding="utf-8").read(), "rt", "exec"), ns)
ns["TELEGRAM_FILE"] = os.path.join(tempfile.mkdtemp(), "tg.json")
R = ns["Runtime"](); R.reset()
msg = lambda uid, text: {"update_id": uid, "message": {"text": text, "date": uid, "chat": {"id": 42}, "from": {"first_name": "Francis"}}}
async def fake_tg(method, params=None, wait=0):
    # while "waiting", the other program saves 1001
    json.dump({"offset": 1002, "messages": [{"text": "first", "sender": "Francis", "chat": "42", "chat_name": "", "date": 1001, "update_id": 1001}]},
              open(ns["TELEGRAM_FILE"], "w", encoding="utf-8"))
    return [msg(1001, "first"), msg(1002, "second")]
R._tg = fake_tg
new = asyncio.run(R.tg_fetch())
store = json.load(open(ns["TELEGRAM_FILE"], encoding="utf-8"))
print(json.dumps({"new": [m["text"] for m in new], "stored": [m["text"] for m in store["messages"]], "offset": store["offset"]}))
"""

# Home Assistant events over the WebSocket: a wrong token is said plainly, and a big event (over 64 KB) arrives whole (issue #34).
HA_EVENTS = r"""
import asyncio, json, os, sys
sys.path.insert(0, sys.argv[2])
import fake_ha
url, _ = fake_ha.start()
os.environ.update(HA_URL=url, HA_TOKEN="wrong-token")
ns = {"__name__": "rt", "__file__": sys.argv[1]}
exec(compile(open(sys.argv[1], encoding="utf-8").read(), "rt", "exec"), ns)
R = ns["Runtime"](); R.reset()
out = {}
async def bad():
    try:
        await R._listen_ha_event([("anything|", None)])
    except ns["RunError"] as e:
        return str(e)
out["bad"] = asyncio.run(asyncio.wait_for(bad(), 15))
ns["HA_TOKEN"] = fake_ha.TOKEN
fired = []
R._fire = lambda fn, rec, label: fired.append(rec)
async def good():
    task = asyncio.ensure_future(R._listen_ha_event([("zha_event|kitchen remote", None)]))
    for _ in range(200):
        if fake_ha.subscribers:
            break
        await asyncio.sleep(0.05)
    await asyncio.to_thread(fake_ha.fire_event, "zha_event", {"device_name": "Hall remote", "command": "on"})
    await asyncio.to_thread(fake_ha.fire_event, "zha_event", {"device_name": "Kitchen remote", "command": "on", "note": "x" * 70000})
    for _ in range(200):
        if fired:
            break
        await asyncio.sleep(0.05)
    task.cancel()
asyncio.run(good())
out["fired"] = [{"command": r.get("command"), "device": r.get("device_name"), "note": len(r.get("note", "")), "type": r.get("event_type")} for r in fired]
print(json.dumps(out))
"""

# A forward proxy that redirects a public page to this computer: get_url must refuse the second hop (issue #23).
PROXY_REDIRECT = r"""
import json, os, socket, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
for k in list(os.environ):
    if k.lower().endswith("_proxy"):
        del os.environ[k]
seen = []
class Proxy(BaseHTTPRequestHandler):  # a forward proxy that sends a public page somewhere on this computer
    def log_message(self, *a): pass
    def do_GET(self):  # the program sends the proxy the checked address, with the name as Host
        seen.append(self.headers.get("Host", "") + " " + self.path)
        if "public.example" in self.headers.get("Host", ""):
            self.send_response(302); self.send_header("Location", f"http://127.0.0.1:{port}/admin"); self.send_header("Content-Length", "0"); self.end_headers()
        else:
            self.send_response(200); self.send_header("Content-Length", "6"); self.end_headers(); self.wfile.write(b"secret")
srv = ThreadingHTTPServer(("127.0.0.1", 0), Proxy); threading.Thread(target=srv.serve_forever, daemon=True).start()
port = srv.server_address[1]
os.environ["http_proxy"] = f"http://127.0.0.1:{port}"
ns = {"__name__": "rt", "__file__": sys.argv[1]}
exec(compile(open(sys.argv[1], encoding="utf-8").read(), "rt", "exec"), ns)
real_lookup = socket.getaddrinfo
socket.getaddrinfo = lambda host, *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.215.14", 80))] if host == "public.example" else real_lookup(host, *a, **k)
out = {}
try:
    ns["get_url"]("http://public.example/start")
    out["proxied"] = "fetched"
except ns["RunError"] as e:
    out["proxied"] = str(e)
out["admin_hits"] = sum(1 for p in seen if p.endswith("/admin"))
out["start_hits"] = sum(1 for p in seen if "public.example" in p)
print(json.dumps(out))
"""

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


def agent_prog(tools, steps=6, goal="Test goal", plan=False):
    chain = None
    for t in reversed(tools):
        b = blk("rb_agent_builtin", fields={"KIND": t}) if isinstance(t, str) else t
        if chain:
            b["next"] = {"block": chain}
        chain = b
    inputs = {"GOAL": tx(goal), "STEPS": nm(steps)}
    if chain:
        inputs["TOOLS"] = {"block": chain}
    return script(blk("rb_agent", fields={"PLAN": "TRUE" if plan else "FALSE"}, inputs=inputs), blk("rb_result"))


async def agent_run(pg, tools, replies, steps=6, answer=None, export=None, plan=False):
    """Runs an agent whose stand-in Claude gives these replies in turn. Returns (status, steps, result texts)."""
    await load_state(pg, agent_prog(tools, steps, plan=plan))
    await pg.evaluate("r => { window.__agentScript = r; window.__agentPrompts = []; }", replies)
    try:
        status = await (run_and_answer(pg, answer) if answer else run_program(pg))
    finally:
        await pg.evaluate("window.__agentScript = null")
    if export:
        EXTRA[export] = await export_python(pg, export)
        AGENT_SCRIPTS[export] = replies
    items = await pg.eval_on_selector_all(".result-text", "e => e.map(x => x.textContent)")
    return status, await step_texts(pg), items


AGENT_SCRIPTS = {}  # exported program -> the replies its stand-in Claude gives in Python
EXAMPLE_A_TOOL = {}  # the 'Agent with your own tool' example, as the page builds it


def var(vid, name):
    return {"id": vid, "name": name}


def setv(vid, value):
    return blk("variables_set", fields={"VAR": {"id": vid}}, inputs={"VALUE": value})


def getv(vid):
    return val({"type": "variables_get", "fields": {"VAR": {"id": vid}}})


def join(*parts):
    return val({"type": "text_join", "extraState": {"itemCount": len(parts)}, "inputs": {f"ADD{i}": x for i, x in enumerate(parts)}})


def with_vars(state, *vs):
    state["variables"] = list(vs)
    return state


def review_loop_prog(rounds=3):
    """The draft is "v1", "v2", ... one per round, so the test can see which one is kept."""
    fix = blk("math_change", fields={"VAR": {"id": "v_n"}}, inputs={"DELTA": nm(1)},
              nxt=blk("rb_set_draft", inputs={"TEXT": join(tx("v"), getv("v_n"))}))
    return with_vars(script(setv("v_n", nm(1)), blk("rb_set_draft", inputs={"TEXT": join(tx("v"), getv("v_n"))}),
                            blk("rb_reflect", inputs={"CRITERIA": tx("clear"), "ROUNDS": nm(rounds), "FIX": {"block": fix}}),
                            add(val(blk("rb_draft"))), add(val(blk("rb_problems")))), var("v_n", "n"))


def checkpoint_prog():
    return with_vars(script(blk("rb_set_draft", inputs={"TEXT": tx("good")}), setv("v_x", nm(1)), add(tx("r1")),
                            blk("rb_checkpoint_save", fields={"NAME": "cp"}),
                            blk("rb_set_draft", inputs={"TEXT": tx("bad")}), setv("v_x", nm(2)), add(tx("r2")),
                            blk("rb_checkpoint_restore", fields={"NAME": "cp"}),
                            blk("rb_set_draft", inputs={"TEXT": tx("worse")}),
                            blk("rb_checkpoint_restore", fields={"NAME": "CP"}),
                            add(join(val(blk("rb_draft")), tx(" "), getv("v_x")))), var("v_x", "x"))


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
