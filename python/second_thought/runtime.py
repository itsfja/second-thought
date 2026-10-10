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
import os
import random
import re
import sys
import time
from .settings import RUNTIME_VERSION, WHERE_KEYS
from .providers import ModelCalls, model_label
from .core import (BUDGET, CAPABILITIES, Finish, HA_WATCH_SECONDS, LOG_DIR, MAX_DEPTH, MAX_SCRIPTS, MAX_SECONDS, MAX_STEPS,
    MEMORY_FILE, MESSAGE_VALUE, MODEL_OVERRIDE, OUTPUT_DIR, Picture, Retryable, RunError, SCHEMAS, _EXT, _MEDIA,
    _locked, _need_picture, _short, _write_json, clean_svg, field_list, num, read_text_file, record_schema, round_js,
    to_bool, to_list, to_record, to_str)
from .connectors import Connections
from .mcp import MCPTools
from .agent import AgentTools
# ---- package only: tools/sync.py leaves everything above this line out of python/runtime.py ----


class Runtime(ModelCalls, Connections, MCPTools, AgentTools):
    def __init__(self):
        self.vars = {}
        self.receivers = {}
        self.client = None
        self.gemini = None
        self.no_schema = set()      # Claude models that refused a reply shape, so it isn't sent again
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
        self.budget = BUDGET          # budget = 50000 in second-thought.ini caps every run; a 'limit this run' block changes it
        self.ask_first = set()       # set by 'ask me before' blocks: "ha", "messages", "files"
        self.trace = []              # every log line, for save_log
        self._pending = []           # model calls since the last log line: who answered, how long, tokens, the prompt
        self.agent_trace = []        # the most recent agent's steps, for the "agent's steps" block
        self.run_started = time.time()
        self.max_seconds = MAX_SECONDS  # max_seconds = 600 stops any run that takes longer
        self.programs = []           # names of saved programs running inside this run, innermost last
        self.calls = 0
        self.steps = 0
        self.depth = 0
        self.started = 0
        self.timer_start = time.monotonic()
        self.journal, self.replay, self.replay_pos = getattr(self, "journal", None), None, 0
        self.tier = os.environ.get("RB_MODEL_TIER", globals().get("DEFAULT_TIER", "default"))
        self.primary = self.tier
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
            raise RunError("A My Blocks block called itself too many times.")
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
        raise RunError("The block '" + kind + "' can't run outside the block editor.")

    def tick(self):
        self.steps += 1
        if self.steps > MAX_STEPS:
            raise RunError(f"Stopped after {MAX_STEPS} steps. A loop may never end; check repeat and while blocks.")

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
            self._pending.append({"who": model_label(t), "secs": time.monotonic() - start, "in": after[0] - before[0],
                                  "out": after[1] - before[1], "ok": ok, "prompt": self._prompt_text(prompt, history, picture)})

    # ----- Claude -----
    @property
    def current_tier(self):
        return MODEL_OVERRIDE.get() or self.tier

    def _count(self, provider, tokens_in, tokens_out):
        u = self.usage.setdefault(provider, [0, 0])
        u[0] += tokens_in or 0
        u[1] += tokens_out or 0

    def tokens_used(self):
        return sum(u[0] + u[1] for u in self.usage.values())

    def set_budget(self, n):
        n = max(0, round_js(num(n)))
        self.budget = n
        self.log("Budget", f"This run stops before a model call once it has used {n:,} tokens (used so far: {self.tokens_used():,})."
                 if n else "No token budget for this run.", "set")

    # ----- Asking before actions -----
    ASK_FIRST = {"ha": "any smart home action (Home Assistant, Homey or MQTT)", "messages": "sending messages and announcements",
                 "files": "saving files", "all": "all of these"}

    def ask_before(self, kind):
        kinds = {"ha", "messages", "files"} if kind == "all" else {kind}
        self.ask_first |= kinds
        self.log("Ask first", "From now on, the program asks you before " + self.ASK_FIRST.get(kind, kind) + ".", "set")

    async def _allowed(self, kinds, what):
        """True if the action may go ahead. Asks first when an 'ask me before' block covers it."""
        if not (self.ask_first & set(kinds)):
            return True
        return await self.confirm(what)

    async def confirm(self, what):
        """Shows what the program is about to do and waits for a yes. Unattended scheduled runs say no."""
        if self.schedule_mode and not sys.stdin.isatty():
            self.log("Not done", what + " needs your approval, and nobody is at the keyboard.", "refused")
            return False
        if await self.approve("Allow this? " + what):
            return True
        self.log("Not done", what + " was refused, so nothing happened.", "refused")
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
                    print("\n(A previous run stopped part-way, but the program has changed since, so it starts afresh.)", flush=True)
            except (OSError, ValueError):
                old = []
        if old:
            choice = os.environ.get("RB_RESUME", "").strip().lower()
            if choice in ("1", "yes", "true", "on"):
                use = True
            elif choice in ("0", "no", "false", "off"):
                use = False
            elif sys.stdin.isatty():
                print(f"\n? The last run stopped part-way, after {len(old)} saved step{'s' if len(old) != 1 else ''}.", flush=True)
                use = (await self._input("Pick up where it stopped, reusing those? [y/n] > ")).strip().lower() in ("y", "yes")
            else:
                use = False
                print("\n(The last run stopped part-way. Set resume = yes in second-thought.ini to pick up where it stopped.)", flush=True)
            if use:
                self.replay = old
                self.log("Resuming", f"Picking up the run that stopped: {len(old)} saved step{'s' if len(old) != 1 else ''} will be "
                         "reused instead of repeated.", "resume")
        try:
            self.journal = open(path, "w", encoding="utf-8")
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
            else:
                print("Run the program again to pick up where it stopped.", flush=True)

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
                    self.log("Caught up", "That was the last saved step. From here the run carries on as usual.", "resume", calls=False)
                return True, e.get("value")
            self.log("Run differs here", "From this step the run isn't the same as the one that stopped, so the rest runs afresh.",
                     "resume", calls=False)
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

    async def ask_me(self, q):
        out = await self._journaled("ask_me", self._key(to_str(q)), lambda: self._ask_me_live(q))
        self.answer = out
        return out

    async def approve(self, text):
        return await self._journaled("approve", self._key(to_str(text)), lambda: self._approve_live(text))

    async def choose(self, items):
        return await self._journaled("choose", self._key(to_list(items)), lambda: self._choose_live(items))

    async def choose_file(self):
        return await self._journaled("choose_file", self._key("file"), self._choose_file_live)

    async def ha_call(self, service, entity, data_text=""):
        key = self._key(to_str(service), to_str(entity), to_str(data_text))
        hit, v = self._replayed("ha_call", key)
        if hit:
            self.log("Home Assistant: " + to_str(service).strip(), f"{to_str(entity)}: already done before the stop, so not done again.", "reused")
            return v
        out = await self._ha_call_live(service, entity, data_text)
        self._record("ha_call", key, out)
        return out

    async def ha_notify(self, target, text):
        key = self._key(to_str(target), to_str(text))
        hit, _ = self._replayed("ha_notify", key)
        if hit:
            self.log("Notification → " + (to_str(target).strip() or "persistent_notification"), "Already sent before the stop, so not sent again.", "reused")
            return
        await self._ha_notify_live(target, text)
        self._record("ha_notify", key, True)

    async def ha_speak(self, text, player):
        key = self._key(to_str(text), to_str(player))
        hit, _ = self._replayed("ha_speak", key)
        if hit:
            self.log("Spoken on " + (to_str(player).strip() or "a speaker"), "Already said before the stop, so not said again.", "reused")
            return
        await self._ha_speak_live(text, player)
        self._record("ha_speak", key, True)

    async def ask_text(self, p):
        p = to_str(p)
        if not p.strip():
            raise RunError("An 'ask Claude' block is empty.")
        out = await self._call("Answer the request below. Reply with only the answer, no preamble.\n\n" + p)
        self.log("Ask Claude: " + _short(p, 60), out, "done")
        return out

    async def ask_yesno(self, p):
        p = to_str(p)
        if not p.strip():
            raise RunError("A yes/no block is empty.")
        r = await self._call('Answer the question. Reply with only JSON: {"answer": true} or {"answer": false}.\n\nQuestion:\n' + p, SCHEMAS["yesno"])
        yes = r["answer"] is True
        self.log("Yes or no: " + _short(p, 60), "Yes" if yes else "No", "done")
        return yes

    async def ask_number(self, p):
        p = to_str(p)
        if not p.strip():
            raise RunError("An 'ask for a number' block is empty.")
        r = await self._call('Reply with only JSON: {"number": <a single number>}.\n\nRequest:\n' + p, SCHEMAS["number"])
        n = num(r["number"])
        self.log("Number: " + _short(p, 60), n, "done")
        return n

    async def ask_list(self, p):
        p = to_str(p)
        if not p.strip():
            raise RunError("An 'ask for a list' block is empty.")
        r = await self._call('Reply with only JSON: {"items": [<short strings>]}, no other text.\n\nRequest:\n' + p, SCHEMAS["list"])
        items = [to_str(i) for i in r["items"] if to_str(i)]
        self.log("List: " + _short(p, 60), "\n".join("- " + i for i in items) or "(empty list)", f"{len(items)} items")
        return items

    async def rewrite(self, text, how):
        text, how = to_str(text), to_str(how)
        if not text.strip():
            raise RunError("A 'rewrite' block has nothing to rewrite.")
        out = await self._call("Rewrite the text below. Instruction: " + how + "\nReply with only the rewritten text.\n\nText:\n" + text)
        self.log("Rewrite: " + _short(how, 60), out, "done")
        return out

    async def extract(self, what, text):
        what, text = to_str(what), to_str(text)
        if not text.strip():
            raise RunError("An 'extract' block has no text to read.")
        out = await self._call("From the text below, extract: " + what + "\nReply with only what you extracted, nothing else.\n\nText:\n" + text)
        self.log("Extract: " + _short(what, 60), out, "done")
        return out

    async def score(self, text, criteria):
        text, criteria = to_str(text), to_str(criteria)
        r = await self._call("Score the text from 1 to 10 against these criteria: " + criteria +
                             '\nBe strict and consistent. Reply with only JSON: {"score": <1-10>}.\n\nText:\n' + text, SCHEMAS["score"])
        s = max(0, min(10, num(r["score"])))
        self.log("Score: " + _short(text, 50), f"{s}/10", "done")
        return s

    async def better(self, a, b, criteria):
        a, b, criteria = to_str(a), to_str(b), to_str(criteria)
        r = await self._call("Which text is better for: " + criteria +
                             '?\nReply with only JSON: {"pick": 1 or 2, "reason": "<one sentence>"}.\n\nText 1:\n' + a + "\n\nText 2:\n" + b, SCHEMAS["pick"])
        second = num(r["pick"]) == 2
        self.log("Pick the better one", ("Picked the second" if second else "Picked the first") +
                 (". " + to_str(r.get("reason")) if r.get("reason") else ""), "done")
        return b if second else a

    # ----- Conversations, instructions, web search -----
    def set_instructions(self, text):
        self.instructions = to_str(text).strip()
        self.log("Instructions for Claude", self.instructions or "(cleared)", "set")

    async def chat(self, name, message):
        key = to_str(name).strip().lower() or "chat"
        message = to_str(message).strip()
        if not message:
            raise RunError("The 'chat' block has no message.")
        hist = self.chats.setdefault(key, [])
        reply = await self._call(message, history=list(hist))
        hist += [{"role": "user", "content": message}, {"role": "assistant", "content": reply}]
        del hist[:-40]
        self.log(f"Chat {to_str(name).strip()}: " + _short(message, 50), reply, f"turn {len(hist) // 2}")
        return reply

    def chat_reset(self, name):
        self.chats.pop(to_str(name).strip().lower(), None)
        self.log("Conversation " + to_str(name).strip(), "Starting afresh.", "reset")

    async def web_search(self, q):
        q = to_str(q).strip()
        if not q:
            raise RunError("The 'search the web' block is empty.")
        out = await self._call("Search the web and answer briefly, listing the sources you used as plain URLs at the end.\n\nQuery: " + q,
                               web=True)
        self.log("Web search: " + _short(q, 50), out, "done")
        return out

    # ----- Records -----
    async def ask_record(self, fields, prompt, many=False):
        fields, prompt = field_list(fields), to_str(prompt).strip()
        if not fields:
            raise RunError("Give the record's fields, separated by commas.")
        if not prompt:
            raise RunError("The 'ask Claude for a record' block has no request.")
        shape = "{" + ", ".join(json.dumps(f) + ": ..." for f in fields) + "}"
        r = await self._call(('Reply with only JSON: {"items": [<objects, each shaped like ' + shape + '>]}' if many else "Reply with only one JSON object shaped like " + shape) +
                             ". Use these exact field names. Numbers as numbers.\n\nRequest:\n" + prompt, record_schema(fields, many))
        if many:
            recs = [to_record(o, fields) for o in r["items"]]
            self.log("Records: " + _short(prompt, 55), "\n".join(" · ".join(f"{f}: {_short(x[f], 40)}" for f in fields) for x in recs), f"{len(recs)} records")
            return recs
        rec = to_record(r, fields)
        self.log("Record: " + _short(prompt, 55), to_str(rec), "done")
        return rec

    # ----- Prompt library -----
    def prompt(self, name):
        text = PROMPTS.get(to_str(name).strip().lower()) if "PROMPTS" in globals() else None
        if text is None:
            raise RunError(f"There's no prompt called “{name}” in this program's prompt library.")
        return text

    # ----- Files -----
    async def _choose_file_live(self):
        print("\n? Choose a file: type the path to a PDF, a .docx, or a text file (.txt, .md, .csv, .json ...).", flush=True)
        while True:
            path = (await self._input("Path > ")).strip().strip('"').strip("'")
            if not os.path.isfile(path):
                print("  That file doesn't exist. Try again.")
                continue
            if os.path.getsize(path) > 25 * 1024 * 1024:
                print("  That file is over 25 MB. Choose a smaller one.")
                continue
            try:
                text = read_text_file(path)
            except RunError as e:
                print("  " + str(e))
                continue
            if not text.strip():
                print("  No text could be found in that file. A scanned PDF holds pictures of pages, not text.")
                continue
            self.log("Chose file", f"{path} \u00b7 {len(text):,} characters", "chosen")
            return text

    async def save_file(self, value, name, ext):
        if isinstance(value, Picture):
            raise RunError("To save a picture, use the 'save picture' block.")
        if ext == "json" and not isinstance(value, str):
            text = json.dumps(value, default=str, indent=2, ensure_ascii=False)
        elif ext == "csv" and isinstance(value, list):
            text = "\n".join(",".join('"' + to_str(c).replace('"', '""') + '"' for c in r) if isinstance(r, list) else to_str(r) for r in value)
        else:
            text = to_str(value)
        if not text:
            raise RunError("There's nothing to save: the value in the 'save as file' block is empty.")
        base = re.sub(r"[^\w\-]+", "-", to_str(name)).strip("-") or "output"
        path = os.path.join(OUTPUT_DIR, f"{base}.{ext}")
        if not await self._allowed(["files"], f"save {path} ({len(text):,} characters)"):
            return
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        self.log("Save file", "Saved " + path, "saved")

    def result_text(self):
        items = self.result if self.result else ([self.draft] if self.draft else [])
        return "\n\n".join(items)

    # ----- Errors and retries -----
    @staticmethod
    def _describe(e):
        return str(e) if isinstance(e, RunError) else f"{type(e).__name__}: {e}"

    def failed(self, e):
        self.last_error = self._describe(e)
        self.log("Something failed, so the 'if it fails' part ran", self.last_error, "handled")

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
            self.log(f"Gave up after {attempt} tries", self.last_error, "failed")
            raise e
        wait = 2 * attempt
        self.log("Retrying", f"Try {attempt} of {max_tries} failed: {self.last_error}\nTrying again in {wait}s.", f"retry {attempt + 1}")
        await asyncio.sleep(wait)

    # ----- Memory -----
    @staticmethod
    def _mem_key(name):
        key = to_str(name).strip().lower()
        if not key:
            raise RunError("A memory block has no name. Type a name into its name slot.")
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
            raise RunError("Pictures can only be remembered 'while this page is open'. Save the picture as a file to keep it.")
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
        self.log("Remembered \u201c" + to_str(name).strip() + "\u201d", _short(value, 120) + "  \u00b7  " +
                 ("while running" if kind == "transient" else "forever"), "saved")

    def remember_for(self, value, name, n, unit):
        ms = min(365 * 86400000, max(0, num(n)) * {"m": 60000, "h": 3600000, "d": 86400000}.get(unit, 86400000))
        if not ms:
            raise RunError("A 'remember for' block needs a time above zero.")
        expires = int(time.time() * 1000 + ms)
        self._mem_write(name, value, "permanent", expires)
        until = datetime.datetime.fromtimestamp(expires / 1000).strftime("%a %d %b %H:%M")
        self.log("Remembered \u201c" + to_str(name).strip() + "\u201d", _short(value, 120) + "  \u00b7  until " + until, "saved")

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
        self.log("Added to \u201c" + to_str(name).strip() + "\u201d", f"{len(items)} items", "saved")

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
        self.log("Forgot \u201c" + to_str(name).strip() + "\u201d", None, "forgotten")

    def memory_names(self):
        names = {v["name"] for v in self.transient_memory.values()}
        names |= {v["name"] for k, v in self._mem_load().items() if k not in self.transient_memory}
        return sorted(names)

    # ----- Pictures -----
    _DRAW_RULES = ("Reply with only the SVG code, starting with <svg and ending with </svg>. Use a viewBox, flat shapes and solid fills. "
                   "No scripts, no external images or fonts, no animation. Only add text if the description asks for it.")

    def _save_file(self, pic, data=None, ext=None):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        ext = ext or _EXT.get(pic.media_type, ".png")
        base = re.sub(r"[^\w\-]+", "-", pic.name).strip("-") or "picture"
        path = os.path.join(OUTPUT_DIR, base + ext)
        i = 2
        while os.path.exists(path):
            path = os.path.join(OUTPUT_DIR, f"{base}-{i}{ext}")
            i += 1
        with open(path, "wb") as f:
            f.write(data if data is not None else pic.data)
        return path

    def _picture_path(self, pic):
        if not pic.path or not os.path.exists(pic.path):
            pic.path = self._save_file(pic)
        return pic.path

    async def choose_picture(self):
        print("\n? Choose a picture: type the path to a JPEG, PNG, WebP, GIF or SVG file.", flush=True)
        while True:
            path = (await self._input("Path > ")).strip().strip('"').strip("'")
            ext = os.path.splitext(path)[1].lower()
            if not os.path.isfile(path):
                print("  That file doesn't exist. Try again.")
                continue
            if ext not in _MEDIA:
                print("  That isn't a JPEG, PNG, WebP, GIF or SVG file.")
                continue
            with open(path, "rb") as f:
                data = f.read()
            name = os.path.splitext(os.path.basename(path))[0]
            if ext == ".svg":
                svg = clean_svg(data.decode("utf-8", "replace"))
                if not svg:
                    print("  That SVG file couldn't be read.")
                    continue
                pic = Picture(svg.encode("utf-8"), "image/svg+xml", name, svg)
            else:
                pic = Picture(data, _MEDIA[ext], name)
            pic.path = path
            self.log("Chose picture", path, "chosen")
            return pic

    async def _draw(self, prompt, label, picture=None):
        out = await self._call(prompt, picture=picture)
        svg = clean_svg(out)
        if not svg:
            raise Retryable("Claude's drawing came back in a form that can't be used. Run again, or simplify the description.")
        pic = Picture(svg.encode("utf-8"), "image/svg+xml", None, svg)
        self.log(label, "Saved to " + self._picture_path(pic), "drawn")
        return pic

    async def draw_picture(self, desc):
        desc = to_str(desc).strip()
        if not desc:
            raise RunError("The 'draw a picture' block has no description.")
        return await self._draw("Draw this as a single SVG illustration: " + desc + "\n" + self._DRAW_RULES, "Draw: " + _short(desc, 60))

    async def change_picture(self, pic, how):
        pic = _need_picture(pic, "change picture")
        how = to_str(how).strip()
        if not how:
            raise RunError("The 'change picture' block has no change in it.")
        if pic.svg is not None:
            return await self._draw("Here is an SVG illustration:\n" + pic.svg + "\n\nRedraw it with these changes: " + how +
                                    "\nKeep everything else the same. " + self._DRAW_RULES, "Change picture: " + _short(how, 60))
        return await self._draw("Draw a new SVG illustration of the attached picture, with these changes: " + how + "\n" + self._DRAW_RULES,
                                "Redraw as illustration: " + _short(how, 50), picture=pic)

    async def ask_picture(self, q, pic):
        q = to_str(q).strip()
        pic = _need_picture(pic, "ask Claude about picture")
        if not q:
            raise RunError("The 'ask Claude about picture' block has no question.")
        out = await self._call("Look at the attached picture and answer. Reply with only the answer, no preamble.\n\n" + q, picture=pic)
        self.log("Look at picture: " + _short(q, 55), out, "done")
        return out

    async def score_picture(self, pic, criteria):
        pic = _need_picture(pic, "score picture")
        r = await self._call("Score the attached picture from 1 to 10 against these criteria: " + to_str(criteria) +
                             '\nBe strict and consistent. Reply with only JSON: {"score": <1-10>}.', SCHEMAS["score"], picture=pic)
        s = max(0, min(10, num(r["score"])))
        self.log("Score picture: " + _short(criteria, 55), f"{s}/10", "done")
        return s

    def show_picture(self, pic):
        pic = _need_picture(pic, "show picture")
        self.log("Picture", self._picture_path(pic), "shown")

    async def save_picture(self, pic, fmt):
        pic = _need_picture(pic, "save picture")
        if not await self._allowed(["files"], f"save the picture {pic.name}"):
            return
        if fmt == "svg":
            if pic.svg is None:
                raise RunError("Only drawn pictures can be saved as SVG. Choose PNG instead.")
            path = self._save_file(pic, pic.svg.encode("utf-8"), ".svg")
        elif fmt == "png" and pic.media_type != "image/png":
            if pic.svg is not None:
                try:
                    import cairosvg  # optional: pip install cairosvg
                    path = self._save_file(pic, cairosvg.svg2png(bytestring=pic.svg.encode("utf-8")), ".png")
                except ImportError:
                    path = self._save_file(pic, pic.svg.encode("utf-8"), ".svg")
                    self.log("Save picture", "PNG needs the cairosvg package (pip install cairosvg), so it was saved as SVG.", "note")
            else:
                path = self._save_file(pic)
        else:
            path = self._save_file(pic)
        self.log("Save picture", "Saved " + path, "saved")

    # ----- Draft and Review -----
    def set_task(self, t):
        self.task = to_str(t).strip()
        if not self.task:
            raise RunError("The task is empty. Type what you want into 'set task to'.")
        self.log("Task set", self.task, "set")

    def _need_task(self):
        if not self.task:
            raise RunError("Add a 'set task to' block before this step.")

    def _need_draft(self):
        if not self.draft:
            raise RunError("There's no draft yet. Put a 'write a first draft' or 'set draft to' block before this step.")

    async def generate(self):
        self._need_task()
        self.draft = await self._call("Complete the task below. Reply with only the finished piece, no preamble.\n\nTask:\n" + self.task)
        self.problems, self.approved = [], None
        self.log("Write a first draft", self.draft, "done")

    async def rework(self, instr):
        self._need_draft()
        instr = to_str(instr).strip()
        if not instr:
            raise RunError("The 'rework the draft' block has no instruction.")
        self.draft = await self._call("Rewrite the draft below following this instruction: " + instr +
                                      "\nKeep it true to the original task. Reply with only the rewritten piece.\n\nTask:\n" +
                                      (self.task or "(none given)") + "\n\nDraft:\n" + self.draft)
        self.log("Rework: " + _short(instr, 60), self.draft, "done")

    async def revise(self):
        self._need_draft()
        if not self.problems:
            self.log("Revise", "No review problems recorded, so nothing to fix.", "skipped")
            return
        fixed = [e for e in (self.reflect or {}).get("earlier", []) if e not in self.problems]
        keep = ("\n\nThese problems were fixed in earlier rounds. Don't bring them back:\n" + "\n".join("- " + e for e in fixed)) if fixed else ""
        self.draft = await self._call("Revise the draft so it fixes every problem listed. Change nothing else that works. "
                                      "Reply with only the improved piece.\n\nTask:\n" + (self.task or "(none given)") +
                                      "\n\nProblems:\n" + "\n".join("- " + p for p in self.problems) + keep + "\n\nDraft:\n" + self.draft)
        self.log("Revise to fix the problems", self.draft, "revised")

    def set_draft(self, t):
        self.draft = to_str(t)

    @contextlib.contextmanager
    def reviewing(self):
        """Around a 'review … up to N rounds' loop: remembers each round's problems and its best draft."""
        before = self.reflect
        self.reflect = {"earlier": [], "best": None, "round": 0}
        try:
            yield
        finally:
            self.reflect = before

    async def review(self, criteria, label="Review", in_loop=False):
        self._need_draft()
        loop = self.reflect if in_loop else None
        earlier = ("\n\nEarlier rounds of this review found the problems below. Check each one is still fixed, "
                   "and list it again if it has come back:\n" + "\n".join("- " + e for e in loop["earlier"])) if loop and loop["earlier"] else ""
        v = await self._call("You are a strict reviewer. Judge the draft ONLY against these criteria (separated by semicolons):\n" +
                             to_str(criteria) + "\n\nTask:\n" + (self.task or "(none given)") + "\n\nDraft:\n" + self.draft + earlier +
                             '\n\nReply with only JSON like {"approved": false, "problems": ["specific fixable problem"]}. '
                             "approved is true only if every criterion is met; problems is empty when approved.", SCHEMAS["review"])
        approved = v["approved"] is True
        problems = [to_str(p) for p in (v.get("problems") or [])]
        self.approved = approved
        self.problems = [] if approved else ([p for p in problems if p] or ["Does not yet meet the criteria."])
        if loop is not None:
            loop["round"] += 1
            best = loop["best"]
            if best is None or len(self.problems) <= best["n"]:  # a tie goes to the newer draft
                loop["best"] = {"draft": self.draft, "problems": list(self.problems), "n": len(self.problems), "round": loop["round"]}
            for p_ in self.problems:
                if p_ not in loop["earlier"]:
                    loop["earlier"].append(p_)
            del loop["earlier"][:-12]
        if approved:
            self.log(label, "Meets every criterion.", "approved")
        else:
            self.log(label, "\n".join("- " + p for p in self.problems), "needs work")
        return approved

    def rounds(self, n):
        return max(1, min(6, round_js(num(n)) or 3))

    def out_of_rounds(self):
        self.out_of_rounds_hit = True
        best = (self.reflect or {}).get("best")
        if best and best["round"] != self.reflect["round"]:
            self.draft, self.problems, self.approved = best["draft"], list(best["problems"]), False
            self.log("Kept the best draft", f"Went back to the draft from round {best['round']}: it had the fewest problems "
                     f"({best['n']}). The rounds after it didn't improve on it.", "best draft")
        self.log("Review", "Out of rounds. Keeping the best effort.", "failed")

    # ----- Checkpoints -----
    _SNAPSHOT = ("task", "draft", "problems", "approved", "answer", "result")

    def save_checkpoint(self, name):
        name = to_str(name).strip()
        if not name:
            raise RunError("The 'save checkpoint' block needs a name.")
        state = {k: getattr(self, k) for k in self._SNAPSHOT}
        state["vars"] = dict(self.vars)
        try:
            state = copy.deepcopy(state)
        except Exception:  # noqa: BLE001 - something uncopyable: keep references instead
            state = {k: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v) for k, v in state.items()}
        self.checkpoints[name.lower()] = state
        self.log("Checkpoint “" + name + "”", "Saved the task, draft, review, result and variables" +
                 (f". Draft: {_short(self.draft, 80)}" if self.draft else "."), "saved")

    def restore_checkpoint(self, name):
        name = to_str(name).strip()
        state = self.checkpoints.get(name.lower())
        if state is None:
            raise RunError(f"There's no checkpoint called “{name}” in this run. Put a 'save checkpoint' block before this one.")
        try:  # a copy, so the same checkpoint can be gone back to more than once
            state = copy.deepcopy(state)
        except Exception:  # noqa: BLE001
            state = {k: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v) for k, v in state.items()}
        for k in self._SNAPSHOT:
            setattr(self, k, state[k])
        self.vars.clear()
        self.vars.update(state["vars"])
        self.log("Back to checkpoint “" + name + "”", "Restored the task, draft, review, result and variables" +
                 (f". Draft: {_short(self.draft, 80)}" if self.draft else "."), "restored")

    # ----- You (the person at the keyboard) -----
    async def _input(self, prompt):
        async with self._lock("input"):  # one question at the keyboard at a time
            try:
                return await asyncio.to_thread(input, prompt)
            except EOFError:
                raise RunError("This step needs an answer typed at the keyboard, but there's no one to type it.")

    async def _ask_me_live(self, q):
        q = to_str(q)
        print("\n? " + q, flush=True)
        while True:
            a = (await self._input("> ")).strip()
            if a:
                self.answer = a
                return a
            print("  Type an answer first.")

    async def _approve_live(self, text):
        print("\n? Do you approve this?\n", flush=True)
        for line in to_str(text).splitlines():
            print("    " + line)
        while True:
            a = (await self._input("Approve? [y/n] > ")).strip().lower()
            if a in ("y", "yes"):
                return True
            if a in ("n", "no"):
                return False
            print("  Type y or n.")

    async def _choose_live(self, items):
        items = to_list(items)
        if not items:
            raise RunError("'let me choose from' got an empty list.")
        print("\n? Choose one:", flush=True)
        for i, it in enumerate(items, 1):
            print(f"  {i}. {_short(it, 80)}")
        while True:
            a = (await self._input("Number > ")).strip()
            if a.isdigit() and 1 <= int(a) <= len(items):
                return items[int(a) - 1]
            print(f"  Type a number from 1 to {len(items)}.")

    async def pause(self, note):
        print("\n⏸ " + (to_str(note) or "Paused."), flush=True)
        await self._input("Press Enter to continue > ")

    # ----- Output -----
    def say(self, v):
        if isinstance(v, Picture):
            self.log("Note", "Picture: " + self._picture_path(v))
        else:
            self.log("Note", to_str(v))

    def show(self):
        self.log("Current draft", self.draft or "(no draft yet)")

    def _result_item(self, v):
        if isinstance(v, Picture):
            return "[picture: " + self._picture_path(v) + "]"
        return to_str(v)

    def add_result(self, v):
        item = self._result_item(v)
        self.result.append(item)
        self.log("Added to result", item, "added")

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
            raise RunError(f"A list block asked for item {i + 1} but the list has {len(lst)} items.")
        v = lst[i]
        if mode != "GET":
            del lst[i]
            if var is not None:
                self.vars[var] = lst
        return v

    def list_set(self, var, mode, where, at, value):
        if var is None:
            raise RunError("To change a list, put a list variable in the 'in list' slot.")
        lst = list(to_list(self.get(var)))
        i = self._index(lst, where, at, mode == "INSERT")
        if mode == "INSERT":
            lst.insert(max(0, min(i, len(lst))), value)
        else:
            if i < 0 or i >= len(lst):
                raise RunError("A list 'set' block points past the end of the list.")
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
            self.log("Wait", f"Waiting {secs:g} seconds")
        await asyncio.sleep(secs)

    async def wait_until_time(self, h, m):
        now = datetime.datetime.now()
        t = now.replace(hour=int(h), minute=int(m), second=0, microsecond=0)
        if t <= now:
            t += datetime.timedelta(days=1)
        self.log("Wait until a time", "Waiting until " + t.strftime("%H:%M") + (" tomorrow" if t.date() != now.date() else ""))
        await asyncio.sleep((t - now).total_seconds())

    async def wait_until(self, check, uses_claude=False):
        while not to_bool(await check()):
            await asyncio.sleep(10 if uses_claude else 0.5)

    async def wait_for_message(self, name):
        key = to_str(name).strip().lower()
        self.log("Waiting for “" + to_str(name) + "”", "Carries on when another script broadcasts this message.")
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
        self.log("Model", "Using " + model_label(tier))

    @contextlib.asynccontextmanager
    async def using_model(self, tier):
        token = MODEL_OVERRIDE.set(tier)
        self.log("Model", "Using " + model_label(tier) + " for the blocks inside")
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
            raise RunError("A broadcast block has no message name.")
        waiters = self.msg_waiters.pop(key, [])
        for f in waiters:
            if not f.done():
                f.set_result(value)
        fns = self.receivers.get(key, [])
        if not fns and not waiters:
            self.log("Broadcast “" + to_str(name) + "”", "Nobody is listening for this message.", "no listeners")
            return []
        self.started += len(fns)
        if self.started > MAX_SCRIPTS:
            raise RunError(f"Stopped after starting {MAX_SCRIPTS} scripts. A message may be broadcasting itself in a loop.")
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
            raise RunError(f"The program “{name}” runs itself (" + " → ".join(self.programs + [name]) + "), which would never end.")
        if len(self.programs) >= 10:
            raise RunError("Programs inside programs went more than 10 deep, so the run stopped.")
        busy = [t for t in self.tasks if not t.done() and t is not asyncio.current_task()]
        if busy:
            raise RunError(f"“{name}” can't run while other scripts are running at the same time. "
                           "Run it from a script that runs on its own (not alongside a broadcast).")
        saved = {k: getattr(self, k) for k in self.STATE}
        saved_vars = dict(self.vars)
        self.task, self.draft, self.problems, self.approved, self.answer = "", "", [], None, ""
        self.result, self.out_of_rounds_hit, self.instructions, self.chats, self.last_error = [], False, "", {}, ""
        self.checkpoints, self.reflect, self.agent_trace = {}, None, []
        self.vars.clear()
        token = MESSAGE_VALUE.set(value)
        self.programs.append(name)
        self.log("Program: " + name, "Started" + (f" with: {_short(to_str(value), 200)}" if to_str(value).strip() else "."), "running")
        try:
            try:
                await fn()
            except Finish:
                pass
            out = "\n\n".join(to_str(x) for x in self.result) if self.result else self.draft
            self.log("Program: " + name, out or "(no result)", "done")
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

    async def run(self, scripts, label="Run"):
        self.reset()
        self.run_label = label
        print(f"\n=== {label} · {datetime.datetime.now():%H:%M} ===", flush=True)
        finished = False
        try:
            if not self.schedule_mode:
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
                self.error = RunError(f"The run took longer than {self.max_seconds:g} seconds (max_seconds in second-thought.ini), so it stopped.")
                self._end()
            if not self.ending and not self.schedule_mode and self.tasks and self.msg_waiting >= len(self.tasks):
                names = ", ".join("“" + k + "”" for k in self.msg_waiters)
                self.error = RunError("Every script is waiting for " + names + ", but nothing running can send it.")
                self._end()
        if self.error:
            msg = str(self.error) if isinstance(self.error, RunError) else f"{type(self.error).__name__}: {self.error}"
            print("\n✖ Run stopped: " + msg, flush=True)
            return 1
        text = "\n\n".join(self.result) if self.result else self.draft
        if text:
            print("\n" + "=" * 60 + ("\nRESULT (best effort)\n" if self.out_of_rounds_hit else "\nRESULT\n") + "=" * 60, flush=True)
            print(text, flush=True)
        else:
            print("\nThe program ended without a result.", flush=True)
        used = " · ".join(f"{who}: {u[0]:,} tokens in, {u[1]:,} out" for who, u in self.usage.items()) or "no tokens used"
        spare = f" · a backup answered {self.backup_used} step{'s' if self.backup_used != 1 else ''}" if self.backup_used else ""
        budget = f" · budget {self.budget:,}" if self.budget else ""
        print(f"\nDone · {self.calls} model call{'s' if self.calls != 1 else ''} · {used}{spare}{budget}", flush=True)
        return 0

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
        if self.budget:
            lines.append(f"- Budget: {self.budget:,} tokens")
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
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            print(f"Log saved to {path}", flush=True)
        except OSError as e:
            print(f"(The log couldn't be saved: {e})", flush=True)

    # ----- Schedules -----
    async def run_schedules(self, schedules, watches=(), telegram=(), listeners=()):
        if not schedules and not watches and not telegram and not listeners:
            sys.exit("This program has no scheduled scripts, and nothing that listens.")
        self.schedule_mode = True
        print("Schedules are on. Leave this running; press Ctrl+C to stop.", flush=True)
        if watches:
            asyncio.ensure_future(self._watch(watches))
        if telegram:
            if not self._tg_chats():
                print(f"Telegram: send your bot a message. Until TELEGRAM_CHAT_ID is set {WHERE_KEYS}, the program only says which chat it came from.", flush=True)
            asyncio.ensure_future(self._tg_watch(telegram))
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
                    if busy and not busy.done():
                        self.start_script(fn)
                    else:
                        busy = asyncio.ensure_future(self.run([fn], s[-2] if s[0] == "every" else f"Scheduled {s[1]:02d}:{s[2]:02d}"))
            await asyncio.sleep(5)

    async def _watch(self, watches):
        """Polls Home Assistant and starts 'when … changes' scripts."""
        last = {}
        first = True
        busy = None
        while True:
            try:
                states = {e["entity_id"]: e for e in await self._ha("GET", "/api/states")}
            except RunError as e:
                print("  (Home Assistant check failed: " + str(e) + ")", flush=True)
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
                    busy = asyncio.ensure_future(self.run([(fn, payload)], f"When {entity} changes"))
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

    def approve_program(self, can, unattended=False):
        """True if the program may run. One that can act on the world lists what it can do and asks once; the yes is
        kept in .<program>.approved until the program file changes. approve = no in second-thought.ini skips this."""
        if not self.can_acts(can) or os.environ.get("RB_APPROVE", "").strip().lower() in ("no", "0", "false", "off"):
            return True
        path, digest = self._approval_path()
        if path:
            try:
                with open(path, encoding="utf-8") as f:
                    if json.load(f).get("sha256") == digest:
                        return True
            except (OSError, ValueError, AttributeError):
                pass
        lines, tail = self.can_lines(can)
        print("\nThis program can:", flush=True)
        for line in lines:
            print("  - " + line)
        for line in tail:
            print(line)
        nobody = (f"\nIt hasn't been allowed to do these on this computer yet, and nobody is here to ask. Run it once yourself, "
                  f"not on a schedule, and answer y. Or put approve = no {WHERE_KEYS}.")
        if unattended:
            print(nobody, flush=True)
            return False
        print("\n? Allow it to do these things on this computer? It won't ask again unless the program changes.", flush=True)
        while True:
            try:
                a = input("Approve? [y/n] > ").strip().lower()
            except EOFError:  # no keyboard after all (on Windows, a scheduled task's input can look like one)
                print(nobody, flush=True)
                return False
            if a in ("y", "yes"):
                break
            if a in ("n", "no"):
                print("Not allowed, so it didn't run.")
                return False
            print("  Type y or n.")
        if path:
            try:
                _write_json(path, {"sha256": digest, "allowed": list(can.get("can", [])), "runtime": RUNTIME_VERSION,
                                   "when": datetime.datetime.now().isoformat(timespec="seconds")}, indent=1)
            except OSError as e:
                print(f"  (Couldn't note that you said yes, so it will ask again next time: {e})")
        return True

    def main(self, start_scripts, receivers, schedules, watches=(), telegram=(), listeners=(), can=None):
        if "--version" in sys.argv:
            print(f"Second Thought runtime {RUNTIME_VERSION}")
            return
        self.receivers = {k.lower(): v for k, v in receivers.items()}
        use_schedule = "--schedule" in sys.argv or ((schedules or watches or telegram or listeners) and not start_scripts)
        if not self.approve_program(can, unattended=bool(use_schedule) and not sys.stdin.isatty()):
            sys.exit(1)
        try:
            if use_schedule:
                asyncio.run(self.run_schedules(schedules, watches, telegram, listeners))
            else:
                if not start_scripts:
                    sys.exit("Nothing to run: this program has no 'when Run is clicked' script.")
                sys.exit(asyncio.run(self.run(start_scripts)))
        except KeyboardInterrupt:
            print("\nStopped.")
