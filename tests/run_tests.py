#!/usr/bin/env python3
"""End-to-end tests for Second Thought.

Runs the page in a headless browser with stand-ins for Claude, account storage
and downloads, then exports every example to Python and runs that too, against
a stand-in Anthropic SDK (tests/fakeapi). Nothing calls the real API.

    bash tests/setup.sh          # once
    python tests/run_tests.py    # every time
"""
import asyncio
import re
import json
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

    print("Structured replies")
    num_prog = lambda *qs: script(*[add(val(blk("rb_ask_number", inputs={"TEXT": tx(q)}))) for q in qs])  # noqa: E731

    async def scripted(state, replies, answer=None):
        await load_state(pg, state)
        await pg.evaluate("r => { window.__jsonScript = r; window.__jsonPrompts = []; }", replies)
        try:
            status = await (run_and_answer(pg, answer) if answer else run_program(pg))
        finally:
            await pg.evaluate("window.__jsonScript = null")
        return (status, await step_texts(pg), await pg.eval_on_selector_all(".result-text", "e => e.map(x => x.textContent)"),
                await pg.evaluate("window.__jsonPrompts"))

    status, steps, items, prompts = await scripted(num_prog("How many grams in a cup of flour?"), ["BAD", {"number": 7}])
    rep = [t for n, p_, t in steps if n == "Unreadable reply"]
    check(status.startswith("done") and items == ["7"] and rep and "readable JSON" in rep[0] and len(prompts) == 2 and "couldn't be used" in prompts[1],
          f"an unreadable reply is sent back once with the problem, and the corrected one is used ({items})")
    status, steps, items, prompts = await scripted(num_prog("q"), [{"num": 7}, {"number": "8"}])
    rep = [t for n, p_, t in steps if n == "Unreadable reply"]
    check(status.startswith("done") and items == ["8"] and rep and 'missing "number"' in rep[0] and '{"num":7}' in prompts[1],
          f"a reply with the wrong shape is caught, explained and fixed, not turned into 0 ({items})")
    status, steps, items, prompts = await scripted(num_prog("q"), [{"num": 7}, {"num": 7}])
    stopped = [t for n, p_, t in steps if n == "Run stopped"]
    check(status == "error" and stopped and "still didn't have the expected shape" in stopped[0] and "retry" in stopped[0],
          "a second wrong reply stops the step with a clear message")
    retry = script(blk("rb_retry", inputs={"TIMES": nm(2), "DO": {"block": add(val(blk("rb_ask_number", inputs={"TEXT": tx("q")})))}}))
    status, steps, items, prompts = await scripted(retry, [{"num": 1}, {"num": 1}, {"number": 5}])
    check(status.startswith("done") and items == ["5"], f"inside 'retry', a step that still fails is tried again ({status}, {items})")
    yesno = script(add(val(blk("rb_ask_yesno", inputs={"TEXT": tx("Is rye a grain?")}))))
    status, steps, items, prompts = await scripted(yesno, [{"answer": "yes"}, {"answer": True}])
    check(status.startswith("done") and items == ["true"], f"'yes' as text isn't taken as an answer: it's sent back and fixed ({items})")
    rev = script(blk("rb_set_draft", inputs={"TEXT": tx("A draft.")}), blk("rb_review", inputs={"CRITERIA": tx("clear")}), add(val(blk("rb_passed"))))
    status, steps, items, prompts = await scripted(rev, [{"verdict": "fine"}, {"approved": True}])
    check(status.startswith("done") and items == ["true"], f"a review reply without 'approved' is fixed, and 'problems' may be left out ({items})")
    await load_state(pg, num_prog("one", "two"))
    EXTRA["t_json"] = await export_python(pg, "t_json")

    print("Review loop: best draft, earlier rounds, checkpoints")
    nope = lambda *p_: {"approved": False, "problems": list(p_)}  # noqa: E731
    status, steps, items, prompts = await scripted(review_loop_prog(), [nope("a", "b"), nope("a"), nope("a", "b", "c"), nope("a", "b")])
    kept = [t for n, p_, t in steps if n == "Kept the best draft"]
    check(status.startswith("done") and items == ["v2", "a"] and kept and "round 2" in kept[0] and "fewest problems (1)" in kept[0],
          f"out of rounds, the draft with the fewest problems is kept, with its own problems ({items})")
    check("Earlier rounds" not in prompts[0] and "Earlier rounds of this review found" in prompts[1] and "- a\n- b" in prompts[1]
          and "- a\n- b\n- c" in prompts[3], "each round, the reviewer is shown the problems earlier rounds found")
    status, steps, items, prompts = await scripted(review_loop_prog(), [nope("a"), {"approved": True}])
    check(status.startswith("done") and items[0] == "v2" and "Kept the best draft" not in [n for n, *_ in steps], "an approved draft is kept as it is")
    status, steps, items, prompts = await scripted(review_loop_prog(), [nope("a", "b"), nope("a"), nope("a"), nope("a")])
    check(status.startswith("done") and items[0] == "v4" and "Kept the best draft" not in [n for n, *_ in steps],
          "when the last draft is as good as any, it stays (a tie goes to the newer draft)")
    revise_loop = script(blk("rb_set_draft", inputs={"TEXT": tx("x")}),
                         blk("rb_reflect", inputs={"CRITERIA": tx("short; titled"), "ROUNDS": nm(2), "FIX": {"block": blk("rb_revise")}}),
                         blk("rb_review", inputs={"CRITERIA": tx("short")}))
    await pg.evaluate("window.__textPrompts = []")
    status, steps, items, prompts = await scripted(revise_loop, [nope("too long", "no title"), nope("no title"), nope("no title"), {"approved": True}])
    revises = [q for q in await pg.evaluate("window.__textPrompts") if q.startswith("Revise the draft")]
    check(status.startswith("done") and len(revises) == 2 and "Don't bring them back" not in revises[0]
          and "Don't bring them back:\n- too long\n\nDraft:" in revises[1], "revise is told which problems earlier rounds fixed, so it doesn't bring them back")
    check("Earlier rounds" not in prompts[-1], "a review outside the loop isn't shown the loop's earlier problems")
    status, steps, items, prompts = await scripted(checkpoint_prog(), [])
    check(status.startswith("done") and items == ["r1", "good 1"] and [n for n, *_ in steps].count("Back to checkpoint \u201ccp\u201d") == 1,
          f"go back to checkpoint restores the draft, result and variables, and works more than once ({items})")
    await load_state(pg, script(blk("rb_checkpoint_restore", fields={"NAME": "nowhere"})))
    status = await run_program(pg)
    stopped = [t for n, p_, t in await step_texts(pg) if n == "Run stopped"]
    check(status == "error" and stopped and "no checkpoint called" in stopped[0], "going back to a checkpoint that wasn't saved says so")
    await load_state(pg, review_loop_prog())
    EXTRA["t_bestdraft"] = await export_python(pg, "t_bestdraft")
    await load_state(pg, checkpoint_prog())
    EXTRA["t_checkpoint"] = await export_python(pg, "t_checkpoint")
    check("with R.reviewing():" in EXTRA["t_bestdraft"] and 'R.restore_checkpoint("cp")' in EXTRA["t_checkpoint"], "exported Python has the review loop and checkpoints")

    print("Agent")
    done = lambda a: {"done": True, "answer": a}  # noqa: E731
    tool = lambda n, **kw: {"tool": n, "input": kw, "why": "test"}  # noqa: E731
    await pg.select_option("#example", "a_bake")
    await pg.click("#load")
    status = await run_program(pg)
    steps = await step_texts(pg)
    names = [n for n, *_ in steps]
    result = await pg.text_content(".result") if await pg.query_selector(".result") else ""
    check(status.startswith("done") and "Agent step 1/8: ask_me" in names and "Agent: finished in 2 steps" in names and "AGENT ANSWER" in result,
          f"the agent picks a tool, uses it, then answers into the draft ({status})")
    asked = [t for n, p_, t in steps if n == "Question for you"]
    check(bool(asked) and "You: rye bread" in asked[0], "the agent's ask_me tool asks you in the log and passes on your answer")
    check(names.index("Question for you") < names.index("Agent step 1/8: ask_me"), "the log shows the question before the step that used the answer")
    status, steps, items = await agent_run(pg, ["ha_act"], [tool("call_service", service="light.turn_off", entity="light.kitchen"), done("off")], answer="Allow")
    names = [n for n, *_ in steps]
    check(names.index("Allow this?") < names.index("Home Assistant: light.turn_off") < names.index("Agent step 1/6: call_service"),
          "an approval and its action show before the agent step that caused them")
    await pg.select_option("#example", "a_tool")
    await pg.click("#load")
    status = await run_program(pg)
    tool = [t for n, p_, t in await step_texts(pg) if n == "Agent step 1/6: hydration"]
    check(status.startswith("done") and tool and "Result:\n170" in tool[0],
          f"a My Block works as a tool: its inputs come from the agent, its return value goes back ({status}, {tool[0][-40:] if tool else 'no tool step'})")
    await pg.evaluate("Blockly.getMainWorkspace().getBlocksByType('rb_agent_tool')[0].setFieldValue('TRUE', 'ASK')")
    status = await run_and_answer(pg, "Don't")
    tool = [t for n, p_, t in await step_texts(pg) if n == "Agent step 1/6: hydration"]
    check(status.startswith("done") and tool and "said no" in tool[0], f"'ask me before each use' lets you refuse a tool, and the agent carries on ({status})")
    EXTRA["t_agent"] = await export_python(pg, "t_agent")
    check('await R.agent(' in EXTRA["t_agent"] and '"fn": block_hydration' in EXTRA["t_agent"] and '"ask": True' in EXTRA["t_agent"],
          "exported Python passes the agent its tools, including the My Block and its ask setting")
    one = script(blk("rb_agent", inputs={"GOAL": tx("Say hello"), "STEPS": nm(1)}), blk("rb_result"))
    await load_state(pg, one)
    status = await run_program(pg)
    names = [n for n, *_ in await step_texts(pg)]
    check(status.startswith("done") and "Agent: finished in 1 step" in names, f"an agent with no tools and one step just answers ({status})")
    await load_state(pg, script(blk("rb_agent", inputs={"GOAL": tx(""), "STEPS": nm(3)})))
    status = await run_program(pg)
    stopped = [t for n, p_, t in await step_texts(pg) if n == "Run stopped"]
    check(status == "error" and stopped and "needs a goal" in stopped[0], "an agent with no goal says so")

    print("Tool safety default")
    fresh_ask = await pg.evaluate("(() => { const b = Blockly.getMainWorkspace().newBlock('rb_agent_tool'); const v = b.getFieldValue('ASK'); b.dispose(); return v; })()")
    check(fresh_ask == "TRUE", "a new 'tool: My Block' starts with 'ask me before each use' ticked")

    print("Typed tool inputs")
    tcall = lambda n, **kw: {"tool": n, "input": kw, "why": "test"}  # noqa: E731
    fin = lambda a: {"done": True, "answer": a}  # noqa: E731
    hyd_types = "flour grams: number; water grams: number - grams of water"
    def hyd_prog(types=hyd_types):
        st = json.loads(json.dumps(EXAMPLE_A_TOOL))
        st["blocks"]["blocks"][0]["next"]["block"]["inputs"]["TOOLS"]["block"]["fields"]["INPUTS"] = types
        return st
    await pg.select_option("#example", "a_tool")
    await pg.click("#load")
    EXAMPLE_A_TOOL.update(await pg.evaluate("Blockly.serialization.workspaces.save(Blockly.getMainWorkspace())"))

    async def hyd_run(replies, types=hyd_types):
        await load_state(pg, hyd_prog(types))
        await pg.evaluate("r => { window.__agentScript = r; window.__agentPrompts = []; }", replies)
        try:
            status = await run_program(pg)
        finally:
            await pg.evaluate("window.__agentScript = null")
        return status, await step_texts(pg), await pg.evaluate("window.__agentPrompts")

    status, steps, prompts = await hyd_run([tcall("hydration", **{"flour grams": "500", "water grams": 350}), fin("ok")])
    r1 = [t for n, p_, t in steps if n == "Agent step 1/6: hydration"]
    check(status.startswith("done") and r1 and r1[0].endswith("Result:\n70") and
          '"flour grams":{"type":"number"}' in prompts[0] and '"water grams":{"type":"number","description":"grams of water"}' in prompts[0]
          and '"required":["flour grams","water grams"],"additionalProperties":false' in prompts[0],
          "the agent is shown each tool's JSON Schema, and a number sent as text is converted")
    status, steps, prompts = await hyd_run([tcall("hydration", **{"flour grams": "lots", "water grams": 350}), tcall("hydration", **{"flour grams": 500, "water grams": 350}), fin("ok")])
    pl = {n: (p_, t) for n, p_, t in steps}
    check(status.startswith("done") and pl.get("Agent step 1/6: hydration", ("",))[0] == "bad input" and "should be a number" in pl["Agent step 1/6: hydration"][1]
          and pl.get("Agent step 2/6: hydration", ("",))[0] == "done" and "should be a number, not \"lots\"" in prompts[1],
          "an input of the wrong type isn't run: the agent is told what to fix, and its next try runs")
    status, steps, prompts = await hyd_run([tcall("hydration", **{"flour grams": 500}), fin("ok")])
    b1 = [t for n, p_, t in steps if n == "Agent step 1/6: hydration"]
    check(b1 and "\u201cwater grams\u201d is missing" in b1[0], "a missing input is caught before the tool runs")
    status, steps, prompts = await hyd_run([tcall("hydration", **{"flour grams": 500, "water grams": 350, "salt": 10}), fin("ok")])
    b1 = [t for n, p_, t in steps if n == "Agent step 1/6: hydration"]
    check(b1 and "no input called \u201csalt\u201d" in b1[0], "an input the tool doesn't have is caught")
    status, steps, prompts = await hyd_run([fin("ok")], types="flour: number")
    stopped = [t for n, p_, t in steps if n == "Run stopped"]
    check(status == "error" and stopped and "inputs are: flour grams, water grams" in stopped[0], "a type for an input the My Block doesn't have stops the run, naming the real inputs")
    status, steps, prompts = await hyd_run([fin("ok")], types="flour grams: weight")
    stopped = [t for n, p_, t in steps if n == "Run stopped"]
    check(status == "error" and stopped and "isn't a type the agent knows" in stopped[0], "an unknown type is reported")
    status, steps, items = await agent_run(pg, ["ha_read"], [tcall("device_state"), fin("ok")])
    b1 = [t for n, p_, t in steps if n == "Agent step 1/6: device_state"]
    check(b1 and "\u201centity\u201d is missing" in b1[0], "built-in tools have types too")
    await load_state(pg, hyd_prog())
    EXTRA["t_typed"] = await export_python(pg, "t_typed")
    AGENT_SCRIPTS["t_typed"] = [tcall("hydration", **{"flour grams": "lots", "water grams": 350}), tcall("hydration", **{"flour grams": "500", "water grams": 350}), fin("ok")]
    check('"inputs": "flour grams: number; water grams: number - grams of water"' in EXTRA["t_typed"], "exported Python keeps the input types")

    print("Traceability")
    await pg.select_option("#example", "review")
    await pg.click("#load")
    await run_program(pg)
    rows = await pg.eval_on_selector_all(".step", """e => e.map(x => [x.querySelector('.step-name').textContent,
        (x.querySelector(':scope > .step-meta') || {}).textContent || '', (x.querySelector(':scope > .step-prompt summary') || {}).textContent || '',
        [...x.querySelectorAll(':scope > .step-prompt pre')].map(p => p.textContent)])""")
    by = {r[0]: r for r in rows}
    meta_ok = re.fullmatch(r"Claude, \w+ · \d+\.\d s · ~\d+ in, ~\d+ out", by["Review, round 1"][1] or "")
    check(meta_ok and by["Task set"][1] == "" and by["Review, round 1"][2] == "Prompt sent" and "You are a strict reviewer" in by["Review, round 1"][3][0],
          f"each step that calls a model shows which model, how long and the tokens, and the exact prompt sent ({by['Review, round 1'][1]})")
    status, steps, items, prompts = await scripted(num_prog("How many grams in a cup?"), ["BAD", {"number": 7}])
    rows = await pg.eval_on_selector_all(".step", """e => e.filter(x => x.querySelector('.step-name').textContent.startsWith('Number')).map(x =>
        [(x.querySelector(':scope > .step-meta') || {}).textContent || '', (x.querySelector(':scope > .step-prompt summary') || {}).textContent || '',
         [...x.querySelectorAll(':scope > .step-prompt pre')].map(p => p.textContent)])""")
    check(rows and rows[0][0].startswith("2 calls · ") and rows[0][1] == "Prompts sent (2)" and "couldn't be used" in rows[0][2][1],
          f"a repaired step shows both calls and both prompts ({rows[0][0] if rows else 'no step'})")
    instr = script(blk("rb_set_instructions", inputs={"TEXT": tx("Write in British English.")}), add(val(blk("rb_ask", inputs={"TEXT": tx("Spell colour.")}))))
    await load_state(pg, instr)
    await run_program(pg)
    pre = await pg.eval_on_selector_all(".step > .step-prompt pre", "e => e.map(p => p.textContent)")
    check(pre and "Write in British English." in pre[-1] and "Spell colour." in pre[-1], "the prompt shown includes standing instructions, as the model received them")
    await pg.click("#log-save")
    await pg.wait_for_timeout(300)
    saved = [n for n in await pg.evaluate("window.__saved") if "-log-" in n]
    data = (await pg.evaluate("window.__savedData"))[saved[-1]] if saved else ""
    check("<details><summary>Prompt sent</summary>" in data and "Write in British English." in data and re.search(r"\*Claude, \w+ · \d+\.\d s · ~\d+ in", data),
          "the saved log has each step's model, time, tokens and prompt")
    steps_prog = script(blk("rb_agent", inputs={"GOAL": tx("Test goal"), "STEPS": nm(6), "TOOLS": {"block": blk("rb_agent_builtin", fields={"KIND": "memory"})}}),
                        add(val(blk("rb_agent_steps"))))
    await load_state(pg, steps_prog)
    replies = [tcall("remember", name="s", value="rye"), tcall("recall", name="s"), tcall("recall", name="s"), fin("Rye.")]
    await pg.evaluate("r => { window.__agentScript = r; }", replies)
    try:
        status = await run_program(pg)
    finally:
        await pg.evaluate("window.__agentScript = null")
    items = await pg.eval_on_selector_all(".result-text", "e => e.map(x => x.textContent)")
    got = items[0] if items else ""
    check(status.startswith("done") and [l.split(": ", 1)[1] for l in got.splitlines() if l.startswith("status: ")] == ["done", "done", "repeat", "answer"]
          and "tool: recall" in got and 'input: {"name": "s"}' in got and "result: rye" in got,
          f"'agent's steps' lists each step's tool, input, result and status ({got[:80]!r})")
    EXTRA["t_steps"] = await export_python(pg, "t_steps")
    AGENT_SCRIPTS["t_steps"] = replies

    print("Cut-off replies")
    long_prog = script(add(val(blk("rb_ask", inputs={"TEXT": tx("Write a very long essay about rye.")}))))
    await load_state(pg, long_prog)
    await pg.evaluate("window.__truncate = 1")
    status = await run_program(pg)
    rows = await pg.eval_on_selector_all(".step", """e => e.map(x => [x.querySelector('.step-name').textContent, x.querySelector('.pill').textContent,
        (x.querySelector(':scope > .step-meta') || {}).textContent || '', [...x.querySelectorAll(':scope > .step-prompt pre')].map(p => p.textContent)])""")
    items = await pg.eval_on_selector_all(".result-text", "e => e.map(x => x.textContent)")
    pill = await pg.text_content(".result .pill")
    ask_row = [r for r in rows if r[0].startswith("Ask Claude")]
    check(status.startswith("done") and any(r[0] == "Reply continued" for r in rows) and not any(r[0] == "Cut short" for r in rows)
          and items and items[0].count("ANSWER(") == 2 and "Continue exactly" in items[0] and pill == "finished"
          and ask_row and ask_row[0][2].startswith("2 calls") and "[assistant]" in ask_row[0][3][1],
          f"a cut-off reply is continued once on its own, and the two parts are joined ({items[0][:70] if items else ''!r})")
    await pg.evaluate("window.__truncate = 2")
    status = await run_program(pg)
    names = [n for n, *_ in await step_texts(pg)]
    pill = await pg.text_content(".result .pill")
    check(status.startswith("done") and "Cut short" in names and pill == "best effort", f"a reply still cut off after continuing is flagged, and the result marked best effort ({pill})")
    await pg.evaluate("window.__truncate = 0")
    EXTRA["t_long"] = await export_python(pg, "t_long")

    for tier in ("mistral-default", "gemini-default"):
        await load_state(pg, script(blk("rb_use_model", fields={"TIER": tier}),
                                    add(val(blk("rb_ask_number", inputs={"TEXT": tx("one")}))), add(val(blk("rb_ask_number", inputs={"TEXT": tx("two")})))))
        EXTRA["t_json_" + tier.split("-")[0]] = await export_python(pg, "t_json_" + tier.split("-")[0])

    await load_state(pg, script(blk("rb_ask_me", inputs={"TEXT": tx("What bread?")}), add(val(blk("rb_ask", inputs={"TEXT": tx("one")}))),
                                blk("rb_ha_notify", inputs={"TARGET": tx("persistent_notification"), "TEXT": tx("Half way there.")}),
                                add(val(blk("rb_ask", inputs={"TEXT": tx("two")}))), add(val(blk("rb_ask", inputs={"TEXT": tx("three")})))))
    EXTRA["t_resume"] = await export_python(pg, "t_resume")

    print("Agent: every path")
    done = lambda a: {"done": True, "answer": a}  # noqa: E731
    tool = lambda n, **kw: {"tool": n, "input": kw, "why": "test"}  # noqa: E731
    pills = lambda steps: {n: p_ for n, p_, t in steps}  # noqa: E731
    status, steps, items = await agent_run(pg, ["memory"], ["BAD", done("recovered")], export="t_ag_bad")
    pl = pills(steps)
    check(status.startswith("done") and pl.get("Agent step 1/6") == "unreadable" and "Agent: finished in 2 steps" in pl and items == ["recovered"],
          f"an unreadable reply wastes a step instead of ending the run ({status}, {items})")
    status, steps, items = await agent_run(pg, ["memory"], [done(""), done("second try")])
    check(status.startswith("done") and pills(steps).get("Agent step 1/6") == "empty answer" and items == ["second try"],
          f"an empty final answer is sent back for another go ({items})")
    status, steps, items = await agent_run(pg, ["memory"], [tool("make_tea"), done("fine")])
    t1 = [t for n, p_, t in steps if n == "Agent step 1/6"]
    check(status.startswith("done") and t1 and "make_tea" in t1[0] and pills(steps)["Agent step 1/6"] == "not a tool", "an unknown tool name is reported back, not run")
    status, steps, items = await agent_run(pg, ["memory"], [tool("remember", name="starter", value="rye, fed daily"), tool("recall", name="starter"), done("Your starter is rye.")])
    r2 = [t for n, p_, t in steps if n == "Agent step 2/6: recall"]
    check(status.startswith("done") and r2 and r2[0].endswith("Result:\nrye, fed daily") and items == ["Your starter is rye."],
          f"a multi-step chain: remember, then recall what it saved, then answer ({items})")
    status, steps, items = await agent_run(pg, ["memory"], [tool("remember", name="", value="no name"), done("ok")])
    e1 = [(p_, t) for n, p_, t in steps if n == "Agent step 1/6: remember"]
    check(status.startswith("done") and e1 and e1[0][0] == "tool error" and "remember needs a name" in e1[0][1], "a tool's error goes back to the agent and the run carries on")
    status, steps, items = await agent_run(pg, ["memory"], [tool("recall", name="x")] * 3, export="t_ag_repeat")
    pl = pills(steps)
    check(status.startswith("done") and pl.get("Agent step 2/6: recall") == "repeat" and "Agent: stopped, repeating itself" in pl
          and "Agent: out of steps" not in pl and items and "Nothing is saved" in items[0],
          f"a repeated call is skipped with a warning, and a third stops the agent ({items})")
    status, steps, items = await agent_run(pg, ["memory"], [tool("list_memory"), tool("recall", name="a")], steps=2, export="t_ag_out")
    pl = pills(steps)
    check(status.startswith("done") and pl.get("Agent step 2/2") == "not a tool" and pl.get("Agent: out of steps") == "best effort",
          "out of steps: a tool on the last step isn't run, and the draft keeps the last result")
    off = [tool("find_devices", search="kitchen"), tool("call_service", service="light.turn_off", entity="light.kitchen"), done("Kitchen light is off.")]
    status, steps, items = await agent_run(pg, ["ha_read", "ha_act"], off, answer="Allow", export="t_ag_ha")
    names = [n for n, *_ in steps]
    check(status.startswith("done") and names.count("Allow this?") == 1 and "Home Assistant: light.turn_off" in names and items == ["Kitchen light is off."],
          f"controlling Home Assistant asks first by default ({status})")
    status, steps, items = await agent_run(pg, ["ha_read", "ha_act"], off, answer="Don't")
    s2 = [t for n, p_, t in steps if n == "Agent step 2/6: call_service"]
    check(status.startswith("done") and "Home Assistant: light.turn_off" not in [n for n, *_ in steps] and s2 and "said no" in s2[0],
          "saying no keeps the light on, and the agent is told")
    status, steps, items = await agent_run(pg, ["ha_read", "ha_act_free"], off)
    names = [n for n, *_ in steps]
    check(status.startswith("done") and "Allow this?" not in names and "Home Assistant: light.turn_off" in names, "'control devices (no asking)' acts without asking")
    unlock = [tool("call_service", service="lock.unlock", entity="lock.front_door"), done("Unlocked.")]
    status, steps, items = await agent_run(pg, ["ha_act"], unlock, answer="Allow")
    names = [n for n, *_ in steps]
    check(status.startswith("done") and names.count("Allow this?") == 1 and "Home Assistant: lock.unlock" in names, "unlocking asks once, not twice")

    print("Agent planning")
    planned = [dict(tool("remember", name="a", value="1"), plan=["save it", "check it"]),
               dict(tool("recall", name="a"), plan=["save it", "check it"]),
               dict(tool("list_memory"), plan=["save it", "list everything"]),
               done("planned and done")]
    status, steps, items = await agent_run(pg, ["memory"], planned, plan=True, export="t_ag_plan")
    names = [n for n, *_ in steps]
    prompts = await pg.evaluate("window.__agentPrompts")
    check(status.startswith("done") and names.count("Agent plan") == 1 and names.count("Agent: plan changed") == 1
          and names.index("Agent plan") < names.index("Agent step 1/6: remember") and items == ["planned and done"],
          f"the agent's plan is logged before its first step, and a changed plan is logged once ({status})")
    check(len(prompts) == 4 and "Planning is on" in prompts[0] and "YOUR PLAN:\n(none yet)" in prompts[0]
          and "YOUR PLAN:\n1. save it\n2. check it" in prompts[1] and "only when you change your plan" in prompts[1]
          and "2. list everything" in prompts[3],
          "each step's prompt shows the current plan, and asks for changes only when needed")
    status, steps, items = await agent_run(pg, ["memory"], [tool("list_memory"), done("ok")], plan=True)
    prompts = await pg.evaluate("window.__agentPrompts")
    check(status.startswith("done") and "Agent plan" not in [n for n, *_ in steps] and len(prompts) == 2 and "Planning is on" in prompts[1],
          "if the first reply has no plan, the tool still runs and the next prompt asks for one again")
    status, steps, items = await agent_run(pg, ["memory"], [dict(tool("list_memory"), plan=["x"]), done("ok")])
    prompts = await pg.evaluate("window.__agentPrompts")
    check(status.startswith("done") and not any("YOUR PLAN" in q or "plan" in q.split("TOOLS:")[0] for q in prompts)
          and "Agent plan" not in [n for n, *_ in steps], "with planning off, the prompt never mentions a plan and any plan sent is ignored")
    check("plan=True" in EXTRA["t_ag_plan"], "exported Python keeps planning switched on")

    print("My Blocks")
    double = {"variables": [{"id": "v_x", "name": "x"}], "blocks": {"languageVersion": 0, "blocks": [
        {"type": "rb_start", "x": 20, "y": 20, "next": {"block": add(val({"type": "procedures_callreturn", "extraState": {"name": "double", "params": ["x"]},
                                                                           "inputs": {"ARG0": nm(21)}}))}},
        {"type": "procedures_defreturn", "x": 20, "y": 200, "fields": {"NAME": "double"}, "extraState": {"params": [{"name": "x", "id": "v_x"}]},
         "inputs": {"RETURN": val({"type": "math_round", "fields": {"OP": "ROUND"}, "inputs": {"NUM": val({"type": "math_arithmetic", "fields": {"OP": "MULTIPLY"},
                    "inputs": {"A": val({"type": "variables_get", "fields": {"VAR": {"id": "v_x"}}}), "B": nm(2)}})}})}}]}}
    await load_state(pg, double)
    status = await run_program(pg)
    items = await pg.eval_on_selector_all(".result-text", "e => e.map(x => x.textContent)")
    check(status.startswith("done") and items == ["42"], f"a My Block's return value can use its inputs inside nested blocks ({items})")

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
        (pathlib.Path(tmp) / "t_steps.py").write_text(EXTRA["t_steps"], encoding="utf-8")
        code_, out, err = run_ag("t_steps")
        out = out.replace("\r\n", "\n")
        statuses = [l.split(": ", 1)[1] for l in out.split("RESULT")[-1].splitlines() if l.startswith("status: ")]
        check(code_ == 0 and statuses == ["done", "done", "repeat", "answer"] and "tool: recall" in out,
              "t_steps.py gives the agent's steps as records" + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        check(re.search(r"▸ Agent step 1/6: remember  \[done\]\n(    .*\n)*    · Claude, \w+ · \d+\.\d s · \d+ in, \d+ out\n", out),
              "Python prints each step's model, time and exact tokens")
        code_, out, err = run_ag("t_ag_bad")
        check(code_ == 0 and "▸ Agent step 1/6  [unreadable]" in out and "▸ Agent: finished in 2 steps" in out, "t_ag_bad.py survives an unreadable reply" + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
        code_, out, err = run_ag("t_ag_repeat")
        check(code_ == 0 and "▸ Agent step 2/6: recall  [repeat]" in out and "▸ Agent: stopped, repeating itself" in out, "t_ag_repeat.py stops an agent that repeats itself")
        code_, out, err = run_ag("t_ag_out")
        check(code_ == 0 and "▸ Agent step 2/2  [not a tool]" in out and "▸ Agent: out of steps  [best effort]" in out, "t_ag_out.py runs out of steps cleanly")
        code_, out, err = run_ag("t_ag_plan")
        out = out.replace("\r\n", "\n")
        check(code_ == 0 and "▸ Agent plan  [planned]\n    1. save it\n    2. check it" in out and out.count("▸ Agent: plan changed") == 1
              and "▸ Agent: finished in 4 steps" in out, "t_ag_plan.py plans, changes its plan once, then finishes" + ("" if code_ == 0 else f": {(err or out)[-300:]!r}"))
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
