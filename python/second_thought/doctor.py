"""--doctor: checks a program's setup without spending anything or acting on anything.

Part of the second_thought package. tools/sync.py joins these files, in order, into
python/runtime.py, which is what ships inside every exported program and the page.
"""
import asyncio
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from .settings import (INI_NAMES, KEY_SOURCES, KEYCHAIN_NAMES, KEYCHAIN_PROBLEM, OTHER_SETTING_PREFIXES, OTHER_SETTINGS, RUNTIME_VERSION,
                       SETTING_NAMES, SETTINGS_PATH, SETTINGS_PATHS, SKIPPED_SETTINGS, WHERE_KEYS)
from .providers import CURRENCY, MODELS, dollars, record_limits, PROVIDERS, SERVICES, TIER_NAMES, _tier, amount_text, band_text, model_byline, fixed_rate, per_dollar, rate_note, rates
from .spending import PLANS, plan_of, reported_lines
from .core import CAPABILITIES, LOG_DIR, MEMORY_FILE, OUTPUT_DIR, RunError, SAFETY, _short, num, to_str
from .connectors import webhook_host
from .mcp import FR24_COMMANDS, KRAKEN_COMMANDS, mcp_env_name, mcp_is_fr24, mcp_is_twak, mcp_is_vaillant
from .settings import tr  # noqa: F401
# ---- package only: tools/sync.py leaves everything above this line out of python/runtime.py ----
import difflib  # noqa: E402,F811 - below the line, so python/runtime.py has it too
import re  # noqa: E402,F811


# The line the page puts after the program, above its blocks. Written in two parts, like PROGRAM_MARKS in update.py
# (which this can't import: it joins after this file): the runtime goes inside every program, and the page finds the
# line anywhere in the file, so the runtime must not contain it as it's written.
PROGRAM_MARKS = tuple("# ---- " + who + " program: lets the block editor import this file again ----"
                      for who in ("Second Thought", "Reflection Blocks"))


def _grammar_problems(data):
    """Where a block file breaks the format in docs/program-format.md: a list, empty when it matches.

    Checks only the shape the format promises, not what each block type means, and ignores keys it doesn't
    know, so a program saved by a newer page still passes and still opens.
    """
    problems = []

    def wrong(path, text):
        problems.append(f"{path} {text}")

    def scalar(v):
        return v is None or isinstance(v, (str, int, float, bool)) \
            or (isinstance(v, dict) and isinstance(v.get("id"), str) and v["id"].strip())

    def connection(v, path):
        if not isinstance(v, dict) or not any(k in v for k in ("block", "shadow")):
            return wrong(path, "isn't a block connection (a block, a shadow, or both)")
        for k in ("block", "shadow"):
            if k in v:
                block(v[k], f"{path}.{k}")

    def block(b, path):
        if not isinstance(b, dict) or not isinstance(b.get("type"), str) or not b["type"].strip():
            return wrong(path, "isn't a block with a type")
        fields = b.get("fields", {})
        if not isinstance(fields, dict) or any(not scalar(v) for v in fields.values()):
            wrong(f"{path} ({b['type']})", "has fields that aren't plain values")
        inputs = b.get("inputs", {})
        if not isinstance(inputs, dict):
            wrong(f"{path} ({b['type']})", "has inputs that aren't an object")
        else:
            for name, v in inputs.items():
                connection(v, f"{path} ({b['type']}) input {name}")
        if "next" in b:
            connection(b["next"], f"{path} ({b['type']}) next")
        for k in ("x", "y"):
            if k in b and not isinstance(b[k], (int, float)):
                wrong(f"{path} ({b['type']})", f"has {k} that isn't a number")

    if not isinstance(data, dict):
        return ["the top level isn't an object"]
    if data.get("format") != "reflection-blocks":
        wrong("the top level", 'isn\'t format "reflection-blocks"')
    if data.get("version") != 1:
        wrong("the top level", "isn't version 1")
    if not isinstance(data.get("name", ""), str) or not data.get("name", "").strip():
        wrong("the top level", "has no name")
    program = data.get("program")
    if not isinstance(program, dict) or not isinstance(program.get("blocks"), dict) \
            or not isinstance(program["blocks"].get("blocks"), list):
        return problems + ["the program part isn't a block tree"]
    if "languageVersion" in program["blocks"] and not isinstance(program["blocks"]["languageVersion"], int):
        wrong("the program part", "has a languageVersion that isn't a number")
    for i, b in enumerate(program["blocks"]["blocks"]):
        block(b, f"block {i + 1}")
    tests = data.get("tests")
    if tests is not None and (not isinstance(tests, list) or any(not isinstance(t, dict) or not isinstance(t.get("name"), str)
                                                                or not t.get("name", "").strip() for t in tests)):
        wrong("the top level", "has tests that aren't a list of named cases")
    return problems


import importlib.metadata  # noqa: E402,F811 - below the line, so python/runtime.py has them too
import importlib.util  # noqa: E402,F811
import shutil  # noqa: E402,F811
import hashlib  # noqa: E402,F811
import urllib.parse  # noqa: E402,F811
import socket  # noqa: E402,F811


class Doctor:
    """python my-program.py --doctor. Part of Runtime.

    Checks only what the program uses (from CAN), reading only: model keys with each service's free list of models,
    connections by reading from them, MCP servers by listing their tools. Nothing is sent, posted, switched or charged.
    """
    DOCTOR_TIMEOUT = 20

    @staticmethod
    def _doctor_get(url, headers, timeout, service=None):
        """(status, parsed JSON or None, error text). Status 0 means it couldn't be reached. With a service, keeps any
        rate limits its reply reports (#270): some services send them even on the free list of models."""
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
                if service:
                    record_limits(service, "", r.headers)
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
        status, body, err = await asyncio.to_thread(self._doctor_get, url, headers, self.DOCTOR_TIMEOUT, s["name"])
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

    async def _doctor_mikrotik(self):
        """The MikroTik check (#360): reachable, the certificate pinned, and an account that can only read."""
        base = os.environ.get("MIKROTIK_URL", "").strip()
        pinned = os.environ.get("MIKROTIK_CERT_SHA256", "").strip()
        if base and not base.lower().startswith("http://") and not pinned:
            seen = await asyncio.to_thread(self._mt_fingerprint, base)
            if seen:
                raise RunError(tr("the router's certificate is its own, so pin it: if {url} is your {who}, put {setting} = {seen} in second-thought.ini.", url=base, who="MikroTik", setting="MIKROTIK_CERT_SHA256", seen=seen))
        res = await self.mikrotik_health()
        user = os.environ.get("MIKROTIK_USER", "").strip()
        group = next((to_str(u.get("group")) for u in await self._mikrotik("GET", "/rest/user") if isinstance(u, dict) and u.get("name") == user), "")
        policy = next((to_str(g.get("policy")) for g in await self._mikrotik("GET", "/rest/user/group") if isinstance(g, dict) and g.get("name") == group), "")
        extra = sorted({p for p in policy.split(",") if p and not p.startswith("!")} - {"read", "api", "rest-api"})
        said = tr("{board}, RouterOS {version}", board=res.get("board") or "MikroTik", version=res.get("version") or "?")
        if base.lower().startswith("http://"):
            return "NOTE", said + "; " + tr("the password goes unencrypted over http://. Use the www-ssl service and https:// instead.")
        if extra:
            return "NOTE", said + "; " + tr("the account's group ({group}) can also {what}. Second Thought only reads, so a group with just read, api and rest-api is safer.", group=group, what=", ".join(extra))
        return said

    @staticmethod
    def _mt_fingerprint(base):
        """The SHA-256 fingerprint of the certificate the router shows, if it isn't one this computer trusts already."""
        import socket
        import ssl
        u = urllib.parse.urlparse(base if "://" in base else "https://" + base)
        try:
            with socket.create_connection((u.hostname, u.port or 443), timeout=10) as s:
                with ssl.create_default_context().wrap_socket(s, server_hostname=u.hostname):
                    return None  # trusted as it is
        except ssl.SSLCertVerificationError:
            pass
        except OSError:
            return None  # can't reach it: the request after says so
        ctx = ssl.create_default_context()
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
        with socket.create_connection((u.hostname, u.port or 443), timeout=10) as s:
            with ctx.wrap_socket(s) as t:
                return hashlib.sha256(t.getpeercert(binary_form=True)).hexdigest()

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
        if has("coinbase_read", "coinbase_trade"):
            async def coinbase():
                perms = await self._coinbase("GET", "/api/v3/brokerage/key_permissions")
                await self._coinbase("GET", "/api/v3/brokerage/accounts", {"limit": "1"})
                if perms.get("can_transfer"):
                    return "NOTE", tr("the key works, but it can also transfer money. This program never transfers: make a key without Transfer permission.")
                if "coinbase_trade" in can and not perms.get("can_trade"):
                    raise RunError(tr("the key works, but it's View only, so this program's orders would be refused. Make a key with Trade permission, limited to one portfolio."))
                if "coinbase_trade" not in can and perms.get("can_trade"):
                    return "NOTE", tr("the key works and can trade, but this program only reads: a View-only key is safer.")
                return tr("the key works: it can trade (every order asks you first)") if perms.get("can_trade") else tr("the key works, View only")
            out.append(("Coinbase", coinbase))
        if has("mikrotik_read"):
            async def mikrotik():
                return await self._doctor_mikrotik()
            out.append(("MikroTik", mikrotik))
        if has("solax_read"):
            async def solax():
                got = await self.solax_now()  # one call: the figures are cached for five minutes after it
                return tr("reached SolaxCloud: {status}, figures from {time}", status=got.get("status") or "?", time=got.get("upload_time") or "?")
            out.append(("Solax", solax))
        if has("powerwall_read", "powerwall_control"):
            async def powerwall():
                base = os.environ.get("POWERWALL_URL", "").strip()
                if base and not base.lower().startswith("http://") and not os.environ.get("POWERWALL_CERT_SHA256", "").strip():
                    seen = await asyncio.to_thread(self._mt_fingerprint, base)
                    if seen:
                        raise RunError(tr("the router's certificate is its own, so pin it: if {url} is your {who}, put {setting} = {seen} in second-thought.ini.", url=base, who="Powerwall gateway", setting="POWERWALL_CERT_SHA256", seen=seen))
                got = await self.powerwall_now()
                return tr("battery at {pct}%, reserve {reserve}%, grid {grid}", pct=got.get("battery_soc_pct") or "?",
                          reserve=got.get("reserve_pct") or "?", grid=got.get("grid") or "?")
            out.append(("Powerwall", powerwall))
        if has("unifi_read"):
            async def unifi():
                base = os.environ.get("UNIFI_URL", "").strip()
                if base and not os.environ.get("UNIFI_CERT_SHA256", "").strip():
                    seen = await asyncio.to_thread(self._mt_fingerprint, base)
                    if seen:
                        raise RunError(tr("the router's certificate is its own, so pin it: if {url} is your {who}, put {setting} = {seen} in second-thought.ini.", url=base, who="UniFi console", setting="UNIFI_CERT_SHA256", seen=seen))
                info = await self._unifi("/info")
                site = await self._unifi_site()
                devices = await self._unifi_all(f"/sites/{site}/devices")
                return tr("UniFi Network {version}, {n} devices", version=to_str(info.get("applicationVersion")) or "?", n=len(devices))
            out.append(("UniFi", unifi))
        if has("proxmox_read", "proxmox_control"):
            async def proxmox():
                base = os.environ.get("PROXMOX_URL", "").strip()
                if base and not os.environ.get("PROXMOX_CERT_SHA256", "").strip():
                    seen = await asyncio.to_thread(self._mt_fingerprint, base if "://" in base else "https://" + base)
                    if seen:
                        raise RunError(tr("the router's certificate is its own, so pin it: if {url} is your {who}, put {setting} = {seen} in second-thought.ini.", url=base, who="Proxmox", setting="PROXMOX_CERT_SHA256", seen=seen))
                version = to_str((await self._proxmox("GET", "/api2/json/version") or {}).get("version"))
                privs = {p for v in (await self._proxmox("GET", "/api2/json/access/permissions") or {}).values() if isinstance(v, dict) for p, on in v.items() if on}
                said = tr("Proxmox VE {version}", version=version or "?")
                if "proxmox_control" in can and "VM.PowerMgmt" not in privs:
                    raise RunError(said + "; " + tr("the token can't start or stop guests (it needs VM.PowerMgmt), so this program's power blocks would be refused."))
                more = sorted(p for p in privs if not p.endswith(".Audit") and p != "VM.PowerMgmt") + (["VM.PowerMgmt"] if "proxmox_control" not in can and "VM.PowerMgmt" in privs else [])
                if more:
                    return "NOTE", said + "; " + tr("the token can also {what}. Second Thought doesn't need that: the PVEAuditor role is safer.", what=", ".join(more[:6]))
                return said
            out.append(("Proxmox", proxmox))
        if has("docker_read", "docker_control"):
            async def docker():
                version = to_str((await self._docker("GET", "/version")).get("Version"))
                n = len(await self._docker("GET", "/containers/json", {"all": "1"}))
                return tr("Docker {version}", version=version or "?") + ", " + tr("{n} containers", n=n)
            out.append(("Docker", docker))
        if has("sabnzbd_read", "sabnzbd_control"):
            async def sabnzbd():
                q = (await self._sabnzbd("queue")).get("queue") or {}
                return tr("SABnzbd {version}", version=to_str(q.get("version")) or "?") + ", " + tr("{n} in the queue", n=len(q.get("slots") or []))
            out.append(("SABnzbd", sabnzbd))
        if has("arr_read", "arr_control"):
            async def arr(which):
                status = await self._arr(which, "GET", "/api/v3/system/status")
                q = await self._arr(which, "GET", "/api/v3/queue", {"page": "1", "pageSize": "1"})
                return tr("{who} {version}", who=which.capitalize(), version=to_str(status.get("version")) or "?") \
                    + ", " + tr("{n} in the queue", n=num(q.get("totalRecords") or 0))
            out.append(("Radarr", lambda: arr("radarr")))
            out.append(("Sonarr", lambda: arr("sonarr")))
        if has("unraid_read", "unraid_control"):
            async def unraid():
                d = await self._unraid("query{vars{version}array{state}}")
                return tr("Unraid {version}", version=to_str((d.get("vars") or {}).get("version")) or "?") \
                    + ", " + tr("array {state}", state=to_str((d.get("array") or {}).get("state")) or "?")
            out.append(("Unraid", unraid))
        if has("nzbgeek_read", "nzbgeek_fetch"):
            async def nzbgeek():
                raw = await self._nzbgeek({"t": "caps", "o": "json"})
                caps = (json.loads(raw) if raw.strip() else {}).get("caps") or {}
                server = (caps.get("server") or {}).get("@attributes") or {}
                ret = caps.get("retention")
                days = num((ret or {}).get("@attributes", {}).get("days")) if isinstance(ret, dict) else num(ret)
                return tr("NZBGeek {version}", version=to_str(server.get("version")) or "?") \
                    + ", " + tr("{n} days of retention", n=days or "?")
            out.append(("NZBGeek", nzbgeek))
        if has("pihole_read", "pihole_control"):
            async def pihole():
                s = await self._pihole("GET", "/api/stats/summary")
                q = (s.get("queries") or {})
                return tr("{n} queries, {blocked} blocked", n=num(q.get("total")), blocked=num(q.get("blocked")))
            out.append(("Pi-hole", pihole))
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
                key = mcp_env_name(name)
                command = os.environ.get(key, "").strip() or self.__dict__.get("_mcp_defaults", {}).get(key, "")
                if re.search(r"(^|\s)--allow-dangerous\b", command):
                    raise RunError(tr("{key} starts the server with --allow-dangerous, which turns off its own check before tools that move money. Take it out.", key=key))
                if re.match(r"^\s*kraken(\.exe)?\s", command) and not shutil.which("kraken"):
                    raise RunError(tr("kraken-cli isn't installed, so Kraken's tools can't start. Install it: https://docs.kraken.com/home/mcp"))
                fr24 = mcp_is_fr24(name, command)
                vaillant = mcp_is_vaillant(name, command)
                if fr24 and not shutil.which("npx"):
                    raise RunError(tr("Node.js isn't installed, so Flightradar24's tools can't start (they come from npx). Install it: https://nodejs.org"))
                if fr24 and not os.environ.get("FR24_API_KEY", "").strip():
                    raise RunError(tr("Flightradar24 needs a key: set FR24_API_KEY in second-thought.ini, next to this program (a paid subscription, from https://fr24api.flightradar24.com)"))
                tools = await self.mcp_tools(name)
                text = tr("{tools} tools, MCP {version}", tools=len(tools), version=self._mcp(name).version)
                twak = mcp_is_twak(name, command)  # its tools carry no marks, so its own safe list says which only look (#320)
                changes = sum(1 for t in tools if not (isinstance(t.get("annotations"), dict) and t["annotations"].get("readOnlyHint") is True)
                              and not (twak and t.get("name") in SAFETY["mcp_twak_safe"])
                              and not (fr24 and t.get("name") in SAFETY["mcp_fr24_safe"])
                              and not (vaillant and t.get("name") in SAFETY["mcp_vaillant_safe"]))
                if changes:  # worth knowing: GitHub's server, say, started without --read-only (#333)
                    text += " · " + tr("{n} of them can change things", n=changes)
                names = {to_str(t.get("name")) for t in tools}
                if key == "MCP_KRAKEN" and os.environ.get("KRAKEN_API_KEY") and names & {"kraken_auth_test", "kraken_balance"}:
                    # The key, checked with a read-only call; what it reads isn't shown.
                    reply, failed = await self.mcp_call(name, "kraken_auth_test" if "kraken_auth_test" in names else "kraken_balance", {})
                    if failed:
                        raise RunError(tr("Kraken refused KRAKEN_API_KEY: {problem}", problem=_short(reply, 160)))
                    text += " · " + tr("your Kraken key works")
                if fr24:  # each call costs credits, so the key is only checked for being there, not by spending one
                    text += " · " + tr("your FR24_API_KEY is set (each call costs credits, so it isn't checked here)")
                return text
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

    @staticmethod
    def known_setting(key):
        """Whether the runtime reads this setting (#307): one of its own, a model service's, or a model, MCP server or plan."""
        services = {n for s in SERVICES for n in (*s["keys"], s.get("base_env"), (s.get("vision") or [None])[0]) if n}
        return (key in SETTING_NAMES.values() or key in KEYCHAIN_NAMES or key in OTHER_SETTINGS or key in services
                or key.startswith(OTHER_SETTING_PREFIXES))

    def settings_notes(self):
        """What --doctor notes about the settings files (#307): one others can read, names it skipped, and names it
        doesn't know, which are usually spelling mistakes."""
        notes, where = [], lambda w: w[3:] if w.startswith("st:") else SETTINGS_PATHS[0] if w == "home" else SETTINGS_PATH
        if os.name == "posix":
            for path in SETTINGS_PATHS:
                try:
                    if os.stat(path).st_mode & 0o077:
                        notes.append(tr("{path} can be read by other people on this computer. To keep its keys to you:  chmod 600 {path}", path=path))
                except OSError:
                    pass
        if SKIPPED_SETTINGS:
            notes.append(tr("skipped {names}: settings never change LD_, DYLD_ or PYTHON names, which change how programs start",
                            names=", ".join(f"{n} ({where(w)})" for n, w in SKIPPED_SETTINGS)))
        unknown = [(n, w) for k, n, w in INI_NAMES if not self.known_setting(k)]
        if unknown:
            notes.append(tr("{names} isn't a setting Second Thought uses, so check the spelling. If an MCP server or a command "
                            "you run needs it, that's fine.", names=", ".join(f"{n} ({where(w)})" for n, w in unknown)))
        return notes

    @staticmethod
    def _doctor_program():
        """The block file embedded in this program, checked against the format in docs/program-format.md (#391).
        It's what lets the page import this program again, so a broken one is worth knowing about before a run."""
        try:
            with open(os.path.abspath(sys.argv[0] or ""), encoding="utf-8") as f:
                text = f.read()
        except OSError:
            return "NOTE", tr("this file's own text couldn't be read, so its block file wasn't checked")
        at = next((i for i in (text.find(m) for m in PROGRAM_MARKS) if i >= 0), -1)
        payload, on = [], False
        for line in (text[at:].splitlines() if at >= 0 else []):
            if not on:
                if re.fullmatch(r"#\s*BLOCKS:\s*", line):
                    on = True
                continue
            m = re.fullmatch(r"#\s*([A-Za-z0-9+/=]+)\s*", line)
            if m:
                payload.append(m.group(1))
        if not payload:
            return "NOTE", tr("no block file embedded, so the page can't import this program again (it was exported by an older page)")
        try:
            data = json.loads(base64.b64decode("".join(payload)))
        except ValueError:
            return "FAIL", tr("the block file embedded in this program isn't readable, so the page can't import it again")
        problems = _grammar_problems(data)
        if problems:
            return "FAIL", tr("the block file embedded in this program breaks the format ({problem}), so the page may not "
                              "import it again", problem=_short(problems[0], 160))
        return "ok", tr("the block file inside this program matches the format, so the page can import it again")

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
        status, text = self._doctor_program()
        row(status, "Program", text)
        if CURRENCY != "usd":
            r = rates()
            row("NOTE" if r["problem"] and not fixed_rate() else "ok", "Currency",
                tr("{code}, {note} (1 US dollar = {rate})", code=CURRENCY.upper(), note=rate_note(), rate=amount_text(per_dollar(CURRENCY), CURRENCY))
                + ("" if fixed_rate() or not r["problem"] else " " + tr("Today's rate couldn't be fetched ({err}), so it uses the last one it has.", err=r["problem"])))
        update = self.update_status()
        if update:
            row(update[0], "Runtime", update[1])
        row("ok" if SETTINGS_PATH else "NOTE", "Settings", tr("read {settings_path}", settings_path=" + ".join(SETTINGS_PATHS)) if SETTINGS_PATH else
            tr("no second-thought.ini found next to the program, in this folder or in your home folder, so only environment variables are used"))
        for text in self.settings_notes():
            row("NOTE", "Settings", text)
        found = [(k, KEY_SOURCES.get(k)) for k in KEYCHAIN_NAMES if os.environ.get(k)]
        where = {"environment": tr("the environment"), "file": "second-thought.ini", "keychain": tr("the keychain")}
        if found:
            # an ST_ variable by its name, the home folder's file by its path (#340)
            label = lambda src: src[3:] if (src or "").startswith("st:") else SETTINGS_PATHS[0] if src == "home" else where.get(src) or where["environment"]  # noqa: E731
            row("ok", "Keys", ", ".join(f"{k} ({label(src)})" for k, src in found))
        if KEYCHAIN_PROBLEM:
            row("NOTE", "Keychain", tr("keyring is installed but the keychain couldn't be read ({problem}), so keys only come from the "
                                      "environment and second-thought.ini", problem=_short(KEYCHAIN_PROBLEM, 120)))
        row("ok", "MCP tool", tr("with --mcp, it serves one tool, “{name}”, to Claude and other agents", name=self.mcp_tool_name()))
        names = list(can.get("services", [])) if known else ["Claude"] + [s["name"] for s in SERVICES
                                                                          if s["name"] != "Claude" and any(os.environ.get(k) for k in s["keys"])]
        services = [s for s in SERVICES if s["name"] in names]
        for s in services:
            for line in self.allowance_lines([_tier(s, "default")]):
                row("ok", "Allowances", line)
            plan = plan_of(s["name"])
            if plan:
                p = PLANS[s["name"]]
                cap = p["plans"][plan]
                row("ok", "Plan", tr("{service} {plan} plan: {cap} (published {date}).", service=s["name"], plan=plan.title(), date=p["checked"],
                                     cap=tr("monthly cap {amount}", amount=dollars(cap)) if cap else tr("no monthly cap published")))
        if self.allowance_note() and services:
            row("NOTE", "Allowances", self.allowance_note())
        needs = [("anthropic", "anthropic", "Claude")] if any(s["api"] == "anthropic" for s in services) else []
        needs += [("google.genai", "google-genai", "Gemini")] if any(s["api"] == "gemini" for s in services) else []
        needs += [("paho.mqtt.client", "paho-mqtt", "MQTT")] if known and any(i in ids for i in ("mqtt_read", "mqtt_publish")) else []
        needs += [("cryptography", "cryptography", "Coinbase")] if known and any(i in ids for i in ("coinbase_read", "coinbase_trade")) else []
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
            sizes = [k for k in TIER_NAMES if k in s["tiers"] and (k == "default" or s["tiers"][k][0] != s["tiers"]["default"][0])]
            row(status, s["name"], text + " " + tr("Models: {list}.", list=", ".join(f"{model_byline(_tier(s, k))} ({band_text(_tier(s, k))})" for k in sizes)))
        for line in reported_lines([s["name"] for s in services]):
            row("ok", "Limits", line)
        servers = [n for n in can.get("mcp", []) if to_str(n).strip()]
        if can.get("kraken"):  # the Kraken tools block: its own command, unless MCP_KRAKEN says otherwise
            self.__dict__.setdefault("_mcp_defaults", {})["MCP_KRAKEN"] = KRAKEN_COMMANDS.get(can["kraken"], KRAKEN_COMMANDS["read"])
            servers.append("kraken")
        if can.get("flightradar24"):  # the Flightradar24 tools block: its own command, unless MCP_FLIGHTRADAR24 says otherwise (#364)
            self.__dict__.setdefault("_mcp_defaults", {})["MCP_FLIGHTRADAR24"] = FR24_COMMANDS["read"]
            servers.append("flightradar24")
        for area, check in await self._doctor_connections(ids, servers):
            if not known and not self._doctor_configured(area):
                continue
            try:
                got = await check()  # a few checks give (status, detail): a NOTE, say
                status, text = got if isinstance(got, tuple) else ("ok", got)
                row(status, area, text)
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
                "Calendar": "CALENDAR_URL", "News feeds": "RB_FEEDS", "Web requests": "WEBHOOK_SECRET", "Coinbase": "COINBASE_KEY_FILE COINBASE_KEY", "MikroTik": "MIKROTIK_URL", "UniFi": "UNIFI_URL", "Proxmox": "PROXMOX_URL", "Docker": "DOCKER_HOST", "SABnzbd": "SABNZBD_URL", "Radarr": "RADARR_URL", "Sonarr": "SONARR_URL", "Unraid": "UNRAID_URL", "NZBGeek": "NZBGEEK_API_KEY", "Pi-hole": "PIHOLE_URL PIHOLE_PASSWORD", "Solax": "SOLAX_TOKEN_ID", "Powerwall": "POWERWALL_URL"}.get(area)
        return bool(need and any(os.environ.get(n) for n in need.split()))
