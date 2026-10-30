"""--doctor: checks a program's setup without spending anything or acting on anything.

Part of the second_thought package. tools/sync.py joins these files, in order, into
python/runtime.py, which is what ships inside every exported program and the page.
"""
import asyncio
import json
import os
import sys
import urllib.error
import urllib.request
from .settings import KEY_SOURCES, KEYCHAIN_NAMES, KEYCHAIN_PROBLEM, RUNTIME_VERSION, SETTINGS_PATH, WHERE_KEYS
from .providers import MODELS, PROVIDERS, SERVICES, TIER_NAMES, _tier
from .core import CAPABILITIES, LOG_DIR, MEMORY_FILE, OUTPUT_DIR, RunError, _short, to_str
from .connectors import webhook_host
from .settings import tr  # noqa: F401
# ---- package only: tools/sync.py leaves everything above this line out of python/runtime.py ----
import difflib  # noqa: E402,F811 - below the line, so python/runtime.py has it too
import re  # noqa: E402,F811
import importlib.metadata  # noqa: E402,F811 - below the line, so python/runtime.py has them too
import importlib.util  # noqa: E402,F811
import socket  # noqa: E402,F811


class Doctor:
    """python my-program.py --doctor. Part of Runtime.

    Checks only what the program uses (from CAN), reading only: model keys with each service's free list of models,
    connections by reading from them, MCP servers by listing their tools. Nothing is sent, posted, switched or charged.
    """
    DOCTOR_TIMEOUT = 20

    @staticmethod
    def _doctor_get(url, headers, timeout):
        """(status, parsed JSON or None, error text). Status 0 means it couldn't be reached."""
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
                try:
                    return r.status, json.loads(r.read(3_000_000) or b"null"), ""
                except ValueError:
                    return r.status, None, ""
        except urllib.error.HTTPError as e:
            return e.code, None, ""
        except (urllib.error.URLError, OSError, ValueError) as e:
            return 0, None, to_str(getattr(e, "reason", e))

    @staticmethod
    def _doctor_package(module, pip):
        if importlib.util.find_spec(module.split(".")[0]) is None or (("." in module) and importlib.util.find_spec(module) is None):
            return None
        try:
            return importlib.metadata.version(pip)
        except importlib.metadata.PackageNotFoundError:
            return tr("installed")

    async def _doctor_listed(self, s, key):
        """Asks one model service which models it has: (HTTP status, the model names, an error)."""
        if s["api"] == "anthropic":
            url = (os.environ.get("ANTHROPIC_BASE_URL") or "https://api.anthropic.com").rstrip("/") + "/v1/models?limit=1000"
            headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
        elif s["api"] == "gemini":
            url = (os.environ.get("GEMINI_BASE_URL") or "https://generativelanguage.googleapis.com").rstrip("/") + "/v1beta/models?pageSize=1000"
            headers = {"x-goog-api-key": key}
        else:
            pv = PROVIDERS[s["name"]]
            url, headers = pv["base"] + "/models", dict(pv["headers"], **({"Authorization": "Bearer " + key} if key else {}))
        status, body, err = await asyncio.to_thread(self._doctor_get, url, headers, self.DOCTOR_TIMEOUT)
        items = (body.get("data") or body.get("models") or []) if isinstance(body, dict) else body if isinstance(body, list) else []
        return status, {to_str(m.get("id") or m.get("name")).replace("models/", "") for m in items if isinstance(m, dict)}, err

    @staticmethod
    def retired_models(tiers, have):
        """(tier, model, the closest model the service does list) for each tier whose model isn't in the service's list."""
        out = []
        for t in tiers:
            m = MODELS.get(t)
            if m and have and m not in have and m + ":latest" not in have:
                family = re.match(r"[^0-9]*", m).group(0)  # claude-opus-, gpt-, gemini-: only suggest one of the same kind
                same = sorted(h for h in have if h.startswith(family)) if family else sorted(have)
                close = difflib.get_close_matches(m, same, n=1, cutoff=0.6)
                out.append((t, m, close[0] if close else ""))
        return out

    @staticmethod
    def model_setting(tier, model=""):
        """The second-thought.ini line that changes a tier's model, like  MODEL_DEFAULT = claude-sonnet-5-5."""
        return "MODEL_" + tier.upper().replace("-", "_") + " = " + (model or "<model name>")

    @staticmethod
    def service_tiers(s):
        return [_tier(s, k) for k in TIER_NAMES if k in s["tiers"]]

    async def _doctor_model(self, s):
        """One model service: is its key there, and does the service accept it?"""
        key = next((os.environ[k] for k in s["keys"] if os.environ.get(k)), "")
        if s["signup"] and not key:
            return "FAIL", tr("no key. Put {x} = your-key {where_keys} ({signup}).", x=s['keys'][0], where_keys=WHERE_KEYS, signup=s['signup'])
        if s["api"] == "perplexity":
            return "ok", tr("{x} is set (Perplexity has no free way to try it, so it isn't checked further)", x=s['keys'][0])
        status, have, err = await self._doctor_listed(s, key)
        if status == 0:
            hint = " Is Ollama running? Start it with  ollama serve" if s["name"] == "Llama" else ""
            return "FAIL", tr("couldn't be reached ({err}).{hint}", err=_short(err, 120), hint=hint)
        if status in (401, 403):
            return "FAIL", tr("refused the key ({status}). Check {x} {where_keys}.", status=status, x=s['keys'][0], where_keys=WHERE_KEYS)
        if status != 200:
            return "NOTE", tr("answered {status} when asked which models it has, so the key couldn't be checked", status=status)
        used = [t for t in self._doctor_tiers() if (t.startswith(s["prefix"]) if s["prefix"] else "-" not in t)]
        retired = self.retired_models(used, have)
        if retired:
            missing = sorted({m for _, m, _ in retired})
            hint = "  ollama pull " + "  /  ollama pull ".join(missing) if s["name"] == "Llama" else " " + tr(
                "It may have been retired. To use another without changing the program, put a model it does list in second-thought.ini, such as {settings}.",
                settings="  /  ".join(self.model_setting(t, close) for t, _, close in retired))
            return "NOTE", tr("the key works, but it doesn't list {x}, which this program uses.{hint}", x=', '.join(missing), hint=hint)
        return "ok", (tr("the key works ({n} models)", n=len(have)) if have else tr("the key works"))

    def _doctor_tiers(self):
        tiers = [getattr(self, "primary", None)] + list(getattr(self, "backups", None) or [])
        return [t for t in tiers if isinstance(t, str) and t]

    async def _doctor_connections(self, can, mcp):
        """(area, coroutine giving the detail) for each connection the program uses. Every one only reads."""
        has = lambda *ids: any(i in can for i in ids)  # noqa: E731
        out = []
        if has("ha_read", "ha_act"):
            async def ha():
                await self._ha("GET", "/api/")
                cfg = await self._ha("GET", "/api/config")
                return f"reached Home Assistant {cfg.get('version', '')}".strip() if isinstance(cfg, dict) else tr("reached")
            out.append(("Home Assistant", ha))
        if has("homey_read", "homey_act"):
            async def homey():
                home = await self._homey_home()
                return tr("reached: {home} devices", home=len(home))
            out.append(("Homey", homey))
        if has("mqtt_read", "mqtt_publish"):
            async def mqtt():
                await self.mqtt_read("second-thought/doctor", 1.0)
                return tr("connected to the broker")
            out.append(("MQTT", mqtt))
        if has("telegram_read", "telegram_send"):
            async def tg():
                me = await self._tg("getMe")
                chat = "" if os.environ.get("TELEGRAM_CHAT_ID") else (" (no TELEGRAM_CHAT_ID yet: message your bot, then run a "
                                                                      "Telegram program to see your chat number)")
                return tr("the bot is @{x}{chat}", x=to_str((me or {}).get("username")), chat=chat)
            out.append(("Telegram", tg))
        for svc, name in (("discord", "Discord"), ("slack", "Slack")):
            if has(svc + "_read", svc + "_send"):
                async def chat(svc=svc):
                    await self.chat_search(svc, "", 5)
                    return tr("read your channels")
                out.append((name, chat))
        if has("email_read"):
            async def mail_in():
                await self.email_search("", 2)
                return tr("read the inbox")
            out.append(("Email (reading)", mail_in))
        if has("email_send"):
            async def mail_out():
                import smtplib
                c = self._mail()

                def go():
                    s_ = smtplib.SMTP_SSL(c["smtp"], 465, timeout=30) if c["ssl"] and c["smtp_port"] == 465 else smtplib.SMTP(c["smtp"], c["smtp_port"], timeout=30)
                    with s_:
                        if c["ssl"] and c["smtp_port"] != 465:
                            s_.starttls()
                        s_.login(c["addr"], c["pw"])
                try:
                    await asyncio.to_thread(go)
                except smtplib.SMTPAuthenticationError:
                    raise RunError(tr("the email server refused EMAIL_ADDRESS and EMAIL_PASSWORD {where_keys}. Use an app password.", where_keys=WHERE_KEYS)) from None
                except (smtplib.SMTPException, OSError) as e:
                    raise RunError(tr("couldn't sign in to {smtp} to send ({e})", smtp=c['smtp'], e=_short(e, 120))) from None
                return tr("signed in to {smtp} (nothing was sent)", smtp=c['smtp'])
            out.append(("Email (sending)", mail_out))
        if has("github_read", "github_comment"):
            async def gh():
                await self.gh_for_me()
                return tr("read your pull requests")
            out.append(("GitHub", gh))
        if has("calendar"):
            async def cal():
                lines = await self.calendar_text("today", 7)
                return tr("read the next 7 days ({x} lines)", x=len(to_str(lines).splitlines()))
            out.append(("Calendar", cal))
        if has("feeds") and os.environ.get("RB_FEEDS", "").strip():
            async def feeds():
                items = await self.feed_items("", 3)
                return tr("read your feeds ({items} items)", items=len(items))
            out.append(("News feeds", feeds))
        if has("webhook"):
            async def hook():
                if not os.environ.get("WEBHOOK_SECRET", "").strip():
                    raise RunError(tr("no WEBHOOK_SECRET {where_keys}, so the program won't listen for web requests. Set it to a long password.", where_keys=WHERE_KEYS))
                host, port = webhook_host(), int(os.environ.get("WEBHOOK_PORT") or 8765)
                with socket.socket() as so:
                    try:
                        so.bind((host, port))
                    except OSError as e:
                        raise RunError(tr("port {port} can't be used ({e}): something else may be listening. Change WEBHOOK_PORT.", port=port, e=_short(e, 80))) from None
                return tr("port {port} is free, and WEBHOOK_SECRET is set", port=port)
            out.append(("Web requests", hook))
        for name in mcp:
            async def server(name=name):
                tools = await self.mcp_tools(name)
                return tr("{tools} tools, MCP {version}", tools=len(tools), version=self._mcp(name).version)
            out.append((f"MCP server “{name}”", server))
        if has("memory"):
            async def memory():
                folder = os.path.dirname(os.path.abspath(MEMORY_FILE))
                if os.path.exists(MEMORY_FILE):
                    with open(MEMORY_FILE, encoding="utf-8") as f:
                        try:
                            n = len(json.load(f))
                        except ValueError:
                            raise RunError(tr("{memory_file} isn't valid JSON, so saved notes can't be read", memory_file=MEMORY_FILE)) from None
                    if not os.access(MEMORY_FILE, os.W_OK):
                        raise RunError(tr("{memory_file} can't be written to", memory_file=MEMORY_FILE))
                    return tr("{n} saved notes, in {memory_file}", n=n, memory_file=MEMORY_FILE)
                if not os.access(folder, os.W_OK):
                    raise RunError(tr("notes can't be saved: {folder} can't be written to", folder=folder))
                return tr("nothing saved yet; notes will go in {memory_file}", memory_file=MEMORY_FILE)
            out.append(("Memory", memory))
        if has("files_save"):
            async def outputs():
                here = os.path.abspath(OUTPUT_DIR)
                where = here if os.path.isdir(here) else os.path.dirname(here)
                if not os.access(where, os.W_OK):
                    raise RunError(tr("files can't be saved: {where} can't be written to", where=where))
                return tr("files will be saved in {here}", here=here)
            out.append(("Saving files", outputs))
        return out

    async def doctor(self, can):
        """Runs every check, prints one line each, and gives the exit code: 0 when nothing failed."""
        prog = os.path.basename(sys.argv[0] or "this program")
        print(tr("Checking {prog} (runtime {runtime_version}, Python {x}).", prog=prog, runtime_version=RUNTIME_VERSION, x=sys.version.split()[0]), flush=True)
        print(tr("Only reading: nothing is sent, posted, switched or charged.\n"), flush=True)
        self.reset()
        quiet, self.log = self.log, (lambda *a, **k: None)
        rows = []

        def row(status, area, text):
            rows.append(status)
            print(f"  {status:<5} {tr(area)}: {text}", flush=True)  # ok, FAIL and NOTE stay as they are, for scripts that read them

        known = can is not None
        can = can or {}
        ids = list(can.get("can", [])) if known else [c[0] for c in CAPABILITIES]  # an older program: check whatever is set up
        row("ok" if sys.version_info >= (3, 9) else "FAIL", "Python", sys.version.split()[0] + ("" if sys.version_info >= (3, 9) else ": " + tr("Second Thought needs 3.9 or newer")))
        row("ok" if SETTINGS_PATH else "NOTE", "Settings", tr("read {settings_path}", settings_path=SETTINGS_PATH) if SETTINGS_PATH else
            tr("no second-thought.ini found next to the program, in this folder or in your home folder, so only environment variables are used"))
        found = [(k, KEY_SOURCES.get(k)) for k in KEYCHAIN_NAMES if os.environ.get(k)]
        where = {"environment": tr("the environment"), "file": "second-thought.ini", "keychain": tr("the keychain")}
        if found:
            row("ok", "Keys", ", ".join(f"{k} ({where.get(src) or where['environment']})" for k, src in found))
        if KEYCHAIN_PROBLEM:
            row("NOTE", "Keychain", tr("keyring is installed but the keychain couldn't be read ({problem}), so keys only come from the "
                                      "environment and second-thought.ini", problem=_short(KEYCHAIN_PROBLEM, 120)))
        row("ok", "MCP tool", tr("with --mcp, it serves one tool, “{name}”, to Claude and other agents", name=self.mcp_tool_name()))
        names = list(can.get("services", [])) if known else ["Claude"] + [s["name"] for s in SERVICES
                                                                          if s["name"] != "Claude" and any(os.environ.get(k) for k in s["keys"])]
        services = [s for s in SERVICES if s["name"] in names]
        needs = [("anthropic", "anthropic", "Claude")] if any(s["api"] == "anthropic" for s in services) else []
        needs += [("google.genai", "google-genai", "Gemini")] if any(s["api"] == "gemini" for s in services) else []
        needs += [("paho.mqtt.client", "paho-mqtt", "MQTT")] if known and any(i in ids for i in ("mqtt_read", "mqtt_publish")) else []
        needs += [("tzdata", "tzdata", "calendars on Windows")] if os.name == "nt" and known and "calendar" in ids else []
        for module, pip, why in needs:
            v = self._doctor_package(module, pip)
            row("ok" if v else "FAIL", tr("Package {name}", name=pip), (v if v != "installed" else tr("installed")) if v else tr("missing (needed for {why}). Install it with:  pip install {pip}", why=why, pip=pip))
        if known and "files_read" in ids and not self._doctor_package("pypdf", "pypdf"):
            row("NOTE", "Package pypdf", tr("not installed, so PDFs can't be read (other files can). Install it with:  pip install pypdf"))
        for s in services:
            try:
                status, text = await self._doctor_model(s)
            except Exception as e:  # noqa: BLE001 - one check's trouble is reported, then the next runs
                status, text = "FAIL", _short(self._describe(e), 200)
            row(status, s["name"], text)
        for area, check in await self._doctor_connections(ids, [n for n in can.get("mcp", []) if to_str(n).strip()]):
            if not known and not self._doctor_configured(area):
                continue
            try:
                row("ok", area, await check())
            except Exception as e:  # noqa: BLE001
                row("FAIL", area, _short(self._describe(e), 240))
        if known and self.can_acts(can):
            path, digest = self._approval_path()
            allowed, before = False, None
            if path and os.path.exists(path):
                try:
                    with open(path, encoding="utf-8") as f:
                        before = json.load(f)
                    allowed = before.get("sha256") == digest
                except (OSError, ValueError, AttributeError):
                    before = None
            skip = os.environ.get("RB_APPROVE", "").strip().lower() in ("no", "0", "false", "off")
            changed = " ".join(line.strip() for line in self.changes_since(before, can)) if before and not allowed else ""
            row("ok" if allowed or skip else "NOTE", "First run", tr("approve = no, so it doesn't ask") if skip else
                tr("allowed on this computer") if allowed else
                tr("{changes} Run it once yourself and answer y (a scheduled run won't start until then).", changes=changed) if changed else
                tr("not allowed on this computer yet. Run it once yourself and answer y (a scheduled run won't start until then)."))
        if os.environ.get("RB_SAVE_LOG", "").strip().lower() in ("1", "yes", "true", "on"):
            folder = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0] or ".")), LOG_DIR)
            ok = os.access(folder if os.path.isdir(folder) else os.path.dirname(folder), os.W_OK)
            row("ok" if ok else "FAIL", "Run logs", tr("saved in {folder}", folder=folder) if ok else tr("can't be saved in {folder}", folder=folder))
        for server in self.__dict__.get("_mcp_servers", {}).values():
            if hasattr(server, "close"):
                server.close()
        self.log = quiet
        fails, notes = rows.count("FAIL"), rows.count("NOTE")
        print()
        if fails:
            print(tr("1 problem to fix: the line marked FAIL. Then run --doctor again.") if fails == 1 else
                  tr("{n} problems to fix: the lines marked FAIL. Then run --doctor again.", n=fails))
        else:
            print(tr("Everything checked is ready.") + ((" " + (tr("1 note above.") if notes == 1 else tr("{n} notes above.", n=notes))) if notes else ""))
        return 1 if fails else 0

    @staticmethod
    def _doctor_configured(area):
        """For a program exported before CAN: is this connection set up at all?"""
        need = {"Home Assistant": "HA_TOKEN", "Homey": "HOMEY_API_KEY", "MQTT": "MQTT_HOST", "Telegram": "TELEGRAM_BOT_TOKEN",
                "Discord": "DISCORD_BOT_TOKEN", "Slack": "SLACK_BOT_TOKEN", "Email (reading)": "EMAIL_ADDRESS", "GitHub": "GITHUB_TOKEN",
                "Calendar": "CALENDAR_URL", "News feeds": "RB_FEEDS", "Web requests": "WEBHOOK_SECRET"}.get(area)
        return bool(need and os.environ.get(need))
