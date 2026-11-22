"""The Runtime: run state, logging, memory, drafts, output, scripts and schedules.

Part of the second_thought package. tools/sync.py joins these files, in order, into
python/runtime.py, which is what ships inside every exported program and the page.
"""
import asyncio
import contextlib
import copy
import datetime
import hashlib
import json
import math
import os
import random
import re
import sys
import time
from .settings import RUNTIME_VERSION, WHERE_KEYS, on_github_actions
from .providers import CURRENCY, ModelCalls, amount_text, dollars, fixed_rate, band_text, call_cost, model_byline, model_label, money, other_maker_tiers, per_dollar, rate_note
from .core import (BUDGET, BUDGET_DOLLARS, BUDGET_MONEY, CAPABILITIES, Finish, HA_WATCH_SECONDS, LOG_DIR, MAX_DEPTH, MAX_SCRIPTS, MAX_SECONDS, MAX_STEPS,
    MEMORY_FILE, MESSAGE_VALUE, MODEL_OVERRIDE, Picture, Retryable, RunError, SCHEMAS,
    _locked, _need_picture, _private_open, _short, _write_json, clean_svg, exact_checks, field_list, num, parse_rules, record_schema, review_verdicts,
    round_js, stuck_rule, to_bool, to_list, to_record, to_str)
from .connectors import Connections, get_url
from .core import markdown_to_telegram
from .mcp import MCPTools
from .agent import AgentTools
from .spending import ACTION_KINDS, Spending, any_allowance, check_plans, reported_lines, usage_text
from .doctor import Doctor
from .update import Updates
from .settings import said_no, said_yes, tr  # noqa: F401
# ---- package only: tools/sync.py leaves everything above this line out of python/runtime.py ----
import unicodedata  # noqa: E402 - below the line, so python/runtime.py has it too (settings.py doesn't import it)


# GitHub Actions turns a line starting with this into an error annotation on the run's page (a workflow command,
# not words for people). Newlines inside it are written %0A.
ACTIONS_ERROR = "::error::"
ACTIONS_ERROR_TITLED = "::error title={title}::"  # an error on the run's page with a heading of its own


class _Channel:
    """One way a question reaches you when nobody's at the keyboard (#434). The small set of jobs every channel
    shares: ask a question (with optional choices), wait for the answer up to a time limit, and say who answered.
    Telegram is the first; ntfy and Home Assistant's actionable notifications come later behind the same jobs."""
    name = ""

    def __init__(self, rt):
        self.rt = rt

    async def ask(self, question, choices=(), timeout_s=300, default=""):
        """Sends the question and waits up to timeout_s seconds. Gives (answer, who): the first reply as (text,
        sender), or (default, '') when the time limit runs out."""
        raise NotImplementedError


class _TelegramChannel(_Channel):
    name = "telegram"

    async def ask(self, question, choices=(), timeout_s=300, default=""):
        rt = self.rt
        chat = next(iter(rt._tg_chats()), "")
        if not chat:
            raise RunError(tr("Telegram needs a chat to send to: set TELEGRAM_CHAT_ID {where_keys}. Send your bot a message first; the program then says which chat it came from.", where_keys=WHERE_KEYS))
        text = tr("Second Thought: {question}", question=question)
        if choices:
            text += "\n" + "\n".join(f"{i}. {to_str(c)}" for i, c in enumerate(choices, 1)) + "\n" + tr("Reply with a number or the words.")
        sent_at = time.time()
        await rt._tg("sendMessage", {"chat_id": chat, "text": markdown_to_telegram(text), "parse_mode": "HTML"})
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            for m in await rt.tg_fetch(wait=int(max(0, min(25, deadline - time.monotonic())))):
                if m.get("chat") != chat or not to_str(m.get("text", "")).strip():
                    continue
                if m.get("date") and m["date"] < sent_at - 5:
                    continue  # an older message, not an answer to this question
                return to_str(m["text"]).strip(), m.get("sender") or ""
        return default, ""


class Runtime(ModelCalls, Connections, MCPTools, AgentTools, Spending, Doctor, Updates):
    def __init__(self):
        self.vars = {}
        self.receivers = {}
        self.client = None
        self.gemini = None
        self.no_schema = set()      # (Claude model, reply shape) pairs Claude refused, so that shape isn't sent to it again
        self.json_modes = {}         # (service, model) -> the JSON mode that service accepts: "schema", "object" or "none"
        self.schedule_mode = False
        self.transient_memory = {}   # kept across runs while this program keeps running
        self.reset()

    def _lock(self, name):
        """An asyncio lock, made the first time it's needed, inside the running event loop: Python 3.9 ties a lock to
        the loop that's current when it's made, and exported programs make Runtime before their loop starts. Making it
        involves no await, so two tasks asking at once still share one lock."""
        locks = self.__dict__.setdefault("_locks", {})
        if name not in locks:
            locks[name] = asyncio.Lock()
        return locks[name]

    # ----- run state -----
    def reset(self):
        self.vars.clear()
        self.task = ""
        self.draft = ""
        self.draft_tier = None      # the model that wrote the current draft, for the run log's "who checked" (#426)
        self._last_how = ""        # how the last approval was given, for the receipt's "allowed:" (#431)
        self._receipt_where = ""   # which block or agent step the action belongs to (#431)
        self.problems = []
        self.approved = None
        self.answer = ""
        self.result = []
        self.out_of_rounds_hit = False
        self.last_error = ""
        self.instructions = ""
        self.chats = {}
        self.reflect = None          # the review loop running now: earlier problems and its best draft so far
        self.checkpoints = {}        # 'save checkpoint' snapshots, by name
        self.usage = {}  # provider -> [tokens in, tokens out]
        self.cost = [0.0, True]      # what the run's model calls cost in US dollars, and whether every one had a known price
        self.tiers_used = []         # the tiers that answered, for each key's allowances at the end
        self.budget = BUDGET          # budget = 50000 in second-thought.ini caps every run; a 'limit this run' block changes it
        # The same in money at list prices: budget_dollars = 0.50, or budget_money = 0.40 in the program's currency (which
        # wins). budget_dollars is what's checked, in US dollars; the amount and its currency are what's shown.
        self.budget_amount, self.budget_unit = (BUDGET_MONEY, CURRENCY) if BUDGET_MONEY else (BUDGET_DOLLARS, "usd")
        self.budget_dollars = self.budget_amount / per_dollar(self.budget_unit) if self.budget_amount else 0
        self.ask_first = set()       # set by 'ask me before' blocks: "ha", "messages", "files"
        self._allowance_said = set()  # the kinds whose allowance stop was already said this run (#432)
        self.trace = []              # every log line, for save_log
        self._pending = []           # model calls since the last log line: who answered, how long, tokens, the prompt
        self.agent_trace = []        # the most recent agent's steps, for the "agent's steps" block
        self.run_started = time.time()
        self.max_seconds = MAX_SECONDS  # max_seconds = 600 stops any run that takes longer
        self.programs = []           # names of saved programs running inside this run, innermost last
        self._rules_noted = False    # the "rules saved beside the program" note is logged once per run (#428)
        self.calls = 0
        self.steps = 0
        self.depth = 0
        self.started = 0
        self.timer_start = time.monotonic()
        self.journal, self.replay, self.replay_pos = getattr(self, "journal", None), None, 0
        self.tier = os.environ.get("RB_MODEL_TIER", globals().get("DEFAULT_TIER", "default"))
        self.primary = self.tier
        # The default reviewer for review blocks: same, another (another maker's model with a key) or a named
        # tier. A review block's own "checked by" choice wins over this (#426).
        self.reviewer = os.environ.get("RB_REVIEWER", "")
        self.backup_used = 0
        # Backup models, tried in order when the primary fails on a step. RB_BACKUPS="openai-default,default" overrides.
        backups = os.environ.get("RB_BACKUPS")
        if backups is not None and backups.strip().lower() in ("none", "off", "no"):
            backups = ""
        backups = [b.strip() for b in backups.split(",")] if backups is not None else list(globals().get("BACKUPS", []))
        self.backups = [b for i, b in enumerate(backups) if b and b != self.primary and b not in backups[:i]]
        self.tasks = set()
        self.ending = False
        self.error = None
        self.msg_waiters = {}
        self.msg_waiting = 0

    def get(self, name):
        return self.vars.get(name, 0)

    def push_args(self, args):
        if self.depth >= MAX_DEPTH:
            raise RunError(tr("A My Blocks block called itself too many times."))
        self.depth += 1
        saved = {k: self.vars[k] for k in args if k in self.vars}
        missing = [k for k in args if k not in self.vars]
        self.vars.update(args)
        return saved, missing

    def pop_args(self, token):
        saved, missing = token
        self.depth -= 1
        for k in missing:
            self.vars.pop(k, None)
        self.vars.update(saved)

    def unsupported(self, kind):
        raise RunError(tr("The block '{kind}' can't run outside the block editor.", kind=kind))

    def tick(self):
        self.steps += 1
        if self.steps > MAX_STEPS:
            raise RunError(tr("Stopped after {max_steps} steps. A loop may never end; check repeat and while blocks.", max_steps=MAX_STEPS))

    # ----- logging -----
    def log(self, label, text=None, status=None, calls=True):
        """calls=True: attach the model calls made since the last line. calls=False: a note written between a model call
        and its step, which leaves the calls for the step. A list: exactly these calls (the agent hands each step its own)."""
        if isinstance(calls, list):
            pass
        elif calls:
            calls, self._pending = self._pending, []
        else:
            calls = []
        meta = self._calls_summary(calls)
        self.trace.append((time.time(), label, to_str(text) if text else "", status or "", meta, [c["prompt"] for c in calls]))
        head = f"\n▸ {label}" + (f"  [{status}]" if status else "")
        print(head, flush=True)
        if text:
            for line in to_str(text).splitlines() or [""]:
                print("    " + line, flush=True)
        if meta:
            print("    · " + meta, flush=True)

    @staticmethod
    def _calls_summary(calls):
        """'Claude · 1.4 s · 812 in, 120 out' for the model calls behind one step (several for a repair or a backup)."""
        if not calls:
            return ""
        if all(c["who"].startswith("reused") for c in calls):
            return "reused from the run that stopped: no new call"
        who = ", ".join(dict.fromkeys(c["who"] for c in calls))
        secs = sum(c["secs"] for c in calls)
        tin, tout = sum(c["in"] for c in calls), sum(c["out"] for c in calls)
        failed = sum(1 for c in calls if not c["ok"])
        return ((f"{len(calls)} calls · " if len(calls) > 1 else "") + f"{who} · {secs:.1f} s · {tin:,} in, {tout:,} out" +
                (f" · {failed} failed" if failed else ""))

    def _prompt_text(self, prompt, history, picture):
        """The prompt as the model received it, for the saved log."""
        parts = [f"[instructions]\n{self.instructions}"] if self.instructions else []
        parts += [f"[{h['role']}]\n{to_str(h['content'])}" for h in (history or [])]
        parts.append(("[user]\n" if parts else "") + to_str(prompt) + ("\n[+ a picture]" if picture is not None else ""))
        return "\n\n".join(parts)

    async def _timed_call(self, t, prompt, want_json, picture, history, web):
        """One call on one model, remembered (time, tokens, prompt) for the next log line."""
        start, before = time.monotonic(), [sum(u[i] for u in self.usage.values()) for i in (0, 1)]
        ok = False
        try:
            text = await self._call_tier(t, prompt, want_json, picture, history, web)
            ok = True
            return text
        finally:
            after = [sum(u[i] for u in self.usage.values()) for i in (0, 1)]
            if after != before:
                cost = call_cost(t, after[0] - before[0], after[1] - before[1])
                self.cost = [self.cost[0] + (cost or 0), self.cost[1] and cost is not None]
                self.tiers_used.append(t)
                if cost:
                    self.spend(t, cost)
            self._pending.append({"who": f"{model_byline(t)} ({band_text(t)})", "secs": time.monotonic() - start, "in": after[0] - before[0],
                                  "out": after[1] - before[1], "ok": ok, "prompt": self._prompt_text(prompt, history, picture)})

    # ----- Claude -----
    @property
    def current_tier(self):
        return MODEL_OVERRIDE.get() or self.tier

    def _count(self, provider, tokens_in, tokens_out):
        u = self.usage.setdefault(provider, [0, 0])
        u[0] += tokens_in or 0
        u[1] += tokens_out or 0

    def budget_text(self):
        """The money budget as it was set, in its currency: '$0.50', '£0.40', '¥75'."""
        return amount_text(self.budget_amount, self.budget_unit)

    # ----- Named inputs (#442): declared on the page, given as --input town=Rye, or by name in an MCP call -----
    @staticmethod
    def input_value(name, kind, raw):
        """(value, None) for a value given for an input, as its kind, or (None, why) if it won't do. The page's
        inputValue does the same."""
        s = to_str(raw).strip()
        if not s:
            return None, tr("Input {name} needs a value.", name=name)
        if kind == "number":
            if not re.fullmatch(r"[+-]?(\d+([.,]\d*)?|[.,]\d+)", s):
                return None, tr("Input {name} must be a number, not {value}.", name=name, value=s)
            n = float(s.replace(",", "."))
            return (int(n) if n.is_integer() else n), None
        if kind == "yesno":
            t = s.lower()
            if t in ("yes", "y", "true", "1", "on", tr("Yes").lower()):
                return True, None
            if t in ("no", "n", "false", "0", "off", tr("No").lower()):
                return False, None
            return None, tr("Input {name} must be yes or no, not {value}.", name=name, value=s)
        if kind == "date":
            try:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
                    raise ValueError
                datetime.date.fromisoformat(s)
            except ValueError:
                return None, tr("Input {name} must be a date like 2026-11-21, not {value}.", name=name, value=s)
        return s, None

    def give_inputs(self, declared, given):
        """Sets the values of the program's inputs from what was given ({name: raw}), each by its kind, with the defaults
        for the rest. Returns why it can't, or None."""
        known = {d[0].lower(): d for d in declared}
        for name in given:
            if name.lower() not in known:
                return tr("There's no input called {name}. Its inputs: {names}.", name=name,
                          names=", ".join(d[0] for d in declared) or "-")
        got = {k.lower(): v for k, v in given.items()}
        values = {}
        for name, kind, default in declared:
            value, why = self.input_value(name, kind, got.get(name.lower(), default))
            if why:
                return why
            values[name.lower()] = value
        self.inputs = values
        return None

    @staticmethod
    def cli_inputs():
        """{name: value} from --input name=value on the command line, or the line that says how to write one."""
        given, args = {}, sys.argv[1:]
        for i, a in enumerate(args):
            if a == "--input" or a.startswith("--input="):
                pair = a[len("--input="):] if a.startswith("--input=") else (args[i + 1] if i + 1 < len(args) else "")
                name, eq, value = pair.partition("=")
                if not eq or not name.strip():
                    return None, tr("--input wants a name and a value, like --input town=Rye.")
                given[name.strip()] = value
        return given, None

    def input(self, name, kind="text", default=""):
        """What an 'input' block gives: the value given when the program started, else its default."""
        key = to_str(name).strip().lower()
        if key in getattr(self, "inputs", {}):
            return self.inputs[key]
        value, why = self.input_value(name, kind, default) if to_str(default).strip() else ("", None)
        return "" if why else value

    def tokens_used(self):
        return sum(u[0] + u[1] for u in self.usage.values())

    def set_budget(self, n, unit="tokens"):
        """'limit this run': unit is tokens, or a currency: "dollars" (US), "gbp", "eur", "jpy" or "cny"."""
        if unit != "tokens":
            n = max(0.0, num(n))
            self.budget_amount, self.budget_unit = n, ("usd" if unit == "dollars" else unit)
            self.budget_dollars = n / per_dollar(self.budget_unit) if n else 0
            self.log(tr("Budget"), tr("This run stops before a model call once it has spent {x} at list prices (spent so far: {x2}).",
                                      x=self.budget_text(), x2=money(self.cost[0], self.budget_unit)) if n else tr("No money budget for this run."), tr("set"))
            return
        n = max(0, round_js(num(n)))
        self.budget = n
        self.log(tr("Budget"), tr("This run stops before a model call once it has used {x} tokens (used so far: {x2}).", x=format(n, ','), x2=format(self.tokens_used(), ','))
                 if n else tr("No token budget for this run."), tr("set"))

    # ----- Asking before actions -----
    ASK_FIRST = {"ha": tr("any smart home action (Home Assistant, Homey or MQTT)"), "messages": tr("sending messages and announcements"),
                 "files": tr("saving files"), "all": tr("all of these")}

    def ask_before(self, kind):
        kinds = {"ha", "messages", "files"} if kind == "all" else {kind}
        self.ask_first |= kinds
        self.log(tr("Ask first"), tr("From now on, the program asks you before {x}.", x=self.ASK_FIRST.get(kind, kind)), tr("set"))

    def dry_run(self):
        """True in a test (--test) or a rehearsal (--rehearse, or rehearse = yes): a rehearsal runs for real, models
        and reading included, but nothing is sent, switched, saved or spent (#430)."""
        return getattr(self, "testing", False) or getattr(self, "rehearsing", False)

    def _skip_action(self, what):
        """True when an action must not happen (a test or a rehearsal): the log says what would have happened."""
        if getattr(self, "testing", False):
            self.log(tr("Test run"), tr("Not done, because this is a test: {what}", what=what), tr("skipped"))
            return True
        if getattr(self, "rehearsing", False):
            self.log(tr("Rehearsal"), tr("Not done, because this is a rehearsal: {what}", what=what), tr("skipped"))
            return True
        return False

    async def _allowed(self, kinds, what):
        """True if the action may go ahead. Asks first when an 'ask me before' block covers it. In a test (--test)
        or a rehearsal (--rehearse), nothing acts: it says what it would have done. An action that reaches one of its
        kind's allowances (allow_<kind>_hourly/_daily, on by default) does not act: the run says so once and carries on
        reading (#432). An action that goes ahead gets a receipt, and is counted, (#431)."""
        if self._skip_action(what):
            return False
        problem = self._action_allowance_problem(kinds)
        if problem:
            self._say_allowance_once(problem)
            return False
        if not (self.ask_first & set(kinds)):
            self._receipt(what, tr("no asking, approved at the first run") if getattr(self, "_first_run_ok", False) else tr("no asking"), kinds=kinds)
            return True
        return await self.confirm(what, kinds=kinds)

    def _say_allowance_once(self, problem):
        """Says once per run, per kind, that an allowance has stopped this run acting (#432)."""
        kind, text = problem
        if kind in self._allowance_said:
            return
        self._allowance_said.add(kind)
        self.log(tr("Allowance reached"), text, tr("stopped"))

    def nobody_here(self):
        """True when nobody can answer a question: an unattended scheduled run, or a program serving as an MCP tool."""
        return getattr(self, "mcp_mode", False) or (self.schedule_mode and not sys.stdin.isatty())

    async def confirm(self, what, kinds=()):
        """Shows what the program is about to do and waits for a yes. Unattended scheduled runs say no, unless
        approve_by = telegram is set: then the question goes to your phone (#305). A yes writes the action's
        receipt and counts it (#431, #432)."""
        if self.dry_run():  # in a test or a rehearsal the action itself is skipped (see _allowed), so nobody needs asking
            return True
        if self.nobody_here():
            if os.environ.get("RB_APPROVE_BY", "").strip().lower() == "telegram":
                ok = await self._approve_telegram(what)
                if ok:
                    self._receipt(what, self._last_how, getattr(self, "_receipt_where", ""), kinds=kinds)
                return ok
            self.log(tr("Not done"), tr("{what} needs your approval, and nobody is at the keyboard.", what=what), tr("refused"))
            return False
        if await self.approve("Allow this? " + what):
            self._last_how = tr("yes at the keyboard")
            self._receipt(what, self._last_how, getattr(self, "_receipt_where", ""), kinds=kinds)
            return True
        self.log(tr("Not done"), tr("{what} was refused, so nothing happened.", what=what), tr("refused"))
        return False

    def _approval_code(self):
        """A fresh four-digit code for one Telegram question (#305): a reply counts only with it, and each question has its own."""
        return f"{random.randint(0, 9999):04d}"

    async def _approve_telegram(self, what):
        """Asks on Telegram when nobody is at the keyboard (#305): the question goes to TELEGRAM_CHAT_ID with a fresh
        four-digit code, and only a reply from that chat with that code, before the time runs out, counts. Anything else,
        or no answer, is a no. Never answered from a stopped run's journal: the person says yes, now, each time."""
        chat = next(iter(self._tg_chats()), "")
        if not os.environ.get("TELEGRAM_BOT_TOKEN", "") or not chat:
            self.log(tr("Not done"), tr("{what} needs your approval, approve_by = telegram is set, but TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID {where_keys} are not.", what=what, where_keys=WHERE_KEYS), tr("refused"))
            return False
        code = self._approval_code()
        await self._tg("sendMessage", {"chat_id": chat, "text": tr("Second Thought: allow {what}? Reply yes {code} within 5 minutes.", what=what, code=code)})
        deadline = time.monotonic() + getattr(self, "_approve_wait", 300)
        while time.monotonic() < deadline:
            for m in await self.tg_fetch(wait=max(0, min(30, deadline - time.monotonic()))):
                words = set(m["text"].lower().split())
                if m["chat"] != chat or code not in words:
                    continue
                if any(said_no(w) for w in words):
                    self.log(tr("Not done"), tr("{what} was refused on Telegram by {who}, so nothing happened.", what=what, who=m["sender"] or tr("someone")), tr("refused"))
                    return False
                self.log(tr("Approved on Telegram"), tr("{who} approved {what} by replying yes {code} on Telegram.", who=m["sender"] or tr("someone"), what=what, code=code), tr("approved"))
                self._last_how = tr("yes {code} on Telegram, by {who}", code=code, who=m["sender"] or tr("someone"))
                return True
        self.log(tr("Not done"), tr("{what} wasn't approved on Telegram in time, so nothing happened.", what=what), tr("refused"))
        return False

    # ----- Resuming after a stop -----
    # While a program runs, each finished model call, each answer you give and each message or Home Assistant action is
    # written to a journal next to the program. A run that finishes deletes it. If a run stops part-way, the next start
    # can replay it: the blocks run again from the top, and every step that matches the journal is reused instead of
    # repeated (no new tokens, no asking twice, nothing sent twice). At the first step that differs, the rest runs live.
    def _journal_path(self):
        prog = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else ""
        if not prog or not os.path.isfile(prog):
            return None, None
        with open(prog, "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()[:16]
        base = os.path.splitext(os.path.basename(prog))[0]
        return os.path.join(os.path.dirname(prog), f".{base}.resume.jsonl"), digest

    def _receipts_path(self):
        """The receipts file next to the program: one private line per action that went ahead (#431)."""
        prog = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else ""
        if not prog or not os.path.isfile(prog):
            return None
        base = os.path.splitext(os.path.basename(prog))[0]
        return os.path.join(os.path.dirname(prog), f".{base}.receipts.jsonl")

    @staticmethod
    def _rules_path():
        """The rules file next to the program: rules offered when someone said no at an approve step (#428)."""
        prog = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else ""
        if not prog or not os.path.isfile(prog):
            return None
        base = os.path.splitext(os.path.basename(prog))[0]
        return os.path.join(os.path.dirname(prog), f".{base}.rules.json")

    def _extra_rules(self):
        """The rules saved beside the program, checked in every review without changing the program file (#428)."""
        path = self._rules_path()
        if not path:
            return []
        try:
            with open(path, encoding="utf-8") as f:
                rules = json.load(f)
        except (OSError, ValueError):
            return []
        return [to_str(r).strip() for r in rules if isinstance(rules, list) and to_str(r).strip()]

    def _save_rule(self, rule):
        """Appends an offered rule to the rules file beside the program (#428); returns the path, or None."""
        path = self._rules_path()
        if not path:
            return None
        rules = []
        try:
            with open(path, encoding="utf-8") as f:
                held = json.load(f)
            if isinstance(held, list):
                rules = [to_str(r) for r in held]
        except (OSError, ValueError):
            rules = []
        rule = to_str(rule).strip()
        if not rule or rule in rules:
            return path
        rules.append(rule)
        try:
            with _private_open(path, "w") as f:
                f.write(json.dumps(rules, ensure_ascii=False, indent=1) + "\n")
        except OSError:
            return None
        return path

    def _receipt(self, what, how, where="", kinds=()):
        """Appends one line to the receipts file (#431): when, what (the approval question's sentence), which block
        or agent step, how it was allowed, its kinds (for the action allowances, #432), and a fingerprint of the line
        before, so a missing or altered line shows. The action is counted on this computer from here (#432)."""
        self._count_action(kinds)
        path = self._receipts_path()
        if not path:
            return
        prev = hashlib.sha256(b"").hexdigest()
        try:
            with open(path, "rb") as f:
                for line in f:
                    if line.strip():
                        prev = hashlib.sha256(line.rstrip(b"\n")).hexdigest()
        except OSError:
            pass
        rec = {"t": time.time(), "what": to_str(what), "where": to_str(where), "how": to_str(how),
               "kinds": sorted(set(k for k in kinds if k in ACTION_KINDS)), "prev": prev}
        try:
            with _private_open(path, "a") as f:
                f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
        except OSError:
            pass

    def show_receipts(self, days=7):
        """--receipts: prints the last week's receipts and says whether the chain is broken (#431). Gives the exit code."""
        path = self._receipts_path()
        if not path or not os.path.isfile(path):
            print(tr("No receipts yet: nothing this program has done to the world is recorded."))
            return 0
        try:
            with open(path, "rb") as f:
                raw_lines = [l for l in f.read().split(b"\n") if l.strip()]
        except OSError as e:
            print(tr("Couldn't read {path} ({err}).", path=path, err=_short(to_str(e), 120)))
            return 1
        broken = False
        prev = hashlib.sha256(b"").hexdigest()
        recs = []
        for raw in raw_lines:
            try:
                rec = json.loads(raw.decode("utf-8"))
            except ValueError:
                broken = True
                continue
            if not isinstance(rec, dict) or rec.get("prev") != prev:
                broken = True
            prev = hashlib.sha256(raw).hexdigest()
            if isinstance(rec, dict):
                recs.append(rec)
        cutoff = time.time() - days * 86400
        shown = [r for r in recs if isinstance(r.get("t"), (int, float)) and r["t"] >= cutoff]
        print(tr("Receipts from the last week ({n} lines):", n=len(shown)))
        for r in shown:
            when = datetime.datetime.fromtimestamp(r["t"]).strftime("%Y-%m-%d %H:%M")
            what = to_str(r.get("what"))
            if r.get("where"):
                what += f" ({r['where']})"
            print(tr("{when}  {what}  allowed: {how}", when=when, what=what, how=to_str(r.get("how"))))
        if len(recs) > len(shown):
            print(tr("({n} older lines are not shown.)", n=len(recs) - len(shown)))
        if broken:
            print(tr("The chain is broken: a line is missing or was edited."))
            return 1
        print(tr("The chain is intact: every line carries the fingerprint of the one before."))
        return 0

    # ----- --report and --status (#435) -----

    REPORT_DAYS = 7  # the weekly account: saved logs and receipts from the last week

    def _receipts_data(self, days):
        """(receipts from the last `days` days, whether the chain is broken), or (None, False) with no receipts file:
        the shared reader behind --report/--status (#431, #435)."""
        path = self._receipts_path()
        if not path or not os.path.isfile(path):
            return None, False
        try:
            with open(path, "rb") as f:
                raw_lines = [l for l in f.read().split(b"\n") if l.strip()]
        except OSError:
            return None, False
        broken = False
        prev = hashlib.sha256(b"").hexdigest()
        recs = []
        for raw in raw_lines:
            try:
                rec = json.loads(raw.decode("utf-8"))
            except ValueError:
                broken = True
                continue
            if not isinstance(rec, dict) or rec.get("prev") != prev:
                broken = True
            prev = hashlib.sha256(raw).hexdigest()
            if isinstance(rec, dict):
                recs.append(rec)
        cutoff = time.time() - days * 86400
        return [r for r in recs if isinstance(r.get("t"), (int, float)) and r["t"] >= cutoff], broken

    def _log_paths(self, days):
        """The saved run logs from the last `days` days, oldest first: logs/<program>-<date>-<time>.md."""
        prog = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else ""
        if not prog or not os.path.isfile(prog):
            return []
        folder = os.path.join(os.path.dirname(prog), LOG_DIR)
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y%m%d")
        try:
            names = [n for n in os.listdir(folder) if n.endswith(".md") and len(n.split("-")) >= 2 and n.split("-")[-2] >= cutoff]
        except OSError:
            return []
        return [os.path.join(folder, n) for n in sorted(names)]

    def _parse_log(self, text):
        """One saved log's facts for --report (#435): whether it stopped with an error, its review outcomes in order,
        how many actions it refused, and its rules-by-round tables as {rule: [met, rounds]}."""
        sections = re.findall(r"^## \d+\. (.+?) \[([^\]]+)\]", text, re.M)
        failed = any(l.startswith("- Stopped with an error:") for l in text.splitlines())
        reviews = [st for label, st in sections if label == tr("Review") or re.fullmatch(r"Review, round \d+", label)]
        refused = sum(1 for _, st in sections if st == tr("refused"))
        rules = {}
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            if re.match(r"^## \d+\. " + re.escape(tr("Rules by round")) + r" \[table\]$", lines[i]):
                i += 1
                while i < len(lines) and lines[i] in ("", "~~~~"):  # the log puts the table behind a ~~~~ fence
                    i += 1
                while i < len(lines) and lines[i].startswith("|"):
                    cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                    if len(cells) > 1 and not all(set(c) <= {"-", ":"} for c in cells) and cells[0] != tr("Rule"):
                        met = sum(1 for c in cells[1:] if c == tr("met"))
                        agg = rules.setdefault(cells[0], [0, 0])
                        agg[0] += met
                        agg[1] += len(cells) - 1
                    i += 1
                continue
            i += 1
        return {"failed": failed, "reviews": reviews, "refused": refused, "rules": rules}

    def _report_data(self, days):
        """Everything --report and --status say, from the saved logs, the receipts and the spending record (#435):
        {runs, first, revised, best, failed, plain, refused, rules, recs, broken, spent}."""
        runs = []
        for path in self._log_paths(days):
            try:
                with open(path, encoding="utf-8") as f:
                    runs.append(self._parse_log(f.read()))
            except OSError:
                pass
        recs, broken = self._receipts_data(days)
        spent = sum(v for entry in self._ledger_read()["keys"].values() for v in (entry.get("hours") or {}).values())
        first = revised = best = failed = plain = refused = 0
        rules = {}
        for run in runs:
            failed += run["failed"]
            refused += run["refused"]
            rev = run["reviews"]
            if not rev or (tr("approved") not in rev and tr("failed") not in rev):
                plain += 1
            elif rev[0] == tr("approved"):
                first += 1
            elif tr("approved") in rev:
                revised += 1
            else:
                best += 1
            for rule, (met, n) in run["rules"].items():
                agg = rules.setdefault(rule, [0, 0])
                agg[0] += met
                agg[1] += n
        return {"runs": len(runs), "first": first, "revised": revised, "best": best, "failed": failed, "plain": plain,
                "refused": refused, "rules": rules, "recs": recs, "broken": broken, "spent": spent}

    def show_report(self, days=REPORT_DAYS):
        """--report: the weekly account (#435) — runs and how they went, actions done and refused, cost, and rules by
        round — read from the saved logs (save_log = yes), the receipts (#431) and the spending record. Gives the exit
        code: 1 when the receipts' chain is broken."""
        prog = os.path.splitext(os.path.basename(sys.argv[0] or "program"))[0] or "program"
        d = self._report_data(days)
        if not d["runs"] and d["recs"] is None and not d["spent"]:
            print(tr("No runs, receipts or spending recorded for {prog} yet.", prog=prog))
            return 0
        print(tr("Report for {prog}, last {days} days:", prog=prog, days=days))
        if d["runs"]:
            print(tr("Runs: {n} saved logs — {first} passed review first time, {revised} after revising, {best} as a best effort, {failed} with an error, {plain} without a review.",
                     n=d["runs"], first=d["first"], revised=d["revised"], best=d["best"], failed=d["failed"], plain=d["plain"]))
            print(tr("Refused, in those logs: {n}.", n=d["refused"]))
            if d["rules"]:
                always = sum(1 for met, n in d["rules"].values() if met == n)
                parts = [tr("{rule}: met {met} of {n} rounds", rule=rule, met=met, n=n)
                         for rule, (met, n) in sorted(d["rules"].items()) if met < n]
                if parts:
                    print(tr("Rules that failed at least once in those logs: {list}", list=", ".join(parts)))
                print(tr("{k} of {r} rules were met in every round.", k=always, r=len(d["rules"])))
            else:
                print(tr("No rules were checked in those logs."))
        else:
            print(tr("No saved logs in the last {days} days (save_log = yes keeps one per run in logs/).", days=days))
        if d["recs"] is None:
            print(tr("No receipts yet: nothing this program has done to the world is recorded."))
        else:
            print(tr("Actions done, from the receipts of the last {days} days: {n}.", days=days, n=len(d["recs"])))
            chain = (tr("The chain is broken: a line is missing or was edited.") if d["broken"]
                     else tr("The chain is intact: every line carries the fingerprint of the one before."))
            print(chain)
        print(tr("Cost, counted on this computer at list prices:"))
        for line in usage_text().splitlines():
            print(line)
        return 1 if d["broken"] else 0

    def show_status(self, days=REPORT_DAYS):
        """--status: the same account in one line (#435), for a home server with a dozen programs. Gives the exit code."""
        prog = os.path.splitext(os.path.basename(sys.argv[0] or "program"))[0] or "program"
        d = self._report_data(days)
        if not d["runs"] and d["recs"] is None and not d["spent"]:
            print(tr("No runs, receipts or spending recorded for {prog} yet.", prog=prog))
            return 0
        print(tr("{prog}: {runs} runs ({ok} passed, {failed} with an error), {actions} actions done, {refused} refused, {cost} spent.",
                 prog=prog, runs=d["runs"], ok=d["first"] + d["revised"], failed=d["failed"],
                 actions=len(d["recs"] or []), refused=d["refused"], cost=dollars(d["spent"])))
        return 1 if d["broken"] else 0

    async def _journal_start(self):
        """At the start of a run: offer to pick up a run that stopped, then start a fresh journal."""
        self.journal, self.replay, self.replay_pos, self._replay_noted = None, None, 0, False
        path, digest = self._journal_path()
        if not path:
            return
        old = []
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as f:
                    lines = [json.loads(l) for l in f if l.strip()]
                if lines and lines[0].get("program") == digest:
                    old = lines[1:]
                elif lines:
                    print(tr("\n(A previous run stopped part-way, but the program has changed since, so it starts afresh.)"), flush=True)
            except (OSError, ValueError):
                old = []
        if old:
            choice = os.environ.get("RB_RESUME", "").strip().lower()
            if choice in ("1", "yes", "true", "on"):
                use = True
            elif choice in ("0", "no", "false", "off"):
                use = False
            elif sys.stdin.isatty():
                print("\n? " + (tr("The last run stopped part-way, after 1 saved step.") if len(old) == 1 else
                              tr("The last run stopped part-way, after {n} saved steps.", n=len(old))), flush=True)
                use = said_yes(await self._input(tr("Pick up where it stopped, reusing those? [y/n] > ")))
            else:
                use = False
                print(tr("\n(The last run stopped part-way. Set resume = yes in second-thought.ini to pick up where it stopped.)"), flush=True)
            if use:
                self.replay = old
                self.log(tr("Resuming"), (tr("Picking up the run that stopped: 1 saved step will be reused instead of repeated.") if len(old) == 1 else
                          tr("Picking up the run that stopped: {n} saved steps will be reused instead of repeated.", n=len(old))), tr("resume"))
        try:
            self.journal = _private_open(path)  # prompts and answers: only you can read it (#307)
            self.journal.write(json.dumps({"program": digest, "started": time.time()}) + "\n")
            self.journal.flush()
        except OSError:
            self.journal = None
        self._journal_file = path

    def _journal_end(self, finished):
        if self.journal:
            self.journal.close()
            self.journal = None
            if finished:
                try:
                    os.remove(self._journal_file)
                except OSError:
                    pass
            elif on_github_actions():  # the record of what's done isn't kept between runs there
                print(tr("Fix the problem above, then start it again with Run workflow on the Actions tab."), flush=True)
            else:
                print(tr("Run the program again to pick up where it stopped."), flush=True)

    @staticmethod
    def _key(*parts):
        return hashlib.sha256(json.dumps(parts, default=str, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:20]

    def _replayed(self, kind, key):
        """(True, value) if the next saved step is this one; otherwise (False, None), and replaying ends at the first difference."""
        if self.replay is None:
            return False, None
        if self.replay_pos < len(self.replay):
            e = self.replay[self.replay_pos]
            if e.get("kind") == kind and e.get("key") == key:
                self.replay_pos += 1
                self._record(kind, key, e.get("value"))
                if self.replay_pos == len(self.replay):
                    self.replay = None
                    self.log(tr("Caught up"), tr("That was the last saved step. From here the run carries on as usual."), tr("resume"), calls=False)
                return True, e.get("value")
            self.log(tr("Run differs here"), tr("From this step the run isn't the same as the one that stopped, so the rest runs afresh."),
                     tr("resume"), calls=False)
        self.replay = None
        return False, None

    def _record(self, kind, key, value):
        if self.journal:
            try:
                line = json.dumps({"kind": kind, "key": key, "value": value}, ensure_ascii=False)
            except (TypeError, ValueError):
                return  # something that can't be saved (a picture): that step will simply run again
            self.journal.write(line + "\n")
            self.journal.flush()

    async def _call(self, prompt, want_json=False, picture=None, history=None, web=False):
        key = self._key("call", self.current_tier, to_str(prompt), want_json, history, web, self.instructions,
                        hashlib.sha256(picture.data).hexdigest() if isinstance(picture, Picture) else None)
        hit, v = self._replayed("call", key)
        if hit:
            self._pending.append({"who": "reused from the run that stopped", "secs": 0.0, "in": 0, "out": 0, "ok": True, "prompt": to_str(prompt)})
            return v
        out = await self._call_live(prompt, want_json, picture, history, web)
        self._record("call", key, out if want_json else to_str(out))
        return out

    async def _journaled(self, kind, key, live):
        hit, v = self._replayed(kind, key)
        if hit:
            return v
        out = await live()
        self._record(kind, key, out)
        return out

    # ----- The You blocks: the keyboard, or the approve_by channel when nobody's there (#434) -----
    def _nobody_to_type(self):
        """True when no one can type an answer: an MCP tool call, or a run from a scheduler (--schedule, or
        --run-schedule from cron, Task Scheduler or GitHub Actions), where stdin isn't a terminal."""
        return getattr(self, "mcp_mode", False) or not sys.stdin.isatty()

    def _you_channel(self):
        """The channel the You blocks ask on when nobody's at the keyboard: approve_by's, for now (#434). None when
        approve_by isn't a channel, so the blocks keep reading the keyboard."""
        if os.environ.get("RB_APPROVE_BY", "").strip().lower() == "telegram":
            return _TelegramChannel(self)
        return None

    async def _ask_channel(self, question, choices=(), mins=0, default=""):
        """Asks on the channel when nobody's at the keyboard (#434). Gives (answer, who), or None when there's no
        channel to ask on, so the block reads the keyboard as before. The channel's answer is never journaled: the
        person answers now, each time, not from a stopped run's journal."""
        channel = self._you_channel()
        if channel is None or self.dry_run() or not self._nobody_to_type():
            return None
        timeout_s = round(num(mins) * 60)  # the block's time limit in seconds; 0 waits not at all
        answer, who = await channel.ask(question, choices, timeout_s, to_str(default))
        if who:
            self.log(tr("Question on {channel}", channel=channel.name), _short(to_str(question), 120),
                     tr("{who} answered: {answer}", who=who, answer=_short(answer, 200)), tr("answered"))
        else:
            self.log(tr("Question on {channel}", channel=channel.name), _short(to_str(question), 120),
                     tr("No answer within {mins} min, so the default was used: {answer}", mins=num(mins), answer=_short(answer, 200)), tr("timed out"))
        return answer, who

    async def ask_me(self, q, mins=0, default=""):
        q = to_str(q)
        got = await self._ask_channel(q, mins=mins, default=default)
        if got is not None:
            self.answer = got[0]
            return got[0]
        out = await self._journaled("ask_me", self._key(q), lambda: self._ask_me_live(q))
        self.answer = out
        return out

    async def approve(self, text, offer=False, mins=0, default=""):
        # offer=True is the "I approve …" block: a no there offers the reason as a new rule (#428); action asks don't
        got = await self._ask_channel(to_str(text), choices=[tr("Yes"), tr("No")], mins=mins, default=default)
        if got is not None:
            return said_yes(got[0]) if got[1] else said_yes(default)  # a timeout takes the block's default
        return await self._journaled("approve", self._key(to_str(text)), lambda: self._approve_live(text, offer))

    async def choose(self, items, mins=0, default=""):
        items = to_list(items)
        got = None if not items else await self._ask_channel(tr("Choose one") + ": " + "; ".join(_short(it, 60) for it in items),
                                                            choices=[_short(it, 80) for it in items], mins=mins, default=default)
        if got is not None:
            reply = to_str(got[0]).strip()
            if reply.isdigit() and 1 <= int(reply) <= len(items):
                return items[int(reply) - 1]
            for it in items:
                if to_str(it).strip().lower() == reply.lower():
                    return it
            if not got[1]:  # a timeout: the default when it's one of the items, else the first
                for it in items:
                    if to_str(it).strip().lower() == to_str(default).strip().lower():
                        return it
                return items[0]
            return reply
        return await self._journaled("choose", self._key(items), lambda: self._choose_live(items))

    async def ha_call(self, service, entity, data_text=""):
        key = self._key(to_str(service), to_str(entity), to_str(data_text))
        hit, v = self._replayed("ha_call", key)
        if hit:
            self.log(tr("Home Assistant: {x}", x=to_str(service).strip()), tr("{entity}: already done before the stop, so not done again.", entity=to_str(entity)), tr("reused"))
            return v
        out = await self._ha_call_live(service, entity, data_text)
        self._record("ha_call", key, out)
        return out

    async def ha_notify(self, target, text):
        key = self._key(to_str(target), to_str(text))
        hit, _ = self._replayed("ha_notify", key)
        if hit:
            self.log(tr("Notification → {x}", x=to_str(target).strip() or "persistent_notification"), tr("Already sent before the stop, so not sent again."), tr("reused"))
            return
        await self._ha_notify_live(target, text)
        self._record("ha_notify", key, True)

    async def ha_speak(self, text, player):
        key = self._key(to_str(text), to_str(player))
        hit, _ = self._replayed("ha_speak", key)
        if hit:
            self.log(tr("Spoken on {x}", x=to_str(player).strip() or tr("a speaker")), tr("Already said before the stop, so not said again."), tr("reused"))
            return
        await self._ha_speak_live(text, player)
        self._record("ha_speak", key, True)

    async def ask_text(self, p):
        p = to_str(p)
        if not p.strip():
            raise RunError(tr("An 'ask Claude' block is empty."))
        out = await self._call("Answer the request below. Reply with only the answer, no preamble.\n\n" + p)
        self.log(tr("Ask Claude: {p}", p=_short(p, 60)), out, tr("done"))
        return out

    async def ask_yesno(self, p):
        p = to_str(p)
        if not p.strip():
            raise RunError(tr("A yes/no block is empty."))
        r = await self._call('Answer the question. Reply with only JSON: {"answer": true} or {"answer": false}.\n\nQuestion:\n' + p, SCHEMAS["yesno"])
        yes = r["answer"] is True
        self.log(tr("Yes or no: {p}", p=_short(p, 60)), tr("Yes") if yes else tr("No"), tr("done"))
        return yes

    async def ask_number(self, p):
        p = to_str(p)
        if not p.strip():
            raise RunError(tr("An 'ask for a number' block is empty."))
        r = await self._call('Reply with only JSON: {"number": <a single number>}.\n\nRequest:\n' + p, SCHEMAS["number"])
        n = num(r["number"])
        self.log(tr("Number: {p}", p=_short(p, 60)), n, tr("done"))
        return n

    async def ask_list(self, p):
        p = to_str(p)
        if not p.strip():
            raise RunError(tr("An 'ask for a list' block is empty."))
        r = await self._call('Reply with only JSON: {"items": [<short strings>]}, no other text.\n\nRequest:\n' + p, SCHEMAS["list"])
        items = [to_str(i) for i in r["items"] if to_str(i)]
        self.log(tr("List: {p}", p=_short(p, 60)), "\n".join("- " + i for i in items) or tr("(empty list)"), tr("{items} items", items=len(items)))
        return items

    async def rewrite(self, text, how):
        text, how = to_str(text), to_str(how)
        if not text.strip():
            raise RunError(tr("A 'rewrite' block has nothing to rewrite."))
        out = await self._call("Rewrite the text below. Instruction: " + how + "\nReply with only the rewritten text.\n\nText:\n" + text)
        self.log(tr("Rewrite: {how}", how=_short(how, 60)), out, tr("done"))
        return out

    async def extract(self, what, text):
        what, text = to_str(what), to_str(text)
        if not text.strip():
            raise RunError(tr("An 'extract' block has no text to read."))
        out = await self._call("From the text below, extract: " + what + "\nReply with only what you extracted, nothing else.\n\nText:\n" + text)
        self.log(tr("Extract: {what}", what=_short(what, 60)), out, tr("done"))
        return out

    async def score(self, text, criteria):
        text, criteria = to_str(text), to_str(criteria)
        r = await self._call("Score the text from 1 to 10 against these criteria: " + criteria +
                             '\nBe strict and consistent. Reply with only JSON: {"score": <1-10>}.\n\nText:\n' + text, SCHEMAS["score"])
        s = max(0, min(10, num(r["score"])))
        self.log(tr("Score: {text}", text=_short(text, 50)), f"{s}/10", tr("done"))
        return s

    async def better(self, a, b, criteria):
        a, b, criteria = to_str(a), to_str(b), to_str(criteria)
        r = await self._call("Which text is better for: " + criteria +
                             '?\nReply with only JSON: {"pick": 1 or 2, "reason": "<one sentence>"}.\n\nText 1:\n' + a + "\n\nText 2:\n" + b, SCHEMAS["pick"])
        second = num(r["pick"]) == 2
        self.log(tr("Pick the better one"), (tr("Picked the second") if second else tr("Picked the first")) +
                 (". " + to_str(r.get("reason")) if r.get("reason") else ""), tr("done"))
        return b if second else a

    # ----- Conversations, instructions, web search -----
    def set_instructions(self, text):
        self.instructions = to_str(text).strip()
        self.log(tr("Instructions for Claude"), self.instructions or tr("(cleared)"), tr("set"))

    async def chat(self, name, message):
        key = to_str(name).strip().lower() or "chat"
        message = to_str(message).strip()
        if not message:
            raise RunError(tr("The 'chat' block has no message."))
        hist = self.chats.setdefault(key, [])
        reply = await self._call(message, history=list(hist))
        hist += [{"role": "user", "content": message}, {"role": "assistant", "content": reply}]
        del hist[:-40]
        self.log(tr("Chat {x}: {message}", x=to_str(name).strip(), message=_short(message, 50)), reply, tr("turn {x}", x=len(hist) // 2))
        return reply

    def chat_reset(self, name):
        self.chats.pop(to_str(name).strip().lower(), None)
        self.log(tr("Conversation {x}", x=to_str(name).strip()), tr("Starting afresh."), tr("reset"))

    async def web_search(self, q):
        q = to_str(q).strip()
        if not q:
            raise RunError(tr("The 'search the web' block is empty."))
        out = await self._call("Search the web and answer briefly, listing the sources you used as plain URLs at the end.\n\nQuery: " + q,
                               web=True)
        self.log(tr("Web search: {q}", q=_short(q, 50)), out, tr("done"))
        return out

    # ----- Records -----
    async def ask_record(self, fields, prompt, many=False):
        fields, prompt = field_list(fields), to_str(prompt).strip()
        if not fields:
            raise RunError(tr("Give the record's fields, separated by commas."))
        if not prompt:
            raise RunError(tr("The 'ask Claude for a record' block has no request."))
        shape = "{" + ", ".join(json.dumps(f) + ": ..." for f in fields) + "}"
        r = await self._call(('Reply with only JSON: {"items": [<objects, each shaped like ' + shape + '>]}' if many else "Reply with only one JSON object shaped like " + shape) +
                             ". Use these exact field names. Numbers as numbers.\n\nRequest:\n" + prompt, record_schema(fields, many))
        if many:
            recs = [to_record(o, fields) for o in r["items"]]
            self.log(tr("Records: {prompt}", prompt=_short(prompt, 55)), "\n".join(" · ".join(f"{f}: {_short(x[f], 40)}" for f in fields) for x in recs), tr("{recs} records", recs=len(recs)))
            return recs
        rec = to_record(r, fields)
        self.log(tr("Record: {prompt}", prompt=_short(prompt, 55)), to_str(rec), tr("done"))
        return rec

    # ----- Prompt library -----
    def prompt(self, name):
        text = globals().get("PROMPTS", {}).get(to_str(name).strip().lower())  # written above the runtime, if the program has any
        if text is None:
            raise RunError(tr("There's no prompt called “{name}” in this program's prompt library.", name=name))
        return text

    # ----- Files -----
    def result_text(self):
        items = self.result if self.result else ([self.draft] if self.draft else [])
        return "\n\n".join(items)

    # ----- Errors and retries -----
    def report_stop(self, msg):
        """The run's last lines when it stops on an error: the reason, and what to do about it when that's known."""
        print(tr("\n✖ Run stopped: {msg}", msg=msg), flush=True)
        hint = self.error_hint(msg)
        if hint:
            print("  " + hint, flush=True)
        if self.calls:  # what the run had used when it stopped, as the end line would have said
            used = " · ".join(tr("{who}: {tokens_in} tokens in, {tokens_out} out", who=who, tokens_in=f"{u[0]:,}", tokens_out=f"{u[1]:,}")
                              for who, u in self.usage.items()) or tr("no tokens used")
            print("\n" + (tr("Stopped · 1 model call") if self.calls == 1 else tr("Stopped · {n} model calls", n=self.calls))
                  + f" · {used}{self.cost_text()}", flush=True)
        if on_github_actions():
            # An annotation: the reason shows on the run's summary page, not only in the step's log.
            note = tr("Run stopped: {msg}", msg=msg) + ("\n" + hint if hint else "")
            print(ACTIONS_ERROR + note.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A"), flush=True)

    @staticmethod
    def error_hint(msg):
        """What to do about a model service's refusal that's worded for programmers, in a line, or ''."""
        low = to_str(msg).lower()
        if "not scoped to a workspace" in low:
            return tr("Your Claude key belongs to a whole Console organisation, not one workspace. Make a key inside a "
                      "workspace (the Console's Workspaces page), or set ANTHROPIC_WORKSPACE_ID {where_keys}.", where_keys=WHERE_KEYS)
        if "credit balance is too low" in low:
            return tr("Your Claude account is out of credit. Add some at https://console.anthropic.com, then run it again.")
        if "invalid x-api-key" in low or "authentication_error" in low:
            return tr("Claude refused the key. Check ANTHROPIC_API_KEY {where_keys}.", where_keys=WHERE_KEYS)
        return ""

    @staticmethod
    def _describe(e):
        return str(e) if isinstance(e, RunError) else f"{type(e).__name__}: {e}"

    def failed(self, e):
        self.last_error = self._describe(e)
        self.log(tr("Something failed, so the 'if it fails' part ran"), self.last_error, tr("handled"))

    @staticmethod
    def attempts(n):
        return max(1, min(10, round_js(num(n)) or 1))

    async def retry_or_raise(self, e, attempt, max_tries):
        self.last_error = self._describe(e)
        status = getattr(e, "status_code", None) or getattr(e, "code", None)
        transient = isinstance(e, Retryable) or (type(e).__module__.startswith(("anthropic", "google")) and
                                                 not (isinstance(status, int) and status in (400, 401, 403, 404)))
        if not transient:
            raise e
        if attempt >= max_tries:
            self.log(tr("Gave up after {attempt} tries", attempt=attempt), self.last_error, tr("failed"))
            raise e
        wait = 2 * attempt
        self.log(tr("Retrying"), tr("Try {attempt} of {max_tries} failed: {last_error}\nTrying again in {wait}s.", attempt=attempt, max_tries=max_tries, last_error=self.last_error, wait=wait), tr("retry {x}", x=attempt + 1))
        await asyncio.sleep(wait)

    # ----- Memory -----
    @staticmethod
    def _mem_key(name):
        key = to_str(name).strip().lower()
        if not key:
            raise RunError(tr("A memory block has no name. Type a name into its name slot."))
        return key

    def _mem_load(self):
        try:
            with open(MEMORY_FILE, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return {}
        now = time.time() * 1000
        return {k: v for k, v in data.items() if not (v.get("expires") and v["expires"] <= now)}

    def _mem_save(self, data):
        _write_json(MEMORY_FILE, data, indent=1)

    @staticmethod
    def _storable(v):
        if isinstance(v, Picture):
            raise RunError(tr("Pictures can only be remembered 'while this page is open'. Save the picture as a file to keep it."))
        if isinstance(v, list):
            return [Runtime._storable(x) for x in v]
        if v is None:
            return ""
        return v if isinstance(v, (str, int, float, bool)) else to_str(v)

    def _mem_write(self, name, value, kind, expires=None):
        with _locked(MEMORY_FILE):  # read, change and save as one step, so another program's save isn't lost
            self._mem_write_now(name, value, kind, expires)

    def _mem_write_now(self, name, value, kind, expires):
        key = self._mem_key(name)
        if kind == "transient":
            self.transient_memory[key] = {"name": to_str(name).strip(), "value": value}
            data = self._mem_load()
            if key in data:
                del data[key]
                self._mem_save(data)
            return
        self.transient_memory.pop(key, None)
        data = self._mem_load()
        data[key] = {"name": to_str(name).strip(), "value": self._storable(value), "kind": kind,
                     "expires": expires, "updated": int(time.time() * 1000)}
        self._mem_save(data)

    def _mem_entry(self, key):
        if key in self.transient_memory:
            return self.transient_memory[key], "transient"
        e = self._mem_load().get(key)
        return (e, "saved") if e else (None, None)

    def remember(self, value, name, kind="transient"):
        self._mem_write(name, value, kind)
        self.log(tr("Remembered “{x}”", x=to_str(name).strip()), _short(value, 120) + "  \u00b7  " +
                 (tr("while running") if kind == "transient" else tr("forever")), tr("saved"))

    def remember_for(self, value, name, n, unit):
        ms = min(365 * 86400000, max(0, num(n)) * {"m": 60000, "h": 3600000, "d": 86400000}.get(unit, 86400000))
        if not ms:
            raise RunError(tr("A 'remember for' block needs a time above zero."))
        expires = int(time.time() * 1000 + ms)
        self._mem_write(name, value, "permanent", expires)
        until = datetime.datetime.fromtimestamp(expires / 1000).strftime("%a %d %b %H:%M")
        self.log(tr("Remembered “{x}”", x=to_str(name).strip()), tr("{value}  ·  until {until}", value=_short(value, 120), until=until), tr("saved"))

    def remember_add(self, value, name, kind="transient"):
        key = self._mem_key(name)
        with _locked(MEMORY_FILE):  # the list is read and saved under one lock, so two programs adding at once both count
            cur, where = self._mem_entry(key)
            items = []
            if cur:
                items = list(cur["value"]) if isinstance(cur["value"], list) else ([] if cur["value"] == "" else [cur["value"]])
            items.append(value)
            if cur and where == "saved":
                self._mem_write(name, items, "permanent", cur.get("expires"))
            else:
                self._mem_write(name, items, "transient" if cur else kind)
        self.log(tr("Added to “{x}”", x=to_str(name).strip()), tr("{items} items", items=len(items)), tr("saved"))

    def recall(self, name):
        e, _ = self._mem_entry(self._mem_key(name))
        if not e:
            return ""
        return list(e["value"]) if isinstance(e["value"], list) else e["value"]

    def remembers(self, name):
        return self._mem_entry(self._mem_key(name))[0] is not None

    def forget(self, name):
        key = self._mem_key(name)
        self.transient_memory.pop(key, None)
        with _locked(MEMORY_FILE):
            data = self._mem_load()
            if key in data:
                del data[key]
                self._mem_save(data)
        self.log(tr("Forgot “{x}”", x=to_str(name).strip()), None, tr("forgotten"))

    def memory_names(self):
        names = {v["name"] for v in self.transient_memory.values()}
        names |= {v["name"] for k, v in self._mem_load().items() if k not in self.transient_memory}
        return sorted(names)

    # Searching notes by what's in them. The page ranks them the same way (memRank in second-thought.html), so the agent
    # finds the same notes in both places: keep the two the same.
    MEMORY_STOP = frozenset("a an and are as at be but by do for from had has have i if in into is it its me my no not of on "
                            "or our so than that the their them then there these they this to was we were what when where "
                            "which who will with you your".split())

    @classmethod
    def memory_terms(cls, text):
        """The words searching uses: letters and digits, in lower case (ligatures, superscripts and wide letters made
        plain), common words left out, and a light trim of English endings (loaves -> loave, proving -> prov, baked -> bak; partial matches catch the rest)."""
        out = []
        for w in re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", to_str(text)).lower()):
            if w in cls.MEMORY_STOP:
                continue
            if len(w) > 4 and w.endswith("ing"):
                w = w[:-3]
            elif len(w) > 3 and w.endswith("ed"):
                w = w[:-2]
            elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
                w = w[:-1]
            out.append(w)
        return out

    @classmethod
    def rank_notes(cls, notes, query, limit=5):
        """notes: [{"name", "value", "updated"}]. The best matches for the query, best first, each with its score.
        BM25 over a note's name (counted twice) and its contents; a word that starts the other (bake, bak) counts half.
        Scores are rounded so the page and Python order them alike; ties go to the newest note, then by name."""
        terms = list(dict.fromkeys(cls.memory_terms(query)))
        if not terms or not notes:
            return []
        docs = [cls.memory_terms(n["name"]) * 2 + cls.memory_terms(n.get("value", "")) for n in notes]
        avg = (sum(len(d) for d in docs) / len(docs)) or 1
        part = lambda t, w: t != w and len(t) >= 3 and len(w) >= 3 and (w.startswith(t) or t.startswith(w))  # noqa: E731
        found = []
        for n, d in zip(notes, docs):
            score = 0.0
            for t in terms:
                tf = sum(1.0 if w == t else 0.5 if part(t, w) else 0.0 for w in d)
                if tf:
                    df = sum(1 for e in docs if any(w == t or part(t, w) for w in e))
                    idf = math.log(1 + (len(docs) - df + 0.5) / (df + 0.5))
                    score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * len(d) / avg))
            if score > 0:
                found.append({"name": n["name"], "value": n.get("value", ""), "updated": n.get("updated"), "score": round(score, 6)})
        found.sort(key=lambda x: (-x["score"], -(x["updated"] or 0), x["name"].lower()))
        return found[:max(1, int(limit))]

    def memory_search(self, query, limit=5):
        """Saved notes about something, best first: [{"name", "value", "updated", "score"}]."""
        now = int(time.time() * 1000)
        notes = [{"name": v["name"], "value": to_str(v["value"]), "updated": now} for v in self.transient_memory.values()]
        notes += [{"name": v["name"], "value": to_str(v["value"]), "updated": v.get("updated") or 0}
                  for k, v in self._mem_load().items() if k not in self.transient_memory]
        return self.rank_notes(notes, query, limit)

    def memory_search_text(self, query, limit=5):
        """What the agent's search_memory tool gives back."""
        query = to_str(query).strip()
        if not query:
            raise RunError(tr("search_memory needs some words to look for."))
        found, total = self.memory_search(query, limit), len(self.memory_names())
        if not found:
            return f"No saved note matches “{query}”." + (f" list_memory gives the names of all {total}." if total else " Nothing is saved yet.")
        when = lambda ms: datetime.datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d") if ms else "earlier"  # noqa: E731
        return (f"Notes matching “{query}”, best first ({len(found)} of {total}):\n" +
                "\n".join(f"- {f['name']} (saved {when(f['updated'])}): {_short(f['value'], 300)}" for f in found))

    # ----- Pictures -----
    _DRAW_RULES = ("Reply with only the SVG code, starting with <svg and ending with </svg>. Use a viewBox, flat shapes and solid fills. "
                   "No scripts, no external images or fonts, no animation. Only add text if the description asks for it.")

    async def _draw(self, prompt, label, picture=None):
        out = await self._call(prompt, picture=picture)
        svg = clean_svg(out)
        if not svg:
            raise Retryable(tr("Claude's drawing came back in a form that can't be used. Run again, or simplify the description."))
        pic = Picture(svg.encode("utf-8"), "image/svg+xml", None, svg)
        self.log(label, tr("Saved to {x}", x=self._picture_path(pic)), tr("drawn"))
        return pic

    async def draw_picture(self, desc):
        desc = to_str(desc).strip()
        if not desc:
            raise RunError(tr("The 'draw a picture' block has no description."))
        return await self._draw("Draw this as a single SVG illustration: " + desc + "\n" + self._DRAW_RULES, "Draw: " + _short(desc, 60))

    async def change_picture(self, pic, how):
        pic = _need_picture(pic, "change picture")
        how = to_str(how).strip()
        if not how:
            raise RunError(tr("The 'change picture' block has no change in it."))
        if pic.svg is not None:
            return await self._draw("Here is an SVG illustration:\n" + pic.svg + "\n\nRedraw it with these changes: " + how +
                                    "\nKeep everything else the same. " + self._DRAW_RULES, "Change picture: " + _short(how, 60))
        return await self._draw("Draw a new SVG illustration of the attached picture, with these changes: " + how + "\n" + self._DRAW_RULES,
                                "Redraw as illustration: " + _short(how, 50), picture=pic)

    async def ask_picture(self, q, pic):
        q = to_str(q).strip()
        pic = _need_picture(pic, "ask Claude about picture")
        if not q:
            raise RunError(tr("The 'ask Claude about picture' block has no question."))
        out = await self._call("Look at the attached picture and answer. Reply with only the answer, no preamble.\n\n" + q, picture=pic)
        self.log(tr("Look at picture: {q}", q=_short(q, 55)), out, tr("done"))
        return out

    async def score_picture(self, pic, criteria):
        pic = _need_picture(pic, "score picture")
        r = await self._call("Score the attached picture from 1 to 10 against these criteria: " + to_str(criteria) +
                             '\nBe strict and consistent. Reply with only JSON: {"score": <1-10>}.', SCHEMAS["score"], picture=pic)
        s = max(0, min(10, num(r["score"])))
        self.log(tr("Score picture: {criteria}", criteria=_short(criteria, 55)), f"{s}/10", tr("done"))
        return s

    def show_picture(self, pic):
        pic = _need_picture(pic, "show picture")
        self.log(tr("Picture"), self._picture_path(pic), tr("shown"))

    def set_task(self, t):
        self.task = to_str(t).strip()
        if not self.task:
            raise RunError(tr("The task is empty. Type what you want into 'set task to'."))
        self.log(tr("Task set"), self.task, tr("set"))

    def _need_task(self):
        if not self.task:
            raise RunError(tr("Add a 'set task to' block before this step."))

    def _need_draft(self):
        if not self.draft:
            raise RunError(tr("There's no draft yet. Put a 'write a first draft' or 'set draft to' block before this step."))

    _WEB_ADDRESS = re.compile(r"https?://|\b[a-z0-9-]+(\.[a-z0-9-]+)*\.(com|org|net|io|dev|ai|app|co\.uk|org\.uk|gov\.uk)\b", re.I)

    async def generate(self, web=False):
        """write a first draft; with web=True ('using the web' ticked, #332) the model can search and read the web."""
        self._need_task()
        self.draft = await self._call("Complete the task below. Reply with only the finished piece, no preamble.\n\nTask:\n" + self.task,
                                      web=bool(web))
        self.draft_tier = self.current_tier  # who wrote the draft, for the review's "who checked" (#426)
        self.problems, self.approved = [], None
        self.log(tr("Write a first draft"), self.draft, tr("done"))
        if not web and self._WEB_ADDRESS.search(self.task or ""):
            self.log(tr("Web address in the task"), tr("The task names a web address, but this step can't open it. Tick 'using the web' on "
                                                       "the block, or put the page's words in the task."), tr("note"))

    async def rework(self, instr):
        self._need_draft()
        instr = to_str(instr).strip()
        if not instr:
            raise RunError(tr("The 'rework the draft' block has no instruction."))
        self.draft = await self._call("Rewrite the draft below following this instruction: " + instr +
                                      "\nKeep it true to the original task. Reply with only the rewritten piece.\n\nTask:\n" +
                                      (self.task or "(none given)") + "\n\nDraft:\n" + self.draft)
        self.draft_tier = self.current_tier
        self.log(tr("Rework: {instr}", instr=_short(instr, 60)), self.draft, tr("done"))

    async def revise(self, web=False):
        self._need_draft()
        if not self.problems:
            self.log(tr("Revise"), tr("No review problems recorded, so nothing to fix."), tr("skipped"))
            return
        fixed = [e for e in (self.reflect or {}).get("earlier", []) if e not in self.problems]
        keep = ("\n\nThese problems were fixed in earlier rounds. Don't bring them back:\n" + "\n".join("- " + e for e in fixed)) if fixed else ""
        self.draft = await self._call("Revise the draft so it fixes every problem listed. Change nothing else that works. "
                                      "Reply with only the improved piece.\n\nTask:\n" + (self.task or "(none given)") +
                                      "\n\nProblems:\n" + "\n".join("- " + p for p in self.problems) + keep + "\n\nDraft:\n" + self.draft,
                                      web=bool(web))
        self.draft_tier = self.current_tier
        self.log(tr("Revise to fix the problems"), self.draft, tr("revised"))

    def set_draft(self, t):
        self.draft = to_str(t)
        self.draft_tier = self.current_tier

    @contextlib.contextmanager
    def reviewing(self):
        """Around a 'review … up to N rounds' loop: remembers each round's verdicts and its best draft."""
        before = self.reflect
        self.reflect = {"earlier": [], "best": None, "round": 0, "same": 0, "last_unmet": [], "rounds": []}
        try:
            yield
        finally:
            self.reflect = before

    def review_table(self):
        """The rules by round as a markdown table, for the run log (#424): met, or not met with the problem."""
        rounds = (self.reflect or {}).get("rounds") or []
        if not rounds:
            return ""
        rules = []
        for r in rounds:
            for v in r["verdicts"]:
                if v["rule"] not in rules:
                    rules.append(v["rule"])
        cell = lambda s: to_str(s).replace("|", "\\|").replace("\n", " ")  # noqa: E731
        lines = ["| " + tr("Rule") + " | " + " | ".join(tr("Round {n}", n=r["round"]) for r in rounds) + " |",
                 "|" + "---|" * (len(rounds) + 1)]
        for rule in rules:
            cells = []
            for r in rounds:
                v = next((x for x in r["verdicts"] if x["rule"] == rule), None)
                cells.append(tr("met") if v and v["met"] else tr("not met") + (": " + cell(v["problem"]) if v and v["problem"] else ""))
            lines.append("| " + cell(rule) + " | " + " | ".join(cells) + " |")
        return "\n".join(lines)

    def reviewer_tier(self, choice=None):
        """The model that checks the draft in a review (#426): the block's 'checked by' choice, else the reviewer
        setting, else the same model. 'another' picks another maker's tier that has a key. Gives back (tier, note);
        note says when no other maker has a key, so the same model checks instead of the run failing."""
        c = to_str(choice if choice not in (None, "") else self.reviewer).strip()
        if c.lower() in ("", "same"):
            return self.current_tier, None
        if c.lower() == "another":
            others = other_maker_tiers(self.current_tier)
            if others:
                return others[0], None
            return (self.current_tier, tr("No other maker's model has a key, so the same model checks the draft. Add a key for another service, or name a model in the review block's 'checked by' choice."))
        return c, None

    async def review(self, criteria, label="Review", in_loop=False, checks=None, reviewer=None):
        self._need_draft()
        rtier, rnote = self.reviewer_tier(reviewer)
        if rnote:
            self.log(tr("Reviewer"), rnote, tr("note"), calls=False)
        rules = parse_rules(criteria)
        extra = [r for r in self._extra_rules() if r not in rules]  # rules saved beside the program are checked too (#428)
        if extra:
            if not getattr(self, "_rules_noted", False):
                self._rules_noted = True
                self.log(tr("New rule"), tr("{n} rules saved beside the program are checked too.", n=len(extra)), tr("note"), calls=False)
            rules = rules + extra
        cv = exact_checks(self.draft, checks)  # the exact checks, worked out by code, no model call (#425)
        loop = self.reflect if in_loop else None
        earlier = ("\n\nEarlier rounds of this review found the problems below. Check each one is still fixed, "
                   "and list it again, in the same words, if it has come back:\n" + "\n".join("- " + e for e in loop["earlier"])) if loop and loop["earlier"] else ""
        if rules:  # written rules are judged by the model; with only exact checks there is no model call (#425)
            rule_list = "\n".join(f"{i}. {r}" for i, r in enumerate(rules, 1)) or to_str(criteria)
            token = MODEL_OVERRIDE.set(rtier)  # the reviewer checks the draft, not the model that wrote it (#426)
            try:
                v = await self._call("You are a strict reviewer. Judge the draft ONLY against these rules, one per line:\n" + rule_list +
                                     "\n\nTask:\n" + (self.task or "(none given)") + "\n\nDraft:\n" + self.draft + earlier +
                                     '\n\nReply with only JSON like {"approved": false, "rules": [{"rule": "the rule\'s own words", "met": false, '
                                     '"problem": "specific fixable problem", "shows": "the words in the draft that show it"}], "problems": ["specific fixable problem"]}. '
                                     "approved is true only if every rule is met; for each rule not met, problem says what to fix and shows quotes the words in "
                                     "the draft that show it; problems repeats the unmet rules' problems as a flat list.", SCHEMAS["review"])
            finally:
                MODEL_OVERRIDE.reset(token)
            res = review_verdicts(rules, v)
            res["verdicts"] = cv + res["verdicts"]
            res["approved"] = all(x["met"] for x in res["verdicts"]) and res["approved"]
            res["problems"] = list(dict.fromkeys([x["problem"] or x["rule"] for x in res["verdicts"] if not x["met"]] + res["problems"]))
            res["met"] = sum(1 for x in res["verdicts"] if x["met"])
            res["unmet"] = [x["rule"] for x in res["verdicts"] if not x["met"]]
        else:
            res = {"approved": all(x["met"] for x in cv),
                   "problems": [x["problem"] or x["rule"] for x in cv if not x["met"]],
                   "verdicts": cv, "met": sum(1 for x in cv if x["met"]), "unmet": [x["rule"] for x in cv if not x["met"]]}
        approved = res["approved"]
        self.approved = approved
        self.problems = [] if approved else (res["problems"] or ["Does not yet meet the criteria."])
        self.verdicts = res["verdicts"]
        if loop is not None:
            loop["round"] += 1
            best = loop["best"]
            if best is None or res["met"] >= best["met"]:  # the best draft meets the most rules; a tie goes to the newer draft
                loop["best"] = {"draft": self.draft, "problems": list(self.problems), "met": res["met"],
                                "total": len(rules) + len(cv), "n": len(self.problems), "round": loop["round"]}
            for p_ in self.problems:
                if p_ not in loop["earlier"]:
                    loop["earlier"].append(p_)
            del loop["earlier"][:-12]
            # No progress: the same rule failed this round as the one before (#424)
            same = not approved and stuck_rule(loop["last_unmet"], res["unmet"]) is not None
            loop["same"] = loop["same"] + 1 if same else 0
            loop["last_unmet"] = list(res["unmet"])
            loop["rounds"].append({"round": loop["round"], "verdicts": res["verdicts"]})
        who = tr("Written by {writer}; checked by {checker}.", writer=model_label(self.draft_tier or self.primary), checker=model_label(rtier))
        if approved:
            if loop is not None and loop.get("rounds"):
                self.log(tr("Rules by round"), self.review_table(), tr("table"))
            self.log(label, tr("Meets every criterion.") + "\n" + who, tr("approved"))
        else:
            self.log(label, "\n".join("- " + p for p in self.problems) + "\n" + who, tr("needs work"))
        return approved

    def stuck(self):
        """True, having said why, once the same rule has failed in two rounds running (#424): revising can't fix it,
        probably because the program lacks something, so the loop stops there and keeps its best draft rather than
        spending its remaining rounds."""
        loop = self.reflect or {}
        if loop.get("same", 0) < 2:
            return False
        self.out_of_rounds_hit = True
        best = loop.get("best")
        if best and best["round"] != loop["round"]:
            self.draft, self.problems, self.approved = best["draft"], list(best["problems"]), False
        if loop.get("rounds"):
            self.log(tr("Rules by round"), self.review_table(), tr("table"))
        self.log(tr("Review stuck"), tr("The same rule failed in two rounds running, so revising can't fix it. The program may need "
                                        "something it wasn't given, such as a web page, a file or a fact: give it that (in the task, say, or "
                                        "through an agent that can read web pages), then run again."), tr("stuck"))
        return True

    def rounds(self, n):
        return max(1, min(6, round_js(num(n)) or 3))

    def out_of_rounds(self):
        self.out_of_rounds_hit = True
        best = (self.reflect or {}).get("best")
        if best and best["round"] != self.reflect["round"]:
            self.draft, self.problems, self.approved = best["draft"], list(best["problems"]), False
            if (self.reflect or {}).get("rounds"):
                self.log(tr("Rules by round"), self.review_table(), tr("table"))
            self.log(tr("Kept the best draft"), tr("Went back to the draft from round {round}: it met the most rules ({n} of {total}). The rounds after it didn't improve on it.", round=best['round'], n=best['met'], total=best['total']), tr("best draft"))
        self.log(tr("Review"), tr("Out of rounds. Keeping the best effort."), tr("failed"))

    # ----- Checkpoints -----
    _SNAPSHOT = ("task", "draft", "problems", "approved", "answer", "result")

    def save_checkpoint(self, name):
        name = to_str(name).strip()
        if not name:
            raise RunError(tr("The 'save checkpoint' block needs a name."))
        state = {k: getattr(self, k) for k in self._SNAPSHOT}
        state["vars"] = dict(self.vars)
        try:
            state = copy.deepcopy(state)
        except Exception:  # noqa: BLE001 - something uncopyable: keep references instead
            state = {k: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v) for k, v in state.items()}
        self.checkpoints[name.lower()] = state
        self.log(tr("Checkpoint “{name}”", name=name), (tr("Saved the task, draft, review, result and variables. Draft: {draft}", draft=_short(self.draft, 80)) if self.draft else tr("Saved the task, draft, review, result and variables.")), tr("saved"))

    def restore_checkpoint(self, name):
        name = to_str(name).strip()
        state = self.checkpoints.get(name.lower())
        if state is None:
            raise RunError(tr("There's no checkpoint called “{name}” in this run. Put a 'save checkpoint' block before this one.", name=name))
        try:  # a copy, so the same checkpoint can be gone back to more than once
            state = copy.deepcopy(state)
        except Exception:  # noqa: BLE001
            state = {k: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v) for k, v in state.items()}
        for k in self._SNAPSHOT:
            setattr(self, k, state[k])
        self.vars.clear()
        self.vars.update(state["vars"])
        self.log(tr("Back to checkpoint “{name}”", name=name), (tr("Restored the task, draft, review, result and variables. Draft: {draft}", draft=_short(self.draft, 80)) if self.draft else tr("Restored the task, draft, review, result and variables.")), tr("restored"))

    # ----- You (the person at the keyboard) -----
    async def _input(self, prompt):
        if getattr(self, "mcp_mode", False):  # stdin is the MCP connection: nobody is there to type
            raise RunError(tr("This step needs an answer typed at the keyboard, but there's no one to type it."))
        async with self._lock("input"):  # one question at the keyboard at a time
            try:
                return await asyncio.to_thread(input, prompt)
            except EOFError:
                raise RunError(tr("This step needs an answer typed at the keyboard, but there's no one to type it."))

    async def _ask_me_live(self, q):
        q = to_str(q)
        if getattr(self, "testing", False):
            return to_str(self._from_test("answer", q))
        print("\n? " + q, flush=True)
        while True:
            a = (await self._input("> ")).strip()
            if a:
                self.answer = a
                return a
            print(tr("  Type an answer first."))

    async def _approve_live(self, text, offer=False):
        if getattr(self, "testing", False):
            return bool(self._from_test("approve", text))
        print(tr("\n? Do you approve this?\n"), flush=True)
        for line in to_str(text).splitlines():
            print("    " + line)
        while True:
            a = (await self._input(tr("Approve? [y/n] > "))).strip().lower()
            if said_yes(a):
                return True
            if said_no(a):
                if offer:
                    await self._offer_rule()  # a no at an "I approve …" block offers the reason as a new rule (#428)
                return False
            print(tr("  Type y or n."))

    async def _offer_rule(self):
        """Someone said no at an approve step: ask why in a sentence, and offer it as a new rule (#428). The rule is
        saved beside the program (.<prog>.rules.json), so reviews check it without the program file changing, and the
        line to add to the review block on the page is shown."""
        why = (await self._input(tr("\n? Why not? In one sentence, as a rule > "))).strip().rstrip(".")
        if not why:
            return
        a = (await self._input(tr('Add "{rule}" to the rules? [y/n] > ', rule=why))).strip().lower()
        if not said_yes(a):
            return
        path = self._save_rule(why)
        if path:
            self.log(tr("New rule"), tr('"{rule}" saved in {path}.', rule=why, path=os.path.basename(path)), tr("note"))
            print(tr("Line to add to the review block's rules on the page: {rule}", rule=why), flush=True)
        else:
            print(tr("Line to add to the review block's rules on the page: {rule}", rule=why), flush=True)

    async def _choose_live(self, items):
        items = to_list(items)
        if getattr(self, "testing", False) and items:
            want = to_str(self._from_test("choose", tr("Choose one")))
            return next((it for it in items if to_str(it) == want), items[0])
        if not items:
            raise RunError(tr("'let me choose from' got an empty list."))
        print(tr("\n? Choose one:"), flush=True)
        for i, it in enumerate(items, 1):
            print(f"  {i}. {_short(it, 80)}")
        while True:
            a = (await self._input(tr("Number > "))).strip()
            if a.isdigit() and 1 <= int(a) <= len(items):
                return items[int(a) - 1]
            print(tr("  Type a number from 1 to {items}.", items=len(items)))

    async def pause(self, note, mins=0):
        if getattr(self, "testing", False):
            return
        got = await self._ask_channel(to_str(note) or tr("Paused."), mins=mins)  # #434: on the channel, any reply (or the time limit) continues
        if got is not None:
            return
        print("\n⏸ " + (to_str(note) or tr("Paused.")), flush=True)
        await self._input(tr("Press Enter to continue > "))

    # ----- Output -----
    def say(self, v):
        if isinstance(v, Picture):
            self.log(tr("Note"), tr("Picture: {x}", x=self._picture_path(v)))
        else:
            self.log(tr("Note"), to_str(v))

    def show(self):
        self.log(tr("Current draft"), self.draft or tr("(no draft yet)"))

    def _result_item(self, v):
        if isinstance(v, Picture):
            return "[picture: " + self._picture_path(v) + "]"
        return to_str(v)

    def add_result(self, v):
        item = self._result_item(v)
        self.result.append(item)
        self.log(tr("Added to result"), item, tr("added"))

    def finish_with(self, v):
        self.result = [self._result_item(v)]
        raise Finish()

    # ----- Lists -----
    def _index(self, lst, where, at, inserting=False):
        n = len(lst)
        if where == "FIRST":
            return 0
        if where == "LAST":
            return n if inserting else n - 1
        if where == "RANDOM":
            return random.randrange(max(1, n))
        if where == "FROM_START":
            return round_js(num(at)) - 1
        return n - round_js(num(at)) + (1 if inserting else 0)

    def list_get(self, lst, mode, where, at=1, var=None):
        lst = list(to_list(lst))
        i = self._index(lst, where, at)
        if i < 0 or i >= len(lst):
            raise RunError(tr("A list block asked for item {x} but the list has {lst} items.", x=i + 1, lst=len(lst)))
        v = lst[i]
        if mode != "GET":
            del lst[i]
            if var is not None:
                self.vars[var] = lst
        return v

    def list_set(self, var, mode, where, at, value):
        if var is None:
            raise RunError(tr("To change a list, put a list variable in the 'in list' slot."))
        lst = list(to_list(self.get(var)))
        i = self._index(lst, where, at, mode == "INSERT")
        if mode == "INSERT":
            lst.insert(max(0, min(i, len(lst))), value)
        else:
            if i < 0 or i >= len(lst):
                raise RunError(tr("A list 'set' block points past the end of the list."))
            lst[i] = value
        self.vars[var] = lst

    # ----- Wait & time -----
    def timer(self):
        return round((time.monotonic() - self.timer_start) * 10) / 10

    def reset_timer(self):
        self.timer_start = time.monotonic()

    def now(self, part):
        d = datetime.datetime.now()
        date = d.strftime("%Y-%m-%d")
        return {"time": d.strftime("%H:%M"), "date": date, "datetime": date + " " + d.strftime("%H:%M"),
                "hour": d.hour, "minute": d.minute, "weekday": d.strftime("%A")}[part]

    async def wait(self, seconds):
        secs = max(0, min(86400, num(seconds)))
        if secs >= 5:
            self.log(tr("Wait"), tr("Waiting {x} seconds", x=format(secs, 'g')))
        await asyncio.sleep(secs)

    async def wait_until_time(self, h, m):
        now = datetime.datetime.now()
        t = now.replace(hour=int(h), minute=int(m), second=0, microsecond=0)
        if t <= now:
            t += datetime.timedelta(days=1)
        self.log(tr("Wait until a time"), tr("Waiting until {time} tomorrow" if t.date() != now.date() else "Waiting until {time}", time=t.strftime("%H:%M")))
        await asyncio.sleep((t - now).total_seconds())

    async def wait_until(self, check, uses_claude=False):
        while not to_bool(await check()):
            await asyncio.sleep(10 if uses_claude else 0.5)

    async def wait_for_message(self, name):
        key = to_str(name).strip().lower()
        self.log(tr("Waiting for “{name}”", name=to_str(name)), tr("Carries on when another script broadcasts this message."))
        fut = asyncio.get_running_loop().create_future()
        self.msg_waiters.setdefault(key, []).append(fut)
        self.msg_waiting += 1
        try:
            MESSAGE_VALUE.set(await fut)
        finally:
            self.msg_waiting -= 1

    # ----- Model -----
    def use_model(self, tier):
        self.tier = tier
        self.log(tr("Model"), tr("Using {x}", x=model_label(tier)))

    @contextlib.asynccontextmanager
    async def using_model(self, tier):
        token = MODEL_OVERRIDE.set(tier)
        self.log(tr("Model"), tr("Using {x} for the blocks inside", x=model_label(tier)))
        try:
            yield
        finally:
            MODEL_OVERRIDE.reset(token)

    # ----- Broadcasts and scripts -----
    def message_value(self):
        return MESSAGE_VALUE.get()

    def broadcast(self, name, value=""):
        key = to_str(name).strip().lower()
        if not key:
            raise RunError(tr("A broadcast block has no message name."))
        waiters = self.msg_waiters.pop(key, [])
        for f in waiters:
            if not f.done():
                f.set_result(value)
        fns = self.receivers.get(key, [])
        if not fns and not waiters:
            self.log(tr("Broadcast “{name}”", name=to_str(name)), tr("Nobody is listening for this message."), tr("no listeners"))
            return []
        self.started += len(fns)
        if self.started > MAX_SCRIPTS:
            raise RunError(tr("Stopped after starting {max_scripts} scripts. A message may be broadcasting itself in a loop.", max_scripts=MAX_SCRIPTS))
        return [self.start_script(fn, value) for fn in fns]

    async def broadcast_and_wait(self, name, value=""):
        tasks = self.broadcast(name, value)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if self.ending:
            raise asyncio.CancelledError()

    # ----- Saved programs run as a block -----
    STATE = ("task", "draft", "problems", "approved", "answer", "result", "out_of_rounds_hit", "instructions", "chats", "last_error",
             "checkpoints", "reflect", "agent_trace")

    async def run_program(self, name, fn, value=""):
        """Runs a saved program's 'when Run is clicked' script with its own draft, result and variables.
        Gives back its result as text. Model calls, the budget and the step limits are shared with this run."""
        name = to_str(name).strip()
        if name.lower() in (p.lower() for p in self.programs):
            raise RunError(tr("The program “{name}” runs itself ({x}), which would never end.", name=name, x=" → ".join(self.programs + [name])))
        if len(self.programs) >= 10:
            raise RunError(tr("Programs inside programs went more than 10 deep, so the run stopped."))
        busy = [t for t in self.tasks if not t.done() and t is not asyncio.current_task()]
        if busy:
            raise RunError(tr("“{name}” can't run while other scripts are running at the same time. Run it from a script that runs on its own (not alongside a broadcast).", name=name))
        saved = {k: getattr(self, k) for k in self.STATE}
        saved_vars = dict(self.vars)
        self.task, self.draft, self.problems, self.approved, self.answer = "", "", [], None, ""
        self.result, self.out_of_rounds_hit, self.instructions, self.chats, self.last_error = [], False, "", {}, ""
        self.checkpoints, self.reflect, self.agent_trace, self.verdicts = {}, None, [], []
        self.vars.clear()
        token = MESSAGE_VALUE.set(value)
        self.programs.append(name)
        self.log(tr("Program: {name}", name=name), (tr("Started with: {value}", value=_short(to_str(value), 200)) if to_str(value).strip() else tr("Started.")), tr("running"))
        try:
            try:
                await fn()
            except Finish:
                pass
            out = "\n\n".join(to_str(x) for x in self.result) if self.result else self.draft
            self.log(tr("Program: {name}", name=name), out or tr("(no result)"), tr("done"))
            return out
        finally:
            self.programs.pop()
            MESSAGE_VALUE.reset(token)
            self.vars.clear()
            self.vars.update(saved_vars)
            for k, v in saved.items():
                setattr(self, k, v)

    def start_script(self, fn, value=""):
        task = asyncio.ensure_future(self._guard(fn, value))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    async def _guard(self, fn, value=""):
        MESSAGE_VALUE.set(value)
        try:
            await fn()
        except asyncio.CancelledError:
            pass
        except Finish:
            self._end()
        except Exception as e:  # noqa: BLE001 - any failure ends the run
            if not self.ending:
                self.error = e
            self._end()

    def _end(self):
        if self.ending:
            return
        self.ending = True
        current = asyncio.current_task()
        for t in list(self.tasks):
            if t is not current:
                t.cancel()

    async def run(self, scripts, label=None):
        label = label or tr("Run")
        self.reset()
        self.run_label = label
        print(f"\n=== {label} · {datetime.datetime.now():%H:%M} ===", flush=True)
        finished = False
        try:
            if not self.schedule_mode and not getattr(self, "mcp_mode", False) and not self.dry_run():
                await self._journal_start()
            code = await self._run(scripts)
            finished = code == 0
            return code
        finally:
            self._journal_end(finished)
            self.save_log()

    async def _run(self, scripts):
        for fn in scripts:
            if isinstance(fn, tuple):
                self.start_script(fn[0], fn[1])
            else:
                self.start_script(fn)
        while self.tasks:
            await asyncio.wait(set(self.tasks), timeout=0.5, return_when=asyncio.FIRST_COMPLETED)
            if self.max_seconds and not self.ending and self.tasks and time.time() - self.run_started > self.max_seconds:
                self.error = RunError(tr("The run took longer than {x} seconds (max_seconds in second-thought.ini), so it stopped.", x=format(self.max_seconds, 'g')))
                self._end()
            if not self.ending and not self.schedule_mode and self.tasks and self.msg_waiting >= len(self.tasks):
                names = ", ".join("“" + k + "”" for k in self.msg_waiters)
                self.error = RunError(tr("Every script is waiting for {names}, but nothing running can send it.", names=names))
                self._end()
        if self.error:
            self.report_stop(str(self.error) if isinstance(self.error, RunError) else f"{type(self.error).__name__}: {self.error}")
            return 1
        text = "\n\n".join(self.result) if self.result else self.draft
        if text:
            print("\n" + "=" * 60 + ("\n" + (tr("RESULT (best effort)") if self.out_of_rounds_hit else tr("RESULT")) + "\n") + "=" * 60, flush=True)
            print(text, flush=True)
        else:
            print(tr("\nThe program ended without a result."), flush=True)
        used = " · ".join(tr("{who}: {tokens_in} tokens in, {tokens_out} out", who=who, tokens_in=f"{u[0]:,}", tokens_out=f"{u[1]:,}")
                          for who, u in self.usage.items()) or tr("no tokens used")
        spare = (" · " + (tr("a backup answered 1 step") if self.backup_used == 1 else tr("a backup answered {n} steps", n=self.backup_used))
                 if self.backup_used else "")
        budget = (" · " + tr("budget {n}", n=f"{self.budget:,}") if self.budget else "") + \
            (" · " + tr("budget {n}", n=self.budget_text()) if self.budget_dollars else "")
        print("\n" + (tr("Done · 1 model call") if self.calls == 1 else tr("Done · {n} model calls", n=self.calls)) + f" · {used}{spare}{budget}{self.cost_text()}", flush=True)
        for line in (self.allowance_lines(self.tiers_used) + reported_lines(low_only=True, hints=False) + self.plan_hints_once()
                     + ([self.allowance_note()] if self.allowance_note() and self.tiers_used else [])):
            print("  " + line, flush=True)
        return 0

    def cost_text(self):
        """' · about $0.03 at list prices' for the end line, or '' when nothing was charged or a model's price isn't known."""
        spent, known = self.cost
        if not known or not self.usage or not spent:
            return ""
        return " · " + tr("{cost} at list prices", cost=money(spent))

    def save_log(self):
        """With save_log = yes in second-thought.ini, writes this run's log to logs/<program>-<date>-<time>.md."""
        if os.environ.get("RB_SAVE_LOG", "").strip().lower() not in ("1", "yes", "true", "on"):
            return
        prog = os.path.splitext(os.path.basename(sys.argv[0] or "program"))[0] or "program"
        start = datetime.datetime.fromtimestamp(self.run_started)
        lines = [f"# {prog}: run log", "",
                 f"- Runtime: {RUNTIME_VERSION}",
                 f"- Started: {start:%Y-%m-%d %H:%M:%S} ({getattr(self, 'run_label', 'Run')})",
                 f"- Took: {time.time() - self.run_started:.1f} s",
                 f"- Model calls: {self.calls}"]
        for who, u in self.usage.items():
            lines.append(f"- {who}: {u[0]:,} tokens in, {u[1]:,} out")
        if self.cost_text():
            lines.append(f"- Cost: {self.cost_text()[3:]}" + (f" ({rate_note()})" if rate_note() else ""))
        if self.budget:
            lines.append(f"- Budget: {self.budget:,} tokens")
        if self.budget_dollars:
            lines.append(f"- Budget: {self.budget_text()} at list prices")
        for line in self.allowance_lines(self.tiers_used):
            lines.append(f"- Allowance: {line}")
        for line in reported_lines():
            lines.append(f"- Limits: {line}")
        if self.error:
            lines.append(f"- Stopped with an error: {self._describe(self.error)}")
        lines.append("")
        for i, (t, label, text, status, meta, prompts) in enumerate(self.trace, 1):
            lines.append(f"## {i}. {label}" + (f" [{status}]" if status else "") + f"  ·  +{t - self.run_started:.1f} s")
            if text:
                lines += ["", "~~~~", text, "~~~~"]
            if meta:
                lines += ["", f"*{meta}*"]
            for k, pr in enumerate(prompts, 1):
                lines += ["", f"<details><summary>Prompt sent{f' ({k} of {len(prompts)})' if len(prompts) > 1 else ''}</summary>", "",
                          "~~~~", pr, "~~~~", "", "</details>"]
            lines.append("")
        result = "\n\n".join(to_str(x) for x in self.result) if self.result else self.draft
        if result:
            lines += ["## Result", "", result, ""]
        try:
            folder = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), LOG_DIR)
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, f"{prog}-{start:%Y%m%d-%H%M%S}.md")
            with _private_open(path) as f:  # the run's prompts and answers (#307)
                f.write("\n".join(lines))
            print(tr("Log saved to {path}", path=path), flush=True)
        except OSError as e:
            print(tr("(The log couldn't be saved: {e})", e=e), flush=True)

    # ----- Schedules -----
    # ----- Serving the program as an MCP tool -----
    # python my-program.py --mcp serves the program to Claude Desktop, Claude Code or any agent that speaks MCP (over
    # stdio): one tool, named after the program, whose input becomes 'message value' and whose result is the program's
    # result. Each call runs the 'when Run is clicked' scripts. Nobody is at a keyboard, so a question fails the call, and
    # an action that would ask first is refused. A program that can act on the world serves only once it's allowed to
    # without asking (approve = no, or approved once in a terminal), as with a schedule.
    MCP_PROTOCOLS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")

    @staticmethod
    def mcp_tool_name():
        base = os.path.splitext(os.path.basename(sys.argv[0] or "program"))[0] or "program"
        return (re.sub(r"[^A-Za-z0-9_-]+", "_", base).strip("_") or "program")[:64]

    def mcp_tool(self, can):
        lines, _ = self.can_lines(can)
        what = (" It can " + "; ".join(lines) + ".") if lines else " It only uses its models."
        return {"name": self.mcp_tool_name(),
                "description": f"Runs the Second Thought program “{self.mcp_tool_name()}” and gives back its result.{what}",
                "inputSchema": self.mcp_input_schema()}

    def mcp_input_schema(self):
        """The tool's inputs: 'value', the message value, and each of the program's named inputs by its kind (#442);
        an input with no default is required."""
        props = {"value": {"type": "string", "description": "What the program starts with: its 'message value'. Leave it out if it needs nothing."}}
        required = []
        kinds = {"number": {"type": "number"}, "yesno": {"type": "boolean"}, "date": {"type": "string", "format": "date"}}
        for name, kind, default in getattr(self, "declared_inputs", []):
            prop = dict(kinds.get(kind, {"type": "string"}))
            value, why = self.input_value(name, kind, default) if to_str(default).strip() else (None, "none")
            if why:
                required.append(name)
            else:
                prop["default"] = value
            props[name] = prop
        schema = {"type": "object", "properties": props}
        if required:
            schema["required"] = required
        return schema

    async def serve_mcp(self, start_scripts, can):
        out, sys.stdout = sys.stdout, sys.stderr  # the run log goes to stderr; stdout carries only the protocol
        self.mcp_mode = True
        self._can = can
        refusal = None
        if not start_scripts:
            refusal = tr("Nothing to run: this program has no 'when Run is clicked' script.")
        elif not self.approve_program(can, unattended=True):
            refusal = tr("This program can act on the world and hasn't been allowed to without asking. Run it once in a terminal and answer y, or put approve = no in second-thought.ini.")
        tool = self.mcp_tool(can)

        def send(msg):
            out.write(json.dumps(msg, ensure_ascii=False) + "\n")
            out.flush()

        while True:
            line = await asyncio.to_thread(sys.stdin.readline)
            if not line:
                return 0
            try:
                msg = json.loads(line)
            except ValueError:
                send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})
                continue
            if not isinstance(msg, dict) or "id" not in msg:
                continue  # notifications, such as notifications/initialized, need no answer
            mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
            if method == "initialize":
                asked = params.get("protocolVersion")
                send({"jsonrpc": "2.0", "id": mid, "result": {
                    "protocolVersion": asked if asked in self.MCP_PROTOCOLS else self.MCP_PROTOCOLS[0],
                    "capabilities": {"tools": {}}, "serverInfo": {"name": tool["name"], "version": RUNTIME_VERSION}}})
            elif method == "ping":
                send({"jsonrpc": "2.0", "id": mid, "result": {}})
            elif method == "tools/list":
                send({"jsonrpc": "2.0", "id": mid, "result": {"tools": [tool]}})
            elif method == "tools/call":
                if params.get("name") != tool["name"]:
                    send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"Unknown tool: {params.get('name')}"}})
                    continue
                if refusal:
                    send({"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": refusal}], "isError": True}})
                    continue
                args = params.get("arguments") or {}
                value = to_str(args.get("value", ""))
                named = {k: (("yes" if v else "no") if isinstance(v, bool) else v) for k, v in args.items() if k != "value"}
                why = self.give_inputs(getattr(self, "declared_inputs", []), named)
                if why:
                    send({"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": why}], "isError": True}})
                    continue
                code = await self.run([(fn, value) for fn in start_scripts], tr("MCP call"))
                if code == 0:
                    text = "\n\n".join(to_str(x) for x in self.result) if self.result else to_str(self.draft)
                else:
                    text = str(self.error) if isinstance(self.error, RunError) else f"{type(self.error).__name__}: {self.error}"
                send({"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": text or tr("\nThe program ended without a result.").strip()}],
                                                               "isError": code != 0}})
            else:
                send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Method not found: {method}"}})
    # ----- Tests: python my-program.py --test -----
    # A test case is a run you were happy with, kept on the page with 'Save as test case': what it started with, your
    # answers to its questions, the files you chose, and what its result must do. --test replays each one from
    # <program>.tests.json, next to the program, with the models live, and a strict reviewer checks each result against
    # its criteria. Nothing acts in a test: messages aren't sent, devices aren't switched, files aren't saved, and memory
    # is a copy, so tests can be run as often as you like, for example after changing a model.
    def _from_test(self, kind, what):
        """The next answer of this kind from the test case, in order."""
        q = self.test_inputs.get(kind) or []
        if not q:
            raise RunError(tr("The test case has no answer for this step ({what}). Save it again from a run that gets this far.", what=_short(to_str(what), 80)))
        v = q.pop(0)
        self.log(tr("Test answer"), _short(to_str(v.get("name", "") if isinstance(v, dict) else v), 200), tr("replayed"))
        return v

    @staticmethod
    def tests_path():
        prog = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else ""
        return os.path.splitext(prog)[0] + ".tests.json"

    async def run_tests(self, start_scripts, times=1):
        import shutil
        import tempfile
        path = self.tests_path()
        try:
            with open(path, encoding="utf-8") as f:
                cases = json.load(f)
        except FileNotFoundError:
            print(tr("No tests: {path} isn't there. Make them on the page: after a good run, press Save as test case, then export again.", path=path), flush=True)
            return 1
        except ValueError as e:
            print(tr("{path} isn't valid JSON ({problem}).", path=path, problem=e), flush=True)
            return 1
        cases = [c for c in (cases if isinstance(cases, list) else []) if isinstance(c, dict)]
        if not start_scripts:
            print(tr("Nothing to run: this program has no 'when Run is clicked' script."), flush=True)
            return 1
        if not cases:
            print(tr("No tests: {path} isn't there. Make them on the page: after a good run, press Save as test case, then export again.", path=path), flush=True)
            return 1
        times = max(1, min(10, int(times or 1)))
        self.testing = True
        results = []       # (name, passed, problems, must-fail rule or "")
        rule_runs = {}     # (case name, rule) -> [met on each run], for --times' flaky rules (#427)
        real_memory = MEMORY_FILE
        with tempfile.TemporaryDirectory() as tmp:
            memory = os.path.join(tmp, "memory.json")
            try:
                for i, case in enumerate(cases, 1):
                    name = to_str(case.get("name")).strip() or tr("Test {n}", n=i)
                    must_fail = to_str(case.get("must_fail", "")).strip()  # a saved bad result, and the rule it must break (#427)
                    criteria = to_str(case.get("criteria")).strip() or must_fail
                    runs_passed, problems = 0, []
                    for _ in range(times):
                        if os.path.isfile(real_memory):
                            shutil.copy(real_memory, memory)  # each run starts from your real notes, and can't change them
                        elif os.path.isfile(memory):
                            os.remove(memory)
                        globals()["MEMORY_FILE"] = memory
                        self.test_inputs = {k: list(v) for k, v in (case.get("inputs") or {}).items() if isinstance(v, list)}
                        code = await self.run([(fn, to_str(case.get("value", ""))) for fn in start_scripts], tr("Test: {name}", name=name))
                        if code != 0:
                            passed, problems = False, [str(self.error) if isinstance(self.error, RunError) else tr("The run stopped.")]
                        elif not criteria:
                            passed, problems = True, []
                        else:
                            text = "\n\n".join(to_str(x) for x in self.result) if self.result else to_str(self.draft)
                            self.ending = False  # the run has ended; the check is one more call
                            self.task, self.draft = "The result of one run of this program.", text or tr("(no result)")
                            approved = await self.review(criteria, tr("Test check"))
                            unmet = [v for v in self.verdicts if not v["met"]]
                            for v in self.verdicts:  # for --times: was each rule met on this run? (#427)
                                rule_runs.setdefault((name, v["rule"]), []).append(bool(v["met"]))
                            if must_fail:
                                # passes only if the review fails the saved result on that rule (#427)
                                passed = (not approved) and any(v["rule"] == must_fail for v in unmet)
                                if approved:
                                    problems = [tr("The rule was met: a must-fail case must break it, so rewrite the rule or save a worse draft.")]
                                elif not passed:
                                    problems = [tr("The review failed, but not on the rule it must break ({rule}).", rule=must_fail)] + \
                                               [f"{v['rule']}: {v['problem'] or tr('not met')}" for v in unmet]
                                else:
                                    problems = []
                            else:
                                passed = approved
                                # name the rule that failed (#424)
                                problems = [f"{v['rule']}: {v['problem'] or tr('not met')}" for v in unmet] or list(self.problems)
                        runs_passed += bool(passed)
                    passed = runs_passed == times
                    if times > 1 and not passed and runs_passed:
                        problems = problems + [tr("{p} of {n} runs passed.", p=runs_passed, n=times)]
                    results.append((name, passed, problems, must_fail))
            finally:
                globals()["MEMORY_FILE"] = real_memory
        flaky = []  # rules that passed on some runs and failed on others: the ones to rewrite (#427)
        if times > 1:
            for (name, rule), mets in rule_runs.items():
                if len(mets) > 1 and any(mets) and not all(mets):
                    flaky.append((name, rule, sum(mets), len(mets)))
        print("\n" + "=" * 60 + "\n" + tr("TESTS") + "\n" + "=" * 60, flush=True)
        for name, passed, problems, must_fail in results:
            mark = "PASS" if passed else "FAIL"  # stays in English, like --doctor's ok and FAIL, for scripts that read it
            print(f"{mark:<6}{name}" + (f"  [{tr('must fail')}]" if must_fail else ""), flush=True)
            for p_ in problems:
                print("      - " + p_, flush=True)
        if flaky:
            print("\n" + tr("Flaky rules: these pass on some runs and fail on others \u2014 the ones to rewrite."), flush=True)
            for name, rule, met, n in flaky:
                print(f"      {name} \u00b7 {rule} \u2014 " + tr("{met} of {n} runs met the rule.", met=met, n=n), flush=True)
        failed = sum(not p for _, p, _, _ in results)
        print("\n" + tr("{passed} of {n} passed.", passed=len(results) - failed, n=len(results)), flush=True)
        if on_github_actions():
            self.report_tests_on_actions(results, flaky)
        return 1 if failed else 0

    def report_tests_on_actions(self, results, flaky=()):
        """On GitHub Actions (#246): each failed case as an error on the run's page, and a table of every case in the
        job's summary, with what the tests cost. Must-fail cases and flaky rules from --times are marked too (#427)."""
        esc = lambda s: to_str(s).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")  # noqa: E731
        for name, passed, problems, _mf in results:
            if not passed:
                title = esc(tr("Test failed: {name}", name=name)).replace(",", "%2C").replace(":", "%3A")
                marker = ACTIONS_ERROR_TITLED.replace("{title}", title)
                print(marker + esc("\n".join(problems) or tr("The run stopped.")), flush=True)
        path = os.environ.get("GITHUB_STEP_SUMMARY", "")
        if not path:
            return
        cell = lambda s: to_str(s).replace("|", "\\|").replace("\n", " ")  # noqa: E731
        failed = sum(not p for _, p, _, _ in results)
        lines = ["## " + tr("Test cases: {passed} of {n} passed", passed=len(results) - failed, n=len(results)), "",
                 "| | " + tr("Test") + " | " + tr("What was wrong") + " |", "|---|---|---|"]
        rows = []
        for name, passed, problems, mf in results:
            tag = f" ({tr('must fail')})" if mf else ""
            rows.append(f"| {'✅' if passed else '❌'} | {cell(name + tag)} | {cell('; '.join(problems))} |")
        lines += rows
        if flaky:
            lines += ["", "### " + tr("Flaky rules"), ""]
            lines += [f"- {cell(name)} · {cell(rule)} — " + tr("{met} of {n} runs met the rule.", met=met, n=n)
                      for name, rule, met, n in flaky]
        cost = self.cost_text()
        if cost:
            lines += ["", tr("These {n} tests cost {cost}.", n=len(results), cost=cost[len(" · "):])]
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        except OSError:
            pass

    @staticmethod
    def schedule_due(s, now, late=datetime.timedelta(hours=1)):
        """Whether a 'when it's' schedule should run now: on one of its days, and no more than an hour late."""
        _, h, m, days, _fn = s
        for target in (now.replace(hour=h, minute=m, second=0, microsecond=0) - datetime.timedelta(days=d) for d in (0, 1)):
            wd = target.weekday()
            if (days == "every" or (days == "weekdays" and wd < 5) or (days == "weekends" and wd >= 5)) and target <= now < target + late:
                return True
        return False

    def run_one_schedule(self, schedules, can):
        """--run-schedule N runs scheduled script N (counting from 1) once, if it's due now, for a scheduler outside the
        program such as GitHub Actions. That may start it late, or at both the summer and winter times, so a 'when it's'
        script only runs within an hour after its time. With --now it runs whatever the time."""
        args = sys.argv[sys.argv.index("--run-schedule") + 1:]
        n = int(args[0]) if args and args[0].isdigit() else 0
        if not 1 <= n <= len(schedules):
            return tr("There's no scheduled script {n}: this program has {count}.", n=args[0] if args else "", count=len(schedules))
        s = schedules[n - 1]
        if s[0] == "time" and "--now" not in sys.argv and not self.schedule_due(s, datetime.datetime.now()):
            print(tr("Not time for scheduled script {n} ({time}, {days}), so nothing was run.", n=n, time=f"{s[1]:02d}:{s[2]:02d}",
                     days={"weekdays": tr("weekdays"), "weekends": tr("weekends")}.get(s[3]) or tr("every day")), flush=True)
            return 0
        if not self.approve_program(can, unattended=not sys.stdin.isatty()):
            return 1
        label = s[-2] if s[0] == "every" else tr("Scheduled {time}", time=f"{s[1]:02d}:{s[2]:02d}")
        code = asyncio.run(self.run([s[-1]], label))
        asyncio.run(self._scheduled_end(label, code))  # the failure notice and the heartbeat, if they're set (#433)
        return code

    async def run_schedules(self, schedules, watches=(), telegram=(), listeners=()):
        if not schedules and not watches and not telegram and not listeners:
            sys.exit(tr("This program has no scheduled scripts, and nothing that listens."))
        self.schedule_mode = True
        print(tr("Schedules are on. Leave this running; press Ctrl+C to stop."), flush=True)
        if watches:
            self._background(self._watch(watches))
        if telegram:
            if not self._tg_chats():
                print(tr("Telegram: send your bot a message. Until TELEGRAM_CHAT_ID is set {where_keys}, the program only says which chat it came from.", where_keys=WHERE_KEYS), flush=True)
            self._background(self._tg_watch(telegram))
        if listeners:
            await self._listen(listeners)
        fired, next_every = {}, {}
        start = time.time()
        for i, s in enumerate(schedules):
            if s[0] == "every":
                next_every[i] = start + s[1]
        busy = None
        while True:
            now = time.time()
            dt = datetime.datetime.now()
            for i, s in enumerate(schedules):
                due = False
                if s[0] == "every":
                    if now >= next_every[i]:
                        due = True
                        while next_every[i] <= now:
                            next_every[i] += s[1]
                else:
                    _, h, m, days, fn = s
                    wd = dt.weekday()
                    ok = days == "every" or (days == "weekdays" and wd < 5) or (days == "weekends" and wd >= 5)
                    target = dt.replace(hour=h, minute=m, second=0, microsecond=0)
                    key = dt.strftime("%Y-%m-%d")
                    if ok and target <= dt < target + datetime.timedelta(minutes=10) and fired.get(i) != key:
                        fired[i] = key
                        due = True
                if due:
                    fn = s[-1]
                    label = s[-2] if s[0] == "every" else tr("Scheduled {time}", time=f"{s[1]:02d}:{s[2]:02d}")
                    if busy and not busy.done():
                        self.start_script(fn)
                    else:
                        busy = asyncio.ensure_future(self.run([fn], label))
                        busy.add_done_callback(lambda t, label=label: self._background(self._scheduled_end(label, t)))  # #433
            await asyncio.sleep(5)

    async def _scheduled_end(self, label, result):
        """After a scheduled run finishes (#433): one notify_on_failure message if it stopped with an error, and a
        heartbeat_url fetch either way, so a schedule that goes quiet gets noticed too. Neither is ever an error, and
        in a test or a rehearsal neither happens."""
        if self.dry_run():
            return
        if isinstance(result, asyncio.Task):
            try:
                code = result.result()
            except BaseException:  # noqa: BLE001 - a run that was stopped or crashed counts as stopped
                code = 1
        else:
            code = result
        if code and self.error:
            await self._notify_failure(label, self._describe(self.error))
        await self._heartbeat()

    async def _notify_failure(self, label, reason):
        """One message on the notify_on_failure channel when a scheduled run stops with an error (#433). The run is
        unattended, so the message goes without asking first; a channel that can't be reached is only a note."""
        channel = os.environ.get("RB_NOTIFY_ON_FAILURE", "").strip().lower()
        if not channel:
            return
        prog = os.path.basename(sys.argv[0] or "program")
        text = tr("{program}: scheduled run \u201c{label}\u201d stopped with an error: {reason}",
                  program=prog, label=label, reason=_short(reason, 300))
        if channel == "telegram":
            try:
                if await self.tg_send(text, approved=True):
                    print(tr("  (Sent a failure notice on {channel}.)", channel=channel), flush=True)
            except Exception as e:  # noqa: BLE001 - a notice that can't go out is a note, never an error
                print(tr("  (Couldn't send the failure notice on {channel}: {e})", channel=channel, e=_short(e, 160)), flush=True)
        else:
            print(tr("  (notify_on_failure = {channel} isn't a channel this runtime can send on yet; the error was: {reason})",
                     channel=channel, reason=_short(reason, 160)), flush=True)

    async def _heartbeat(self):
        """Fetches heartbeat_url after a scheduled run finishes (#433), for Healthchecks.io or an Uptime Kuma push
        monitor. Its failure is a note, never an error: the next run tries again."""
        url = os.environ.get("RB_HEARTBEAT_URL", "").strip()
        if not url:
            return
        try:
            await asyncio.to_thread(get_url, url, True, tr("Heartbeat"), 4096)
            print(tr("  (Heartbeat sent: {url})", url=_short(url, 80)), flush=True)
        except Exception as e:  # noqa: BLE001 - a heartbeat that can't be sent is only a note
            print(tr("  (The heartbeat {url} couldn't be fetched, which is only a note: {e})", url=_short(url, 80), e=_short(e, 160)), flush=True)

    async def _watch(self, watches):
        """Polls Home Assistant and starts 'when … changes' scripts."""
        last = {}
        first = True
        busy = None
        while True:
            try:
                states = {e["entity_id"]: e for e in await self._ha("GET", "/api/states")}
            except RunError as e:
                print(tr("  (Home Assistant check failed: {e})", e=str(e)), flush=True)
                await asyncio.sleep(HA_WATCH_SECONDS)
                continue
            for entity, want, fn in watches:
                e = states.get(entity)
                if not e:
                    continue
                now_state = e["state"]
                before = last.get(entity)
                last[entity] = now_state
                if first or before is None or before == now_state:
                    continue
                if want.lower() not in ("", "anything") and want.lower() != now_state.lower():
                    continue
                payload = {"entity": entity, "name": e.get("attributes", {}).get("friendly_name", entity),
                           "from": self._ha_val(before), "to": self._ha_val(now_state)}
                if busy and not busy.done():
                    self.start_script(fn, payload)
                else:
                    busy = asyncio.ensure_future(self.run([(fn, payload)], tr("When {entity} changes", entity=entity)))
            first = False
            await asyncio.sleep(HA_WATCH_SECONDS)

    # ----- What the program can do: listed, and asked once before its first run -----
    @staticmethod
    def can_lines(can):
        """What a program can do, as lines to show: one per thing it can do, then the model services it uses."""
        known = {c[0]: c for c in CAPABILITIES}
        ids = list((can or {}).get("can", []))
        order = {c[0]: i for i, c in enumerate(CAPABILITIES)}
        lines = [known[c][1] if c in known else f"do “{c}”, which this runtime doesn't know about"
                 for c in sorted(ids, key=lambda c: order.get(c, -1))]
        services = list((can or {}).get("services", []))
        tail = [f"It sends what it reads and writes to {services[0] if len(services) == 1 else ', '.join(services[:-1]) + ' and ' + services[-1]}."] if services else []
        return lines, tail

    @staticmethod
    def can_acts(can):
        """Whether the program can act on the world (an unknown capability counts as acting)."""
        known = {c[0]: c[2] for c in CAPABILITIES}
        return any(known.get(c, True) for c in (can or {}).get("can", []))

    @staticmethod
    def _approval_path():
        """(.<program>.approved next to the program, the program file's SHA-256), or (None, None) without a file."""
        prog = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else ""
        if not prog or not os.path.isfile(prog):
            return None, None
        with open(prog, "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        base = os.path.splitext(os.path.basename(prog))[0]
        return os.path.join(os.path.dirname(prog), f".{base}.approved"), digest

    def changes_since(self, before, can):
        """When the program was allowed before and has changed since: lines saying so, and what it can do now that it
        couldn't then, and the other way round, so the full list that follows needn't be read for what's new."""
        if not isinstance(before, dict) or not isinstance(before.get("allowed"), list):
            return []
        was, now = [str(c) for c in before["allowed"]], list((can or {}).get("can", []))
        when = str(before.get("when", ""))[:16].replace("T", " ")
        out = [tr("\nThis program has changed since you allowed it on {when}.", when=when) if when else
               tr("\nThis program has changed since you allowed it.")]
        new = self.can_lines({"can": [c for c in now if c not in was]})[0]
        gone = self.can_lines({"can": [c for c in was if c not in now]})[0]
        if new:
            out.append(tr("New since then: {what}", what="; ".join(new)))
        if gone:
            out.append(tr("No longer: {what}", what="; ".join(gone)))
        if not new and not gone:
            out.append(tr("What it can do is the same as before."))
        return out

    def approve_program(self, can, unattended=False):
        """True if the program may run. One that can act on the world lists what it can do and asks once; the yes is
        kept in .<program>.approved until the program file changes. approve = no in second-thought.ini skips this."""
        if getattr(self, "rehearsing", False):  # a rehearsal acts on nothing, so there's nothing to allow, and nothing is saved (#430)
            return True
        if not self.can_acts(can) or os.environ.get("RB_APPROVE", "").strip().lower() in ("no", "0", "false", "off"):
            return True
        path, digest = self._approval_path()
        before = None
        if path:
            try:
                with open(path, encoding="utf-8") as f:
                    before = json.load(f)
                if before.get("sha256") == digest:
                    self._first_run_ok = True  # for the receipts' "approved at the first run" (#431)
                    return True
            except (OSError, ValueError, AttributeError):
                before = None
        for line in self.changes_since(before, can):
            print(line, flush=True)
        lines, tail = self.can_lines(can)
        print(tr("\nThis program can:"), flush=True)
        for line in lines:
            print("  - " + line)
        for line in tail:
            print(line)
        nobody = (f"\nIt hasn't been allowed to do these on this computer yet, and nobody is here to ask. Run it once yourself, "
                  f"not on a schedule, and answer y. Or put approve = no {WHERE_KEYS}.")
        if unattended:
            print(nobody, flush=True)
            return False
        print(tr("\n? Allow it to do these things on this computer? It won't ask again unless the program changes."), flush=True)
        while True:
            try:
                a = input(tr("Approve? [y/n] > ")).strip().lower()
            except EOFError:  # no keyboard after all (on Windows, a scheduled task's input can look like one)
                print(nobody, flush=True)
                return False
            if said_yes(a):
                self._first_run_ok = True  # for the receipts' "approved at the first run" (#431)
                break
            if said_no(a):
                print(tr("Not allowed, so it didn't run."))
                return False
            print(tr("  Type y or n."))
        if path:
            try:
                _write_json(path, {"sha256": digest, "allowed": list(can.get("can", [])), "runtime": RUNTIME_VERSION,
                                   "when": datetime.datetime.now().isoformat(timespec="seconds")}, indent=1)
            except OSError as e:
                print(tr("  (Couldn't note that you said yes, so it will ask again next time: {e})", e=e))
        return True

    async def setup_check(self):
        """The 'this program's setup check' block: the same checks as --doctor, as text. They run on a fresh runtime, so
        this run's draft, memory and counts are untouched, and only read: nothing is sent, switched or charged."""
        import contextlib
        import io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            await type(self)().doctor(getattr(self, "_can", None))
        return out.getvalue().strip()

    def main(self, start_scripts, receivers, schedules, watches=(), telegram=(), listeners=(), can=None, inputs=()):
        if "--version" in sys.argv:
            print(tr("Second Thought runtime {runtime_version}", runtime_version=RUNTIME_VERSION))
            return
        self._can = can
        self.rehearsing = "--rehearse" in sys.argv or os.environ.get("RB_REHEARSE", "").strip().lower() in ("1", "yes", "true", "on")
        if self.rehearsing:
            import shutil
            import tempfile
            # a rehearsal reads your real notes but can't change them: memory is a copy, as in tests (#430)
            self._rehearsal_tmp = tempfile.TemporaryDirectory()
            mem = os.path.join(self._rehearsal_tmp.name, "memory.json")
            if os.path.isfile(MEMORY_FILE):
                shutil.copy(MEMORY_FILE, mem)
            globals()["MEMORY_FILE"] = mem
        any_allowance()  # so does a mistyped quota_daily (or another allowance)
        check_plans()  # and a PLAN_ setting naming a plan its service doesn't have
        fixed_rate()  # a mistyped exchange_rate stops the program now, saying so, not part-way through a run. Not when the
        # runtime loads: in python/runtime.py, providers comes before core, whose _number_setting it uses (#274)
        if "--doctor" in sys.argv:
            sys.exit(asyncio.run(self.doctor(can)))
        if "--update-runtime" in sys.argv:
            sys.exit(self.update_runtime(can))
        if "--receipts" in sys.argv:
            sys.exit(self.show_receipts())
        if "--report" in sys.argv:
            sys.exit(self.show_report())
        if "--status" in sys.argv:
            sys.exit(self.show_status())
        self.receivers = {k.lower(): v for k, v in receivers.items()}
        self.declared_inputs = [tuple(d) for d in inputs]
        if "--mcp" in sys.argv:
            sys.exit(asyncio.run(self.serve_mcp(start_scripts, can)))
        given, why = self.cli_inputs()
        why = why or self.give_inputs(self.declared_inputs, given)
        if why:
            sys.exit(why + ("" if "--input" in why else " (--input name=value)"))
        if "--test" in sys.argv:
            times = 1  # --test --times 3 runs each case three times and lists the rules that flip (#427)
            if "--times" in sys.argv:
                j = sys.argv.index("--times")
                nxt = sys.argv[j + 1] if j + 1 < len(sys.argv) else ""
                if not nxt.isdigit() or int(nxt) < 1:
                    sys.exit(tr("--times needs a number of runs, like --test --times 3."))
                times = min(int(nxt), 10)
            sys.exit(asyncio.run(self.run_tests(start_scripts, times)))
        if "--run-schedule" in sys.argv:
            sys.exit(self.run_one_schedule(schedules, can))
        use_schedule = "--schedule" in sys.argv or ((schedules or watches or telegram or listeners) and not start_scripts)
        if self.rehearsing:
            print(tr("Rehearsal: the program runs for real, but nothing is sent, switched, saved or spent."), flush=True)
        if not self.approve_program(can, unattended=bool(use_schedule) and not sys.stdin.isatty()):
            sys.exit(1)
        try:
            if use_schedule:
                asyncio.run(self.run_schedules(schedules, watches, telegram, listeners))
            else:
                if not start_scripts:
                    sys.exit(tr("Nothing to run: this program has no 'when Run is clicked' script."))
                sys.exit(asyncio.run(self.run(start_scripts)))
        except KeyboardInterrupt:
            print(tr("\nStopped."))
