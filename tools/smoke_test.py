#!/usr/bin/env python3
"""A short check against the real model services, with your own keys.

The tests in tests/ use stand-ins that behave like the services do according to their documentation. This makes a
handful of small, real calls to each service you have a key for, so you can see that the parts the stand-ins can't
prove actually work: Claude's structured replies and streaming, continuing a cut-off reply, the agent's step shape
and a real tool call, and which JSON mode every other service accepts.

    python tools/smoke_test.py              # every service with a key
    python tools/smoke_test.py claude       # only the services whose names contain these words

Keys come from the environment or a second-thought.ini (in this folder, the current folder or your home folder),
exactly as an exported program finds them. Each service gets a few short questions, so the whole run costs a few
pence; the tokens used are printed at the end. Llama is checked only if LLAMA_BASE_URL is set.
"""
import asyncio
import contextlib
import io
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
RT = {"__name__": "second_thought_runtime", "__file__": str(ROOT / "python" / "runtime.py")}
exec(compile((ROOT / "python" / "runtime.py").read_text(encoding="utf-8"), RT["__file__"], "exec"), RT)  # noqa: S102
Runtime, PROVIDERS, MODELS = RT["Runtime"], RT["PROVIDERS"], RT["MODELS"]

results = []  # (service, check, PASS / FAIL / SKIP / NOTE, detail)
FAILED = object()  # what attempt() gives back when a check raised (None is a normal result for some calls)

_log = Runtime.log


def _quiet_log(self, *a, **kw):
    """The runtime's own run log is kept (for the checks) but not printed, so the report stays readable."""
    with contextlib.redirect_stdout(io.StringIO()):
        return _log(self, *a, **kw)


Runtime.log = _quiet_log


def report(service, check, ok, detail=""):
    results.append((service, check, ok if isinstance(ok, str) else ("PASS" if ok else "FAIL"), detail))
    print(f"  {results[-1][2]:<5} {service}: {check}" + (f"  ({detail})" if detail else ""), flush=True)


def fresh(tier):
    """A runtime on one model, with no backups (so a failure isn't hidden by a backup answering)."""
    R = Runtime()
    R.reset()
    R.tier = R.primary = tier
    R.backups = []
    return R


def labels(R):
    return [t[1] for t in R.trace]


async def attempt(service, check, coro):
    try:
        return await coro
    except Exception as e:  # noqa: BLE001 - every failure is reported, then the next check runs
        report(service, check, False, f"{type(e).__name__}: {str(e)[:160]}")
        return FAILED


async def check_claude():
    s = "Claude"
    if not os.environ.get("ANTHROPIC_API_KEY"):
        report(s, "all checks", "SKIP", "no ANTHROPIC_API_KEY")
        return []
    tier, used = "quick", []

    R = fresh(tier)
    n = await attempt(s, "structured reply (a number)", R.ask_number("What is 6 times 7? Reply with the number."))
    if n is not FAILED:
        report(s, "structured reply (a number)", n == 42 and not R.no_schema,
               "constrained" if not R.no_schema else "the model refused the reply shape, so it fell back to checking afterwards")
    used.append(R)

    R = fresh(tier)
    rec = await attempt(s, "structured reply (records)", R.ask_record("name, rise hours", "Two common bread doughs and how long each rises.", many=True))
    if rec is not FAILED:
        report(s, "structured reply (records)", len(rec) >= 1 and not R.no_schema, f"{len(rec)} records")
    used.append(R)

    R = fresh(tier)

    async def add(a, b):
        return RT["num"](a) + RT["num"](b)
    tools = [{"kind": "block", "name": "add", "desc": "Adds two numbers and gives back the sum.", "inputs": "a: number; b: number",
              "params": ["a", "b"], "fn": add, "ask": False}]
    if await attempt(s, "agent", R.agent("Use the add tool to add 2 and 3, then give the sum as your answer.", 4, tools, plan=True)) is not FAILED:
        steps = R.agent_steps()
        used_add = any(st["tool"] == "add" and st["status"] == "done" for st in steps)
        answered = any(st["status"] == "answer" for st in steps)
        report(s, "agent step shape accepted", not R.no_schema, "constrained" if not R.no_schema else "shape refused, checked afterwards instead")
        report(s, "agent called a typed tool and answered", used_add and answered,
               ", ".join(f"{st['tool'] or '-'}:{st['status']}" for st in steps) + (f" · answer: {R.draft[:40]!r}" if R.draft else ""))
    used.append(R)

    os.environ["RB_STREAM"] = "yes"
    R = fresh(tier)
    out = await attempt(s, "streaming", R.ask_text("In one short sentence, what is autolyse in bread making?"))
    os.environ.pop("RB_STREAM", None)
    if out is not FAILED:
        report(s, "streaming", bool(out.strip()), f"{len(out)} characters")
    used.append(R)

    limit = RT["MAX_TOKENS"]
    RT["MAX_TOKENS"] = 40  # small on purpose, so the reply is cut off and has to be continued
    R = fresh(tier)
    out = await attempt(s, "cut-off reply continued", R.ask_text("Write about 150 words on why bakers use a levain."))
    RT["MAX_TOKENS"] = limit
    if out is not FAILED:
        report(s, "cut-off reply continued", "Reply continued" in labels(R),
               ("still cut short after continuing (expected with a tiny limit)" if "Cut short" in labels(R) else "joined") + f", {len(out)} characters")
    used.append(R)
    return used


async def check_other(name, tier):
    R = fresh(tier)
    n = await attempt(name, "structured reply (a number)", R.ask_number("What is 6 times 7? Reply with the number."))
    if n is not FAILED:
        model = RT["MODELS"].get(tier)
        mode = R.json_modes.get((name, model), "schema")
        report(name, "structured reply (a number)", n == 42, f"answer {n}")
        labels_ = {"schema": "JSON output" if name == "Gemini" else "the full JSON Schema", "object": "plain JSON mode only",
                   "none": "none: replies are checked afterwards"}
        report(name, "JSON mode it accepts", "NOTE", labels_[mode])
    return [R]


async def main(only):
    want = lambda name: not only or any(w in name.lower() for w in only)  # noqa: E731
    print("Second Thought: checking the real services\n", flush=True)
    used = []
    if want("claude"):
        used += await check_claude()
    if want("gemini"):
        if os.environ.get("GEMINI_API_KEY"):
            used += await check_other("Gemini", "gemini-quick")
        else:
            report("Gemini", "all checks", "SKIP", "no GEMINI_API_KEY")
    for name, pv in PROVIDERS.items():
        if not want(name) or name == "Perplexity":
            continue
        if name == "Llama" and not os.environ.get("LLAMA_BASE_URL"):
            continue
        if pv["signup"] and not pv["key"]:
            report(name, "all checks", "SKIP", f"no {pv['key_env']}")
            continue
        used += await check_other(name, pv["prefix"] + "quick")
    totals = {}
    for R in used:
        for who, (tin, tout) in R.usage.items():
            t = totals.setdefault(who, [0, 0])
            t[0] += tin
            t[1] += tout
    fails = [r for r in results if r[2] == "FAIL"]
    print("\nTokens used: " + (" · ".join(f"{w}: {a:,} in, {b:,} out" for w, (a, b) in totals.items()) or "none"))
    print(f"{sum(r[2] == 'PASS' for r in results)} passed, {len(fails)} failed, {sum(r[2] == 'SKIP' for r in results)} skipped.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main([a.lower() for a in sys.argv[1:]])))
