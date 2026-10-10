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
from .settings import RUNTIME_VERSION, SETTINGS_PATH, WHERE_KEYS
from .providers import MODELS, PROVIDERS, SERVICES
from .core import CAPABILITIES, LOG_DIR, MEMORY_FILE, OUTPUT_DIR, RunError, _short, to_str
# ---- package only: tools/sync.py leaves everything above this line out of python/runtime.py ----
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
            return "installed"

    async def _doctor_model(self, s):
        """One model service: is its key there, and does the service accept it?"""
        key = next((os.environ[k] for k in s["keys"] if os.environ.get(k)), "")
        if s["signup"] and not key:
            return "FAIL", f"no key. Put {s['keys'][0]} = your-key {WHERE_KEYS} ({s['signup']})."
        if s["api"] == "perplexity":
            return "ok", f"{s['keys'][0]} is set (Perplexity has no free way to try it, so it isn't checked further)"
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
        if status == 0:
            hint = " Is Ollama running? Start it with  ollama serve" if s["name"] == "Llama" else ""
            return "FAIL", f"couldn't be reached ({_short(err, 120)}).{hint}"
        if status in (401, 403):
            return "FAIL", f"refused the key ({status}). Check {s['keys'][0]} {WHERE_KEYS}."
        if status != 200:
            return "NOTE", f"answered {status} when asked which models it has, so the key couldn't be checked"
        items = (body.get("data") or body.get("models") or []) if isinstance(body, dict) else body if isinstance(body, list) else []
        have = {to_str(m.get("id") or m.get("name")).replace("models/", "") for m in items if isinstance(m, dict)}
        used = [MODELS.get(t) for t in self._doctor_tiers() if (t.startswith(s["prefix"]) if s["prefix"] else "-" not in t)]
        missing = sorted({m for m in used if m and have and m not in have and m + ":latest" not in have})
        if missing:
            hint = "  ollama pull " + "  /  ollama pull ".join(missing) if s["name"] == "Llama" else \
                " Check the model name in MODELS, or MODEL_<TIER> in second-thought.ini."
            return "NOTE", f"the key works, but it doesn't list {', '.join(missing)}, which this program uses.{hint}"
        return "ok", "the key works" + (f" ({len(have)} models)" if have else "")

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
                return f"reached Home Assistant {cfg.get('version', '')}".strip() if isinstance(cfg, dict) else "reached"
            out.append(("Home Assistant", ha))
        if has("homey_read", "homey_act"):
            async def homey():
                home = await self._homey_home()
                return f"reached: {len(home)} devices"
            out.append(("Homey", homey))
        if has("mqtt_read", "mqtt_publish"):
            async def mqtt():
                await self.mqtt_read("second-thought/doctor", 1.0)
                return "connected to the broker"
            out.append(("MQTT", mqtt))
        if has("telegram_read", "telegram_send"):
            async def tg():
                me = await self._tg("getMe")
                chat = "" if os.environ.get("TELEGRAM_CHAT_ID") else (" (no TELEGRAM_CHAT_ID yet: message your bot, then run a "
                                                                      "Telegram program to see your chat number)")
                return "the bot is @" + to_str((me or {}).get("username")) + chat
            out.append(("Telegram", tg))
        for svc, name in (("discord", "Discord"), ("slack", "Slack")):
            if has(svc + "_read", svc + "_send"):
                async def chat(svc=svc):
                    await self.chat_search(svc, "", 5)
                    return "read your channels"
                out.append((name, chat))
        if has("email_read"):
            async def mail_in():
                await self.email_search("", 2)
                return "read the inbox"
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
                    raise RunError(f"the email server refused EMAIL_ADDRESS and EMAIL_PASSWORD {WHERE_KEYS}. Use an app password.") from None
                except (smtplib.SMTPException, OSError) as e:
                    raise RunError(f"couldn't sign in to {c['smtp']} to send ({_short(e, 120)})") from None
                return f"signed in to {c['smtp']} (nothing was sent)"
            out.append(("Email (sending)", mail_out))
        if has("github_read", "github_comment"):
            async def gh():
                await self.gh_for_me()
                return "read your pull requests"
            out.append(("GitHub", gh))
        if has("calendar"):
            async def cal():
                lines = await self.calendar_text("today", 7)
                return f"read the next 7 days ({len(to_str(lines).splitlines())} lines)"
            out.append(("Calendar", cal))
        if has("feeds") and os.environ.get("RB_FEEDS", "").strip():
            async def feeds():
                items = await self.feed_items("", 3)
                return f"read your feeds ({len(items)} items)"
            out.append(("News feeds", feeds))
        if has("webhook"):
            async def hook():
                if not os.environ.get("WEBHOOK_SECRET", "").strip():
                    raise RunError(f"no WEBHOOK_SECRET {WHERE_KEYS}, so the program won't listen for web requests. Set it to a long password.")
                host, port = os.environ.get("WEBHOOK_HOST", "0.0.0.0"), int(os.environ.get("WEBHOOK_PORT") or 8765)
                with socket.socket() as so:
                    try:
                        so.bind((host, port))
                    except OSError as e:
                        raise RunError(f"port {port} can't be used ({_short(e, 80)}): something else may be listening. Change WEBHOOK_PORT.") from None
                return f"port {port} is free, and WEBHOOK_SECRET is set"
            out.append(("Web requests", hook))
        for name in mcp:
            async def server(name=name):
                tools = await self.mcp_tools(name)
                return f"{len(tools)} tools, MCP {self._mcp(name).version}"
            out.append((f"MCP server “{name}”", server))
        if has("memory"):
            async def memory():
                folder = os.path.dirname(os.path.abspath(MEMORY_FILE))
                if os.path.exists(MEMORY_FILE):
                    with open(MEMORY_FILE, encoding="utf-8") as f:
                        try:
                            n = len(json.load(f))
                        except ValueError:
                            raise RunError(f"{MEMORY_FILE} isn't valid JSON, so saved notes can't be read") from None
                    if not os.access(MEMORY_FILE, os.W_OK):
                        raise RunError(f"{MEMORY_FILE} can't be written to")
                    return f"{n} saved notes, in {MEMORY_FILE}"
                if not os.access(folder, os.W_OK):
                    raise RunError(f"notes can't be saved: {folder} can't be written to")
                return "nothing saved yet; notes will go in " + MEMORY_FILE
            out.append(("Memory", memory))
        if has("files_save"):
            async def outputs():
                here = os.path.abspath(OUTPUT_DIR)
                where = here if os.path.isdir(here) else os.path.dirname(here)
                if not os.access(where, os.W_OK):
                    raise RunError(f"files can't be saved: {where} can't be written to")
                return "files will be saved in " + here
            out.append(("Saving files", outputs))
        return out

    async def doctor(self, can):
        """Runs every check, prints one line each, and gives the exit code: 0 when nothing failed."""
        prog = os.path.basename(sys.argv[0] or "this program")
        print(f"Checking {prog} (runtime {RUNTIME_VERSION}, Python {sys.version.split()[0]}).", flush=True)
        print("Only reading: nothing is sent, posted, switched or charged.\n", flush=True)
        self.reset()
        quiet, self.log = self.log, (lambda *a, **k: None)
        rows = []

        def row(status, area, text):
            rows.append(status)
            print(f"  {status:<5} {area}: {text}", flush=True)

        known = can is not None
        can = can or {}
        ids = list(can.get("can", [])) if known else [c[0] for c in CAPABILITIES]  # an older program: check whatever is set up
        row("ok" if sys.version_info >= (3, 9) else "FAIL", "Python", sys.version.split()[0] + ("" if sys.version_info >= (3, 9) else ": Second Thought needs 3.9 or newer"))
        row("ok" if SETTINGS_PATH else "NOTE", "Settings", f"read {SETTINGS_PATH}" if SETTINGS_PATH else
            "no second-thought.ini found next to the program, in this folder or in your home folder, so only environment variables are used")
        names = list(can.get("services", [])) if known else ["Claude"] + [s["name"] for s in SERVICES
                                                                          if s["name"] != "Claude" and any(os.environ.get(k) for k in s["keys"])]
        services = [s for s in SERVICES if s["name"] in names]
        needs = [("anthropic", "anthropic", "Claude")] if any(s["api"] == "anthropic" for s in services) else []
        needs += [("google.genai", "google-genai", "Gemini")] if any(s["api"] == "gemini" for s in services) else []
        needs += [("paho.mqtt.client", "paho-mqtt", "MQTT")] if known and any(i in ids for i in ("mqtt_read", "mqtt_publish")) else []
        needs += [("tzdata", "tzdata", "calendars on Windows")] if os.name == "nt" and known and "calendar" in ids else []
        for module, pip, why in needs:
            v = self._doctor_package(module, pip)
            row("ok" if v else "FAIL", "Package " + pip, (v if v != "installed" else "installed") if v else f"missing (needed for {why}). Install it with:  pip install {pip}")
        if known and "files_read" in ids and not self._doctor_package("pypdf", "pypdf"):
            row("NOTE", "Package pypdf", "not installed, so PDFs can't be read (other files can). Install it with:  pip install pypdf")
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
            allowed = False
            if path and os.path.exists(path):
                try:
                    with open(path, encoding="utf-8") as f:
                        allowed = json.load(f).get("sha256") == digest
                except (OSError, ValueError, AttributeError):
                    pass
            skip = os.environ.get("RB_APPROVE", "").strip().lower() in ("no", "0", "false", "off")
            row("ok" if allowed or skip else "NOTE", "First run", "approve = no, so it doesn't ask" if skip else
                "allowed on this computer" if allowed else "not allowed on this computer yet. Run it once yourself and answer y "
                "(a scheduled run won't start until then).")
        if os.environ.get("RB_SAVE_LOG", "").strip().lower() in ("1", "yes", "true", "on"):
            folder = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0] or ".")), LOG_DIR)
            ok = os.access(folder if os.path.isdir(folder) else os.path.dirname(folder), os.W_OK)
            row("ok" if ok else "FAIL", "Run logs", ("saved in " if ok else "can't be saved in ") + folder)
        for server in self.__dict__.get("_mcp_servers", {}).values():
            if hasattr(server, "close"):
                server.close()
        self.log = quiet
        fails, notes = rows.count("FAIL"), rows.count("NOTE")
        print()
        if fails:
            print(f"{fails} problem{'s' if fails != 1 else ''} to fix: the line{'s' if fails != 1 else ''} marked FAIL. Then run --doctor again.")
        else:
            print("Everything checked is ready." + (f" {notes} note{'s' if notes != 1 else ''} above." if notes else ""))
        return 1 if fails else 0

    @staticmethod
    def _doctor_configured(area):
        """For a program exported before CAN: is this connection set up at all?"""
        need = {"Home Assistant": "HA_TOKEN", "Homey": "HOMEY_API_KEY", "MQTT": "MQTT_HOST", "Telegram": "TELEGRAM_BOT_TOKEN",
                "Discord": "DISCORD_BOT_TOKEN", "Slack": "SLACK_BOT_TOKEN", "Email (reading)": "EMAIL_ADDRESS", "GitHub": "GITHUB_TOKEN",
                "Calendar": "CALENDAR_URL", "News feeds": "RB_FEEDS", "Web requests": "WEBHOOK_SECRET"}.get(area)
        return bool(need and os.environ.get(need))
