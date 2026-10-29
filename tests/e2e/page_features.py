"""End-to-end tests of the page's newer features, block by block."""
from e2e.common import *  # noqa: F401,F403


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

    print("Agent summary")
    summary_rows = """e => { const st = e.find(x => x.querySelector('.step-name').textContent === 'Agent summary'); if (!st) return null;
        return [...st.querySelectorAll('tbody tr')].map(r => [...r.cells].map(c => c.textContent)); }"""
    chain = [tcall("remember", name="s", value="rye"), tcall("recall", name="s"), fin("Your starter is rye.")]
    status, steps, items = await agent_run(pg, ["memory"], chain)
    rows = await pg.eval_on_selector_all(".step", summary_rows)
    check(status.startswith("done") and rows and len(rows) == 3 and rows[1] == ["2", "recall", '{"name": "s"}', "rye", "done"]
          and rows[2][1] == "final answer" and rows[2][4] == "answer",
          f"after the agent, a summary table lists each step's tool, input, result and status ({rows[1] if rows else None})")
    await pg.click("#log-save")
    await pg.wait_for_timeout(300)
    saved = [n for n in await pg.evaluate("window.__saved") if "-log-" in n]
    data = (await pg.evaluate("window.__savedData"))[saved[-1]] if saved else ""
    check("| Step | Tool | Input | Result | Status |" in data and '| 2 | recall | {"name": "s"} | rye | done |' in data, "the saved log has the summary as a markdown table")
    stop_prog = script(blk("rb_budget", inputs={"TOKENS": nm(5)}),
                       blk("rb_agent", inputs={"GOAL": tx("Test goal"), "STEPS": nm(6), "TOOLS": {"block": blk("rb_agent_builtin", fields={"KIND": "memory"})}}))
    await load_state(pg, stop_prog)
    await pg.evaluate("r => { window.__agentScript = r; }", chain)
    try:
        status = await run_program(pg)
    finally:
        await pg.evaluate("window.__agentScript = null")
    rows = await pg.eval_on_selector_all(".step", summary_rows)
    check(status == "error" and rows and len(rows) == 1 and rows[0][1] == "remember", f"if the run stops part-way, the summary still shows what the agent had done ({status})")

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
    search = [tool("remember", name="rye loaf", value="78% hydration, proved overnight"), tool("search_memory", query="hydration rye"), done("Found it.")]
    status, steps, items = await agent_run(pg, ["memory"], search, export="t_ag_memsearch")
    found = [t for n, p_, t in steps if n == "Agent step 2/6: search_memory"]
    check(status.startswith("done") and found and "Notes matching \u201chydration rye\u201d, best first" in found[0] and "- rye loaf (saved " in found[0],
          f"the agent's search_memory finds a note by what's in it, on the page ({found[:1]})")
    mcp_tools = blk("rb_agent_mcp", fields={"SERVER": "bakery", "ASK": "changes"})
    status, steps, items = await agent_run(pg, [mcp_tools], [done("Nothing to add.")], export="t_ag_mcp")
    notes = [t for n, p_, t in steps if n == "MCP server \u201cbakery\u201d"]
    check(status.startswith("done") and notes and "can't be reached from this page" in notes[0] and "MCP_BAKERY" in notes[0],
          "on the page, an agent's MCP server is noted as out of reach, and the run carries on without it")
    code = EXTRA["t_ag_mcp"]
    files = {f["name"]: f["text"] for f in await pg.evaluate("window.__exportFiles()")}
    check('{"kind": "mcp", "server": "bakery", "ask": "changes"}' in code and '"can": ["mcp"]' in code
          and "  - use the tools of the MCP servers you set up" in code.split('"""', 2)[1]
          and "[mcp servers]" in files["second-thought.ini"] and "\nMCP_BAKERY = \n" in files["second-thought.ini"].replace("\r\n", "\n"),
          "exported Python hands the agent its MCP server, lists it as something the program can do, and the ini asks for MCP_BAKERY")
    AGENT_SCRIPTS["t_ag_mcp"] = [tool("bakery_list_loaves"), tool("bakery_add_loaf", name="Rye", grams="900"), done("Added the rye.")]

    print("More agent tools")
    step_of = lambda steps, k, n, name: next((t for s_, p_, t in steps if s_ == f"Agent step {k}/{n}: {name}"), "")  # noqa: E731
    pill_of = lambda steps, k, n, name: next((p_ for s_, p_, t in steps if s_ == f"Agent step {k}/{n}: {name}"), "")  # noqa: E731
    sums = ["(350 / 500) * 100", "round(1000 * 0.02, 1)", "2^3^2 - -2^2", "1/3", "min(3, 1) * sqrt(16)", "2 / 0", "flour + 1"]
    status, steps, items = await agent_run(pg, ["calc"], [tcall("calculate", expression=e) for e in sums] + [fin("ok")], steps=10, export="t_ag_calc")
    want = ["= 70", "= 20", "= 516", "= 0.333333333333", "= 4"]
    check(status.startswith("done") and all(step_of(steps, k + 1, 10, "calculate").endswith(w) for k, w in enumerate(want)),
          "calculate works sums out exactly: brackets, powers, rounding, min and sqrt" + ("" if status.startswith("done") else f" ({status})"))
    check(pill_of(steps, 6, 10, "calculate") == "tool error" and "divides by zero" in step_of(steps, 6, 10, "calculate")
          and "I don't know \u201cflour\u201d" in step_of(steps, 7, 10, "calculate"), "a sum it can't do comes back to the agent as an error it can fix")
    clock = [tcall("time_plus", time="22:00", minutes=600), tcall("time_plus", time="2026-10-10 22:00", minutes="600"),
             tcall("time_plus", time="00:30", minutes=-3000), tcall("time_plus", time="9:15pm", minutes=30),
             tcall("time_plus", time="2026-02-30 10:00", minutes=5), tcall("current_time")]
    status, steps, items = await agent_run(pg, ["time"], clock + [fin("ok")], steps=10, export="t_ag_time")
    check(status.startswith("done") and step_of(steps, 1, 10, "time_plus").endswith("08:00 (next day)")
          and step_of(steps, 2, 10, "time_plus").endswith("2026-10-11 08:00 (Sunday)") and step_of(steps, 3, 10, "time_plus").endswith("22:30 (3 days earlier)")
          and step_of(steps, 4, 10, "time_plus").endswith("21:45"), "time_plus adds and takes away minutes, across midnight and dates, with the day")
    check("isn't a real date" in step_of(steps, 5, 10, "time_plus")
          and re.search(r"Result:\n(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday) \d{4}-\d\d-\d\d \d\d:\d\d$", step_of(steps, 6, 10, "current_time")),
          "a date that doesn't exist is refused, and current_time gives the day, date and time")
    await pg.evaluate("window.__jsonPrompts = []")
    status, steps, items = await agent_run(pg, ["review"], [tcall("review_text", text="Hello there", criteria="short; friendly"), fin("ok")], export="t_ag_review")
    checked = [(p_, t) for s_, p_, t in steps if s_ == "Check: short; friendly"]
    rprompt = [q for q in await pg.evaluate("window.__jsonPrompts") if "Judge the text ONLY" in q]
    r1 = step_of(steps, 1, 6, "review_text")
    check(status.startswith("done") and checked and checked[0][0] in ("passes", "needs work") and rprompt and "short; friendly" in rprompt[0]
          and "Text:\nHello there" in rprompt[0] and ("Passes every criterion." in r1 or "Doesn't pass yet. Problems: - " in r1),
          "review_text has a separate reviewer check the text, and the agent gets the verdict and problems")
    status, steps, items = await agent_run(pg, ["web"], [tcall("read_page", url="http://localhost:8123/"), tcall("read_page", url="ftp://example.com/x"), fin("ok")],
                                           export="t_ag_page")
    check(status.startswith("done") and pill_of(steps, 1, 6, "read_page") == "done" and "doesn't work here" in step_of(steps, 1, 6, "read_page")
          and [p_ for s_, p_, t in steps if s_.startswith("Read page: ")] == ["not live"], "on the page, read_page tells the agent it only works in exported Python")
    status, steps, items = await agent_run(pg, ["ha_read"], [tcall("device_history", entity="sensor.kitchen_temperature", hours=6), fin("ok")], export="t_ag_hist")
    check(status.startswith("done") and re.search(r"Result:\n(\w{3} \d\d:\d\d: [\d.]+ ?)+$", step_of(steps, 1, 6, "device_history")),
          "device_history gives the agent a sensor's recent readings")
    status, steps, items = await agent_run(pg, ["file"], [tcall("read_file", why="to check the hydration"), fin("ok")], export="t_ag_file")
    chose = [t for s_, p_, t in steps if s_ == "Choose a file"]
    check(status.startswith("done") and chose and chose[0].startswith("The agent wants a file: to check the hydration")
          and "Order rye flour." in step_of(steps, 1, 6, "read_file"), "read_file asks you for a file, saying why, and the agent gets its words")
    toolbox = await pg.evaluate("""(() => { const b = Blockly.getMainWorkspace().newBlock('rb_agent_builtin');
        const o = b.getField('KIND').getOptions(false).map(x => x[1]); b.dispose(); return o; })()""")
    check(all(k in toolbox for k in ("calc", "time", "file", "review")), f"the ready-made tool block offers the new tools ({', '.join(toolbox)})")
    cats = await pg.eval_on_selector_all("#example optgroup[label='Agents'] option", "e => e.map(o => o.value)")
    check(len(cats) >= 9 and {"a_bake", "a_tool", "a_timetable", "a_house"} <= set(cats), f"the Agents group in the Example menu has the agent examples ({len(cats)})")

    print("Connections")
    cats_ = await pg.evaluate("Blockly.getMainWorkspace().getToolbox().getToolboxItems().map(i => i.getName && i.getName()).filter(Boolean)")
    check({"Agent", "Tools", "Connections"} <= set(cats_) and cats_.index("Tools") == cats_.index("Agent") + 1,
          f"the tool blocks have their own Tools category, after Agent, and the service blocks are under Connections ({', '.join(cats_)})")
    kinds = await pg.evaluate("""(() => { const b = Blockly.getMainWorkspace().newBlock('rb_agent_builtin');
        const o = b.getField('KIND').getOptions(false).map(x => x[1]); b.dispose(); return o; })()""")
    for k in ("feeds", "linkedin", "calendar", "email", "email_send", "github", "github_act", "telegram", "telegram_send", "telegram_send_free"):
        status, steps, items = await agent_run(pg, [k], [fin("ok")])
        listed = next((t for s_, p_, t in steps if s_ == "Agent"), "")
        check(k in kinds and status.startswith("done") and "Tools: " in listed and "Tools: \u00b7" not in listed, f"the '{k}' tool gives the agent its tools ({listed.splitlines()[-1] if listed else status})")
    gh_calls = [tcall("my_pull_requests"), tcall("read_pull_request", repo="sample-baker/sourdough-chart", number=41), tcall("search_github", query="rye"),
                tcall("list_projects"), tcall("list_pull_requests", repo="sample-baker/oven-timer"), tcall("read_pull_request", repo="not a repo", number=1)]
    status, steps, items = await agent_run(pg, ["github"], gh_calls + [fin("ok")], steps=10, export="t_cn_gh")
    check(status.startswith("done") and "Waiting for your review: sample-baker/sourdough-chart #41 Add rye flour curve" in step_of(steps, 1, 10, "my_pull_requests")
          and "Files changed (2): - src/curves.js (+24 \u22122)" in step_of(steps, 2, 10, "read_pull_request")
          and "isn't a GitHub project" in step_of(steps, 6, 10, "read_pull_request"), "GitHub tools list, read and search pull requests (sample projects on the page)")
    status, steps, items = await agent_run(pg, ["github_act"], [tcall("comment_on_github", repo="sample-baker/oven-timer", number=7, text="Looks good to me."), fin("ok")],
                                           answer="Allow", export="t_cn_comment")
    names = [n for n, *_ in steps]
    check(status.startswith("done") and names.count("Allow this?") == 1 and "GitHub comment on sample-baker/oven-timer #7" in names,
          "commenting on GitHub asks you once first")
    repo = "sample-baker/sourdough-chart"
    flat = lambda steps, k, n, name: " ".join(step_of(steps, k, n, name).split())  # noqa: E731
    gh_more = [tcall("list_branches", repo=repo), tcall("list_commits", repo=repo, author="me", since="7"), tcall("list_commits", repo=repo, since="last Tuesday"),
               tcall("read_github_file", repo=repo, path="README.md"), tcall("read_github_file", repo=repo, path="src"), tcall("read_github_file", repo=repo)]
    status, steps, items = await agent_run(pg, ["github"], gh_more + [fin("ok")], steps=10, export="t_cn_gh_more")
    branches = flat(steps, 1, 10, "list_branches")
    check(status.startswith("done") and 0 <= branches.find("old-d3-v5 · last commit 311 days ago by toast-rack") < branches.find("main · last commit 24 h ago by sample-baker · default branch")
          and "rye-curve · last commit 24 h ago by crumb-shot · open pull request #41" in branches,
          f"list_branches gives each branch's last commit, oldest first, with the default branch and open pull requests marked ({branches!r})")
    commits = flat(steps, 2, 10, "list_commits")
    check("a41c9e2 · " in commits and "Fix tooltip overflow" in commits and "3e8a52c" in commits and "crumb-shot" not in commits and "Remembers the choice" not in commits
          and "isn't a time to start from" in flat(steps, 3, 10, "list_commits"), f"list_commits filters by author (me) and time, one line each ({commits!r})")
    check("| `--starter` | starter percentage" in flat(steps, 4, 10, "read_github_file") and "is a folder: chart.js cli.js curves.js" in flat(steps, 5, 10, "read_github_file")
          and "is a folder: README.md package.json src/" in flat(steps, 6, 10, "read_github_file"), "read_github_file reads a file, and lists a folder or the top of the project")
    acts = [tcall("add_labels", repo=repo, number=40, labels=["bug", "safari"]), tcall("add_labels", repo=repo, number=40, labels=["Bug", "urgent"]),
            tcall("open_issue", repo=repo, title="Document the --dark flag", body="cli.js has it; the README doesn't."), tcall("open_issue", repo=repo, title="")]
    status, steps, items = await agent_run(pg, ["github_act"], acts + [fin("ok")], steps=10, answer="Allow", export="t_cn_issue")
    names = [n for n, *_ in steps]
    check(status.startswith("done") and "has no label safari" in flat(steps, 1, 10, "add_labels") and "documentation, duplicate, enhancement" in flat(steps, 1, 10, "add_labels")
          and "Labelled sample-baker/sourdough-chart #40: bug, urgent." in flat(steps, 2, 10, "add_labels")
          and "Opened sample-baker/sourdough-chart #44" in flat(steps, 3, 10, "open_issue") and "needs a title" in flat(steps, 4, 10, "open_issue")
          and names.count("Allow this?") == 4 and "GitHub labels on sample-baker/sourdough-chart #40" in names
          and "GitHub issue opened in sample-baker/sourdough-chart: #44" in names,
          f"add_labels uses only the project's labels and open_issue opens one, asking before each use (sample projects on the page) ({names})")
    files_and_check = script(add(val(blk("rb_folder_files", inputs={"FOLDER": tx("recipes"), "MATCH": tx("*.pdf")}))), add(val(blk("rb_setup_check"))))
    await load_state(pg, files_and_check)
    status = await run_program(pg)
    items = await pg.eval_on_selector_all(".result-text", "e => e.map(x => x.textContent)")
    whole = " ".join(items)
    check(status.startswith("done") and "rye-sourdough.pdf" in whole and "receipt-mill-and-co.pdf" in whole and "focaccia.docx" not in whole
          and "recipes/rye-sourdough.pdf" in whole and "only runs in exported Python" in whole,
          f"on the page, 'files in folder' lists the sample files matching *.pdf, and the setup check says it runs in exported Python ({whole[:300]!r})")
    EXTRA["t_folder_check"] = await export_python(pg, "t_folder_check")
    tg = [tcall("search_telegram", text="starter"), tcall("send_telegram", text="Feed the starter at 8")]
    status, steps, items = await agent_run(pg, ["telegram", "telegram_send"], tg + [fin("ok")], answer="Allow", export="t_cn_tg")
    check(status.startswith("done") and "Remind me to feed the starter at 8 tonight" in step_of(steps, 1, 6, "search_telegram")
          and any(n.startswith("Telegram \u2192") for n, *_ in steps), "Telegram tools search your messages and send one, asking first")
    mail = [tcall("search_email", query="flour"), tcall("read_email", id="1041"), tcall("send_email", to="sam@example.com", subject="Saturday", body="Yes, see you at 2!"),
            tcall("send_email", to="not an address", subject="x", body="y")]
    status, steps, items = await agent_run(pg, ["email", "email_send"], mail + [fin("ok")], steps=10, answer="Allow", export="t_cn_mail")
    check(status.startswith("done") and "Subject: Your flour order has shipped" in step_of(steps, 1, 10, "search_email")
          and "baking club this Saturday" in step_of(steps, 2, 10, "read_email") and "Email to sam@example.com" in [n for n, *_ in steps]
          and "isn't an email address" in step_of(steps, 4, 10, "send_email"), "email tools search, read and send (asking first), and refuse a bad address")
    cal = [tcall("calendar", day="today", days=7), tcall("free_time", day="today", minutes=60), tcall("calendar", day="someday")]
    status, steps, items = await agent_run(pg, ["calendar"], cal + [fin("ok")], export="t_cn_cal")
    check(status.startswith("done") and "10:00\u201311:00 Dentist (High Street)" in step_of(steps, 1, 6, "calendar")
          and "11:00\u201315:30" in step_of(steps, 2, 6, "free_time") and "isn't a day" in step_of(steps, 3, 6, "calendar"),
          "calendar tools list the week and find free time around events")
    status, steps, items = await agent_run(pg, ["feeds"], [tcall("read_feed", limit=1), tcall("read_feed", url="http://127.0.0.1:9/feed.xml"), fin("ok")], export="t_cn_feed")
    check(status.startswith("done") and "The Loaf Letter (sample feed)" in step_of(steps, 1, 6, "read_feed") and "Small Tools Weekly" in step_of(steps, 1, 6, "read_feed")
          and pill_of(steps, 2, 6, "read_feed") == "tool error", "read_feed reads your feeds (sample feeds on the page)")
    tg_prog = {"blocks": {"languageVersion": 0, "blocks": [{"type": "rb_tg_when", "x": 20, "y": 20, "fields": {"CONTAINS": "bake"}, "next": {"block":
               blk("rb_tg_send", inputs={"TEXT": {"block": {"type": "text_join", "extraState": {"itemCount": 2}, "inputs": {"ADD0": tx("Got: "),
               "ADD1": {"block": {"type": "rb_tg_message", "fields": {"PART": "text"}}}}}}}, nxt=blk("rb_add_result", inputs={"TEXT": {"block": {"type": "rb_tg_message", "fields": {"PART": "sender"}}}}))}}]}}
    await load_state(pg, tg_prog)
    await pg.evaluate("""(() => { const ws = Blockly.getMainWorkspace(), hat = ws.getBlocksByType('rb_tg_when')[0];
        Blockly.ContextMenuRegistry.registry.getItem('rb_run_script').callback({ block:hat }); })()""")
    for _ in range(60):
        await pg.wait_for_timeout(100)
        if await pg.is_enabled("#run") and await pg.query_selector(".result"):
            break
    steps = await step_texts(pg)
    sent = [t for n, p_, t in steps if n.startswith("Telegram \u2192")]
    check(sent == ["Got: What should I bake this weekend?"] and await pg.text_content(".result-text") == "You",
          f"on the page, 'Run this script' on the Telegram block tries it with a sample message ({sent})")
    EXTRA["t_tg_when"] = await export_python(pg, "t_tg_when")
    check('TELEGRAM_WATCHES = [("bake", when_telegram_message_arrives)]' in EXTRA["t_tg_when"] and "R.main(START_SCRIPTS, RECEIVERS, SCHEDULES, HA_WATCHES, TELEGRAM_WATCHES, can=CAN)" in EXTRA["t_tg_when"],
          "exported Python listens for Telegram messages")
    await pg.select_option("#example", "x_tgbrief")
    await pg.click("#load")
    await pg.fill("#io-name", "x_tgbrief")
    files = {f["name"]: f["text"] for f in await pg.evaluate("window.__exportFiles()")}
    ini = files["second-thought.ini"]
    check("[telegram]" in ini and "TELEGRAM_BOT_TOKEN = " in ini and "[calendar]" in ini and "CALENDAR_URL = " in ini and "feeds = " in ini
          and "tzdata" in files["requirements.txt"] and "run-on-schedule.bat" in files, "the exported settings file asks for exactly the connections the program uses")
    await pg.select_option("#example", "a_prs")
    await pg.click("#load")
    files = {f["name"]: f["text"] for f in await pg.evaluate("window.__exportFiles()")}
    check("GITHUB_TOKEN = " in files["second-thought.ini"] and "[telegram]" not in files["second-thought.ini"], "a GitHub agent's settings ask for a GitHub token only")

    print("Listeners")
    hats = [("rb_mqtt_when", {"TOPIC": "home/proofer/temperature"}, "mqtt", "27.4"), ("rb_webhook_when", {"PATH": "bake-done"}, "webhook", '"loaf": "rye"'),
            ("rb_email_when", {"CONTAINS": "flour"}, "email", "Subject: Your flour order has shipped"), ("rb_feed_when", {"URL": ""}, "feed", "nail varnish"),
            ("rb_folder_when", {"FOLDER": "drop"}, "folder", "Grandma's loaf"), ("rb_gh_when", {}, "github", "#41: Add rye flour curve"),
            ("rb_gh_issue_when", {"REPO": "sample-baker/sourdough-chart"}, "github_issue", "sample-baker/sourdough-chart #"),  # the newest issue: earlier tests may open one
            ("rb_gh_release_when", {"REPO": "sample-baker/sourdough-chart"}, "github_release", "v1.4.0: Spelt curve and unit toggle"),
            ("rb_cal_when", {"N": 15}, "calendar", " at "), ("rb_discord_when", {"CONTAINS": "anything"}, "discord", "first rye loaf"),
            ("rb_slack_when", {"CONTAINS": "anything"}, "slack", "proving baskets"), ("rb_tg_when", {"CONTAINS": "anything"}, "telegram", "What should I bake"),
            ("rb_ha_event_when", {"EVENT": "zha_event", "DATA": "kitchen remote"}, "ha_event", "zha_event: {\"device_ieee\"")]

    def say_what(kind):
        return blk("rb_say", inputs={"TEXT": {"block": {"type": "text_join", "extraState": {"itemCount": 2}, "inputs": {"ADD0": tx(kind + ": "),
                   "ADD1": {"block": {"type": "rb_event", "fields": {"KEY": "text"}}}}}}})
    for type_, fields, kind, want in hats:
        prog = {"blocks": {"languageVersion": 0, "blocks": [dict({"type": type_, "x": 20, "y": 20, "next": {"block": dict(say_what(kind),
                next={"block": blk("rb_add_result", inputs={"TEXT": {"block": {"type": "rb_event", "fields": {"KEY": ""}}}})})}}, **({"fields": fields} if fields else {}))]}}
        await load_state(pg, prog)
        await pg.evaluate("""(() => { const hat = Blockly.getMainWorkspace().getTopBlocks(false)[0];
            Blockly.ContextMenuRegistry.registry.getItem('rb_run_script').callback({ block:hat }); })()""")
        for _ in range(50):
            await pg.wait_for_timeout(100)
            if await pg.is_enabled("#run") and await pg.query_selector(".result"):
                break
        said = [t for n, p_, t in await step_texts(pg) if n == "Note"]
        whole = await pg.eval_on_selector_all(".result-text", "e => e.map(x => x.textContent)")
        check(said and said[0].startswith(kind + ": ") and want in said[0] and whole and "text: " in whole[0],
              f"on the page, the {kind} listener runs with a sample of what arrives ({(said or ['nothing'])[0][:60]!r})")
    page_hat = lambda url, words, label: {"type": "rb_page_when", "fields": {"URL": url, "WORDS": words, "N": 1}, "next": {"block": blk("rb_say", inputs={"TEXT": {"block": {  # noqa: E731
        "type": "text_join", "extraState": {"itemCount": 2}, "inputs": {"ADD0": tx(label + ": "), "ADD1": {"block": {"type": "rb_event", "fields": {"KEY": "changed"}}}}}}})}}
    await load_state(pg, {"blocks": {"languageVersion": 0, "blocks": [dict(page_hat("https://example.com/shop/rye-flour", "Price", "page"), x=20, y=20)]}})
    await pg.evaluate("""(() => { const hat = Blockly.getMainWorkspace().getTopBlocks(false)[0];
        Blockly.ContextMenuRegistry.registry.getItem('rb_run_script').callback({ block:hat }); })()""")
    for _ in range(50):
        await pg.wait_for_timeout(100)
        if await pg.is_enabled("#run") and [t for n, p_, t in await step_texts(pg) if n == "Note"]:
            break
    said = ([t for n, p_, t in await step_texts(pg) if n == "Note"] or [""])[0]
    check(said == "page: - £2.40\n+ £2.65\n- In stock\n+ Only 3 left",
          f"on the page, the web page listener runs with a sample change, watching only the lines with 'Price' ({said!r})")
    two = {"blocks": {"languageVersion": 0, "blocks": [dict(page_hat("http://127.0.0.1:1/watch.html", "Price", "page-part"), x=20, y=20),
                                                       dict(page_hat("http://127.0.0.1:1/watch.html", "", "page-all"), x=20, y=260)]}}
    await load_state(pg, two)
    EXTRA["t_page"] = await export_python(pg, "t_page")
    check('LISTENERS = [("page", "http://127.0.0.1:1/watch.html|Price|1", when_page_1), ("page", "http://127.0.0.1:1/watch.html||1", when_page_2)]' in EXTRA["t_page"]
          and "when the web page http://127.0.0.1:1/watch.html changes (the part with Price), checked every 1 minutes" in EXTRA["t_page"],
          "exported Python watches each web page with its words and interval")
    listen_all = {"blocks": {"languageVersion": 0, "blocks": [dict({"type": t, "x": 20, "y": 20 + 120 * i, "next": {"block": say_what(k)}}, **({"fields": f} if f else {}))
                                                              for i, (t, f, k, w) in enumerate(hats)]}}
    listen_all["blocks"]["blocks"][0]["next"]["block"]["next"] = {"block": blk("rb_mqtt_publish", fields={"RETAIN": "FALSE"},
        inputs={"TEXT": {"block": {"type": "text_join", "extraState": {"itemCount": 2}, "inputs": {"ADD0": tx("seen "),
                "ADD1": {"block": {"type": "rb_event", "fields": {"KEY": "text"}}}}}}, "TOPIC": tx("home/proofer/ack")})}
    await load_state(pg, listen_all)
    EXTRA["t_listen"] = await export_python(pg, "t_listen")
    check('LISTENERS = [("mqtt", "home/proofer/temperature", when_mqtt_1), ("webhook", "bake-done", when_webhook_1), ("email", "flour", when_email_1), '
          '("feed", "", when_feed_1), ("folder", "drop", when_folder_1), ("github", "", when_github_1), '
          '("github_issue", "sample-baker/sourdough-chart", when_github_issue_1), ("github_release", "sample-baker/sourdough-chart", when_github_release_1), '
          '("calendar", "15", when_calendar_1), '
          '("discord", "anything", when_discord_1), ("slack", "anything", when_slack_1), '
          '("ha_event", "zha_event|kitchen remote", when_ha_event_1)]' in EXTRA["t_listen"]
          and '"""when Home Assistant event zha_event happens with kitchen remote"""' in EXTRA["t_listen"]
          and "R.main(START_SCRIPTS, RECEIVERS, SCHEDULES, HA_WATCHES, TELEGRAM_WATCHES, listeners=LISTENERS, can=CAN)" in EXTRA["t_listen"],
          "exported Python lists every listener")
    await pg.evaluate("document.getElementById('io-name').value = 't_listen'")
    files = {f["name"]: f["text"] for f in await pg.evaluate("window.__exportFiles()")}
    ini = files["second-thought.ini"]
    check(all(x in ini for x in ("[mqtt]", "MQTT_HOST = ", "[web requests]", "WEBHOOK_SECRET = ", "[email]", "[github]", "[calendar]", "feeds = ",
                                 "[discord]", "DISCORD_BOT_TOKEN = ", "DISCORD_CHANNEL_ID = ", "[slack]", "SLACK_BOT_TOKEN = ", "SLACK_CHANNEL_ID = "))
          and "paho-mqtt" in files["requirements.txt"] and "run-on-schedule.sh" in files, "a listening program's settings ask for each connection it listens to")
    mq = [tcall("read_mqtt", topic="zigbee2mqtt/+"), tcall("publish_mqtt", topic="zigbee2mqtt/oven_plug/set", message="OFF"), tcall("publish_mqtt", topic="home/#", message="x")]
    status, steps, items = await agent_run(pg, ["mqtt", "mqtt_act"], mq + [fin("ok")], answer="Allow", export="t_ls_mqtt")
    check(status.startswith("done") and "zigbee2mqtt/leak_sensor_sink: {\"water_leak\": false" in step_of(steps, 1, 6, "read_mqtt")
          and "MQTT \u2192 zigbee2mqtt/oven_plug/set" in [n for n, *_ in steps] and "can't publish to a topic with + or #" in step_of(steps, 3, 6, "publish_mqtt"),
          "the MQTT tools read topics with wildcards and publish after asking (sample broker on the page)")
    for svc, want_found, chan in (("discord", "Bake-along is Sunday", "#baking"), ("slack", "Oven's free from 2pm", "#kitchen")):
        status, steps, items = await agent_run(pg, [svc, svc + "_send"], [tcall("search_" + svc, text=want_found.split()[0]), tcall("send_" + svc, text="See you there")] + [fin("ok")],
                                               answer="Allow", export="t_ls_" + svc)
        check(status.startswith("done") and want_found in step_of(steps, 1, 6, "search_" + svc)
              and any(n.startswith(svc.capitalize() + " \u2192 " + chan) for n, *_ in steps) and "Allow this?" in [n for n, *_ in steps],
              f"the {svc.capitalize()} tools search the sample channel, and send after asking")

    print("Homey")
    hm = [tcall("find_homey_devices", search="light"), tcall("set_homey_device", device="Kitchen light", capability="onoff", value="off"),
          tcall("set_homey_device", device="Front door lock", capability="locked", value=False), tcall("run_homey_flow", flow="good night"),
          tcall("homey_variable", name="Loaves this week"), tcall("set_homey_device", device="Toaster", capability="onoff", value="on"),
          tcall("set_homey_device", device="Kitchen light", capability="dim", value="bright"), tcall("list_homey_flows")]
    status, steps, items = await agent_run(pg, ["homey_read", "homey_act"], hm + [fin("ok")], steps=12, answer="Allow", export="t_hm_agent")
    names = [n for n, *_ in steps]
    check(status.startswith("done") and "Kitchen light (Kitchen, light): onoff=on, dim=0.8" in step_of(steps, 1, 12, "find_homey_devices")
          and "Homey: Kitchen light" in names and "Homey flow started" in names and names.count("Allow this?") == 5
          and "no Homey device called \u201cToaster\u201d" in step_of(steps, 6, 12, "set_homey_device") and "isn't a number" in step_of(steps, 7, 12, "set_homey_device")
          and "Baking mode (advanced)" in step_of(steps, 8, 12, "list_homey_flows"),
          f"Homey tools find devices, switch them and start flows after asking (once per step, even to unlock), and explain mistakes ({names.count('Allow this?')} asks)")
    num_ = lambda v: {"block": {"type": "math_number", "fields": {"NUM": v}}}  # noqa: E731
    hm_prog = script(blk("rb_add_result", inputs={"TEXT": {"block": {"type": "rb_homey_value", "inputs": {"CAPABILITY": tx("measure_temperature"), "DEVICE": tx("Proofing box")}}}}),
                     blk("rb_homey_set", inputs={"DEVICE": tx("Living room lamp"), "CAPABILITY": tx("dim"), "VALUE": num_(0.25)}),
                     blk("rb_add_result", inputs={"TEXT": {"block": {"type": "rb_homey_value", "inputs": {"CAPABILITY": tx("dim"), "DEVICE": tx("Living room lamp")}}}}),
                     blk("rb_homey_set_variable", inputs={"NAME": tx("Kitchen note"), "VALUE": tx("Feed the starter")}),
                     blk("rb_add_result", inputs={"TEXT": {"block": {"type": "rb_homey_variable", "inputs": {"NAME": tx("Kitchen note")}}}}),
                     blk("rb_homey_flow", inputs={"NAME": tx("Baking mode")}),
                     blk("rb_add_result", inputs={"TEXT": {"block": {"type": "lists_length", "inputs": {"VALUE": {"block": {"type": "rb_homey_find", "inputs": {"TEXT": tx("kitchen")}}}}}}}),
                     blk("rb_result"))
    await load_state(pg, hm_prog)
    status = await run_program(pg)
    items = await pg.eval_on_selector_all(".result-text", "e => e.map(x => x.textContent)")
    check(status.startswith("done") and items == ["26.4", "0.25", "Feed the starter", "5"], f"the Homey blocks read, set, run flows and change variables in the sample home ({items})")
    EXTRA["t_hm_blocks"] = await export_python(pg, "t_hm_blocks")
    hm_listen = {"blocks": {"languageVersion": 0, "blocks": [{"type": "rb_homey_when", "x": 20, "y": 20, "fields": {"DEVICE": "Washing machine", "CAPABILITY": "measure_power"},
                 "next": {"block": blk("rb_say", inputs={"TEXT": {"block": {"type": "text_join", "extraState": {"itemCount": 2}, "inputs": {"ADD0": tx("homey: "),
                          "ADD1": {"block": {"type": "rb_event", "fields": {"KEY": "text"}}}}}}})}}]}}
    await load_state(pg, hm_listen)
    await pg.evaluate("""(() => { const hat = Blockly.getMainWorkspace().getTopBlocks(false)[0];
        Blockly.ContextMenuRegistry.registry.getItem('rb_run_script').callback({ block:hat }); })()""")
    for _ in range(40):
        await pg.wait_for_timeout(100)
        if await pg.is_enabled("#run"):
            break
    said = [t for n, p_, t in await step_texts(pg) if n == "Note"]
    check(said == ["homey: Washing machine measure_power: 412 \u2192 3.1"], f"on the page, the Homey listener runs with a sample change ({said})")
    EXTRA["t_hm_listen"] = await export_python(pg, "t_hm_listen")
    check('LISTENERS = [("homey", "Washing machine|measure_power", when_homey_1)]' in EXTRA["t_hm_listen"], "exported Python listens for the Homey change")
    await pg.evaluate("document.getElementById('io-name').value = 't_hm_listen'")
    files = {f["name"]: f["text"] for f in await pg.evaluate("window.__exportFiles()")}
    check("[homey]" in files["second-thought.ini"] and "HOMEY_API_KEY = " in files["second-thought.ini"] and "run-on-schedule.sh" in files,
          "a Homey program's settings ask for HOMEY_URL and HOMEY_API_KEY")

    await load_state(pg, script(blk("rb_wait", fields={"UNIT": "s"}, inputs={"SECS": nm(30)}), blk("rb_add_result", inputs={"TEXT": tx("too late")}), blk("rb_result")))
    EXTRA["t_maxsec"] = await export_python(pg, "t_maxsec")

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
