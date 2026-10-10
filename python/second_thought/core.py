"""Limits, errors, and the value helpers that mirror the block editor exactly.

Part of the second_thought package. tools/sync.py joins these files, in order, into
python/runtime.py, which is what ships inside every exported program and the page.
"""
import asyncio
import base64
import contextlib
import contextvars
import datetime
import hashlib
import json
import math
import os
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from .settings import SETTING_NAMES, WHERE_KEYS
# ---- package only: tools/sync.py leaves everything above this line out of python/runtime.py ----


MAX_TOKENS = 4096


def _number_setting(name, default, what, whole=False):
    """A number from the settings (second-thought.ini or the environment). A mistake stops the program and says
    which setting is wrong, as a mistake anywhere else in second-thought.ini does, rather than being ignored."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    friendly = next((k for k, v in SETTING_NAMES.items() if v == name), name)
    try:
        n = float(raw)
        if not math.isfinite(n) or n < 0 or (whole and not n.is_integer()):
            raise ValueError
    except ValueError:
        sys.exit(f"{friendly} must be {what}, not “{raw}”. Fix it {WHERE_KEYS}"
                 + (f" (or the {name} environment variable)." if friendly != name else ".") + " 0 means no limit.")
    return int(n) if whole else n


# 0 means no limit for all three (call_timeout used to mean 300 at 0; now 0 is no timeout, like the others).
CALL_TIMEOUT = _number_setting("RB_CALL_TIMEOUT", 300, "a number of seconds, like 120") or None  # one model call gives up after this long
MAX_SECONDS = _number_setting("RB_MAX_SECONDS", 0, "a number of seconds, like 900")             # any run stops after this long
BUDGET = _number_setting("RB_BUDGET", 0, "a whole number of tokens, like 50000", whole=True)      # tokens per run
MAX_AI_CALLS = 60       # per run, to protect your usage
MAX_STEPS = 20000       # stops loops that never end
MAX_SCRIPTS = 100       # scripts started by broadcasts in one run
MAX_DEPTH = 60          # My Blocks calling themselves
OUTPUT_DIR = "outputs"  # where pictures are saved
LOG_DIR = "logs"        # where run logs go when save_log = yes in second-thought.ini
# 'forever' and timed memories live in this file, next to the program.
MEMORY_FILE = os.environ.get("RB_MEMORY_FILE") or os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "memory.json")


# Home Assistant: the address of your Home Assistant and a long-lived access token
# (your Home Assistant profile, Security tab, "Long-lived access tokens").
HA_URL = os.environ.get("HA_URL", "http://homeassistant.local:8123").rstrip("/")
HA_TOKEN = os.environ.get("HA_TOKEN", "")
HA_TTS_ENTITY = os.environ.get("HA_TTS_ENTITY", "tts.home_assistant_cloud")  # used by the 'say … on' block
HA_WATCH_SECONDS = 15  # how often 'when … changes' scripts check Home Assistant
HA_SENSITIVE = (r"^lock\.(unlock|open)$", r"^cover\.open", r"^alarm_control_panel\.alarm_disarm$", r"^valve\.open", r"^garage_door\.open")

# Connections. Each one is only needed if your program uses it; put the keys in second-thought.ini.
# GitHub: a token from https://github.com/settings/tokens (read access to your repositories is enough to look;
# to comment on pull requests it also needs pull request write access).
GITHUB_API = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
# Telegram: make a bot by talking to @BotFather in Telegram; it gives you the token. TELEGRAM_CHAT_ID is your own chat
# with the bot: the bot only listens to, and searches, the chats listed there (anyone can message a bot).
TELEGRAM_API = os.environ.get("TELEGRAM_API_URL", "https://api.telegram.org").rstrip("/")
TELEGRAM_FILE = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "telegram-messages.json")
# The last text of each page a 'when the web page … changes' block watches, so a restart doesn't count every page as changed.
PAGES_FILE = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "watched-pages.json")
# Discord: a bot token (Discord Developer Portal, your application, Bot, Reset Token) with the Message Content intent
# turned on, and DISCORD_CHANNEL_ID: the channels it reads and posts in (anyone in a server can post, so only these count).
# Slack: a bot token (api.slack.com/apps, your app, OAuth & Permissions; scopes channels:history, groups:history,
# chat:write) and SLACK_CHANNEL_ID, the channels it reads and posts in. Invite the bot to each channel.
DISCORD_API = os.environ.get("DISCORD_API_URL", "https://discord.com/api/v10").rstrip("/")
SLACK_API = os.environ.get("SLACK_API_URL", "https://slack.com/api").rstrip("/")
# Email: your address and an app password (Gmail: Google account, Security, App passwords). The mail servers are
# worked out for Gmail, iCloud, Yahoo and Fastmail; for anything else set EMAIL_IMAP_HOST and EMAIL_SMTP_HOST.
# MQTT: MQTT_HOST is your broker (for example homeassistant.local, if it runs Mosquitto), with MQTT_USERNAME and
# MQTT_PASSWORD if it needs them. MQTT_TLS = yes for an encrypted connection (port 8883). Needs  pip install paho-mqtt.
# Web requests: WEBHOOK_SECRET is a password every request must carry (?key=... or an X-Second-Thought-Key header);
# WEBHOOK_PORT is the port to listen on (8765 if you don't say).
# Calendar: CALENDAR_URL is your calendar's private iCal address (Google Calendar: Settings, your calendar,
# "Secret address in iCal format"; Outlook: Settings, Calendar, Shared calendars, Publish; iCloud: share as public).
# Several addresses can be separated by spaces.

MESSAGE_VALUE = contextvars.ContextVar("message_value", default="")
MODEL_OVERRIDE = contextvars.ContextVar("model_override", default=None)  # set by 'with model' blocks
# Server-side web search for the 'search the web' block. Your API organisation must allow it.
WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 3}


class Reply(str):
    """A model's reply text that also says whether it was cut off by the length limit."""
    def __new__(cls, text, truncated=False):
        r = str.__new__(cls, text)
        r.truncated = bool(truncated)
        return r


CONTINUE_PROMPT = "Continue exactly where you stopped. Don't repeat anything you've already written."


class Finish(Exception):
    """Raised by 'finish' and 'stop the run' blocks."""


class RunError(Exception):
    """A problem in the program itself."""


class Retryable(RunError):
    """A failure a second try could fix (a garbled or empty reply)."""


# ----- pictures -----

class BadJSON(Retryable):
    """The model's reply wasn't readable JSON."""


class Picture:
    """A picture: a file you chose, or an SVG illustration Claude drew."""
    _count = 0

    def __init__(self, data, media_type, name=None, svg=None):
        Picture._count += 1
        self.data, self.media_type, self.svg = data, media_type, svg
        self.name = name or f"picture-{Picture._count}"
        self.path = None

    def __str__(self):
        return f"[picture: {self.name}]"


_MEDIA = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif", ".svg": "image/svg+xml"}
_EXT = {v: k for k, v in _MEDIA.items() if k != ".jpeg"}


def clean_svg(text):
    m = re.search(r"<svg[\s\S]*</svg>", to_str(text), re.I)
    if not m:
        return None
    svg = m.group(0)
    svg = re.sub(r"<(script|foreignObject|iframe)\b[\s\S]*?</\1\s*>", "", svg, flags=re.I)
    svg = re.sub(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*')", "", svg, flags=re.I)
    svg = re.sub(r"\s(xlink:)?href\s*=\s*(\"(?!#|data:image/)[^\"]*\"|'(?!#|data:image/)[^']*')", "", svg, flags=re.I)
    if "xmlns=" not in svg[:300]:
        svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    return svg


def _need_picture(v, where):
    if not isinstance(v, Picture):
        raise RunError(f"The '{where}' block needs a picture in its picture slot.")
    return v


# ----- value helpers (they mirror the block editor exactly) -----

def _clean_num(n):
    if isinstance(n, float) and n.is_integer() and abs(n) < 1e15:
        return int(n)
    return n


def num(v):
    if isinstance(v, bool):
        return 1 if v else 0
    if isinstance(v, (int, float)):
        return v
    try:
        s = str(v).strip()
        return _clean_num(float(s)) if s else 0
    except (TypeError, ValueError):
        return 0


def to_str(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, list):
        return "\n".join(to_str(x) for x in v)
    if isinstance(v, dict):
        return "\n".join(f"{k}: " + (", ".join(to_str(x) for x in val) if isinstance(val, list) else to_str(val)) for k, val in v.items())
    if isinstance(v, float):
        return str(_clean_num(v))
    return str(v)  # Picture.__str__ gives "[picture: name]"


def to_bool(v):
    if isinstance(v, str):
        return not (v == "" or v.lower() == "false" or v == "0")
    if isinstance(v, list):
        return True
    return bool(v)


# A list item's marker: "- " or "* ", "•", or a number with . or ) after it ("1.", "3)", "(2)"). Only those, so
# "10 green bottles", "2024 plan", "1.5 kg flour" and "-5 °C" keep their numbers. The page's list() is the same.
_BULLET = re.compile(r"^\s*(?:[-*](?=\s)|•|\(?\d+[.)](?!\d))\s*")


def to_list(v):
    if isinstance(v, list):
        return v
    if v is None or v == "":
        return []
    out = []
    for line in re.split(r"\n+", to_str(v)):
        item = _BULLET.sub("", line).strip()
        if item:
            out.append(item)
    return out


def _num_like(v):
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return True
    if isinstance(v, str) and v.strip():
        try:
            float(v)
            return True
        except ValueError:
            return False
    return False


def compare(a, op, b):
    if _num_like(a) and _num_like(b):
        x, y = num(a), num(b)
    else:
        x, y = to_str(a).lower(), to_str(b).lower()
    return {"EQ": x == y, "NEQ": x != y, "LT": x < y, "LTE": x <= y, "GT": x > y, "GTE": x >= y}[op]


def arith(a, op, b):
    a, b = num(a), num(b)
    if op == "ADD":
        r = a + b
    elif op == "MINUS":
        r = a - b
    elif op == "MULTIPLY":
        r = a * b
    elif op == "DIVIDE":
        if b == 0:
            raise RunError("Can't divide by zero.")
        r = a / b
    else:
        r = math.pow(a, b)
    return _clean_num(r)


def random_int(a, b):
    a, b = round_js(num(a)), round_js(num(b))
    if a > b:
        a, b = b, a
    return random.randint(a, b)


def round_js(n):
    return int(math.floor(n + 0.5))


def round_op(n, op):
    n = num(n)
    return {"ROUND": round_js(n), "ROUNDUP": int(math.ceil(n)), "ROUNDDOWN": int(math.floor(n))}[op]


def modulo(a, b):
    a, b = num(a), num(b)
    if b == 0:
        raise RunError("Can't divide by zero.")
    return _clean_num(math.fmod(a, b))


def join(*parts):
    return "".join(to_str(p) for p in parts)


def length(v):
    return len(v) if isinstance(v, list) else len(to_str(v))


def is_empty(v):
    return len(to_str(v)) == 0


def change_case(v, mode):
    t = to_str(v)
    if mode == "UPPERCASE":
        return t.upper()
    if mode == "LOWERCASE":
        return t.lower()
    return re.sub(r"\S+", lambda m: m.group(0)[0].upper() + m.group(0)[1:].lower(), t)


def contains(a, b):
    return to_str(b).lower() in to_str(a).lower()


def word_count(v):
    t = to_str(v).strip()
    return len(t.split()) if t else 0


def count(start, end, by):
    start, end, by = num(start), num(end), abs(num(by)) or 1
    if start > end:
        by = -by
    i = start
    while (i <= end) if by > 0 else (i >= end):
        yield _clean_num(i)
        i += by


def times(n):
    return range(max(0, int(math.floor(num(n)))))


def field_list(f):
    return [x.strip() for x in re.split(r"[,\n]+", to_str(f)) if x.strip()]


def to_record(o, fields=()):
    r = {}
    if isinstance(o, dict):
        for k, v in o.items():
            r[k] = json.dumps(v) if isinstance(v, dict) else v
    for f in fields:
        r.setdefault(f, "")
    return r


def rec_get(rec, key):
    if not isinstance(rec, dict):
        raise RunError(f"'{to_str(key)} of' needs a record in its second slot.")
    return rec.get(to_str(key).strip(), "")


def rec_set(rec, key, value):
    key = to_str(key).strip()
    if not key:
        raise RunError("The 'set … of record' block needs a field name.")
    if not isinstance(rec, dict):
        raise RunError(f"The 'set {key} of' block needs a record in its middle slot.")
    rec[key] = value


def rec_has(rec, key):
    return isinstance(rec, dict) and to_str(key).strip() in rec


def rec_keys(rec):
    return list(rec.keys()) if isinstance(rec, dict) else []


def sort_by(items, key, order):
    items, key = list(to_list(items)), to_str(key).strip()
    get = (lambda it: it.get(key, "") if isinstance(it, dict) else "") if key else (lambda it: it)
    nums = all(_num_like(get(it)) for it in items)
    items.sort(key=(lambda it: num(get(it))) if nums else (lambda it: to_str(get(it)).lower()), reverse=(order != "asc"))
    return items


def _parse_json(text):
    text = text.strip()
    try:
        return json.loads(text)
    except ValueError:
        pass
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except ValueError:
            pass
    starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
    end = max(text.rfind("}"), text.rfind("]"))
    if starts and end > min(starts):
        try:
            return json.loads(text[min(starts):end + 1])
        except ValueError:
            pass
    raise BadJSON("Claude's reply came back in an unreadable format. Run again.")


# ----- Structured replies -----
# Every block that wants JSON names the shape it expects. Claude is held to that shape while it writes (constrained
# decoding). Every other model is checked after it replies, and asked once to fix a reply that doesn't fit.
# The page keeps a copy of these shapes (SCHEMAS in second-thought.html); keep the two the same.
_ANY = {"anyOf": [{"type": "string"}, {"type": "number"}, {"type": "boolean"}]}


def _obj(props, required=()):
    return {"type": "object", "properties": props, "required": list(required), "additionalProperties": False}


SCHEMAS = {
    "yesno": _obj({"answer": {"type": "boolean"}}, ["answer"]),
    "number": _obj({"number": {"type": "number"}}, ["number"]),
    "list": _obj({"items": {"type": "array", "items": {"type": "string"}}}, ["items"]),
    "score": _obj({"score": {"type": "number"}}, ["score"]),
    "pick": _obj({"pick": {"type": "integer", "enum": [1, 2]}, "reason": {"type": "string"}}, ["pick"]),
    "review": _obj({"approved": {"type": "boolean"}, "problems": {"type": "array", "items": {"type": "string"}}}, ["approved"]),
    "agent": _obj({"tool": {"type": "string"}, "input": {"type": "object"}, "why": {"type": "string"},
                   "done": {"type": "boolean"}, "answer": {"type": "string"},
                   "plan": {"type": "array", "items": {"type": "string"}}}),
}


# ----- What a program can do -----
# Everything a program can do beyond asking its model services, in the order it's listed. The page reads this list too
# (tools/sync.py copies it in): it works out which of these a program uses from its blocks, shows them when you import a
# program, and writes them into the exported program, which lists them and asks before its first run if any of them
# acts on the world (the third value). Each is (id, what it lets the program do, whether that acts on the world).
CAPABILITIES = [
    ("email_send", "send email", True),
    ("telegram_send", "send Telegram messages", True),
    ("discord_send", "send Discord messages", True),
    ("slack_send", "send Slack messages", True),
    ("github_comment", "comment on GitHub", True),
    ("ha_act", "control your Home Assistant devices", True),
    ("homey_act", "control your Homey devices and start Homey flows", True),
    ("mqtt_publish", "publish MQTT messages", True),
    ("webhook", "accept web requests from other computers", True),
    ("mcp", "use the tools of the MCP servers you set up (they can do whatever those servers can)", True),
    ("web", "read public web pages and search the web", False),
    ("email_read", "read your email", False),
    ("calendar", "read your calendars", False),
    ("feeds", "read news feeds", False),
    ("github_read", "look at your GitHub projects", False),
    ("telegram_read", "read your Telegram messages", False),
    ("discord_read", "read your Discord channels", False),
    ("slack_read", "read your Slack channels", False),
    ("ha_read", "look at your Home Assistant devices", False),
    ("homey_read", "look at your Homey devices, flows and variables", False),
    ("mqtt_read", "read MQTT messages", False),
    ("folder", "watch a folder for new files", False),
    ("files_read", "read files you choose", False),
    ("files_save", "save files in its outputs folder", False),
    ("memory", "keep notes between runs, in memory.json", False),
]


def record_schema(fields, many=False):
    one = _obj({f: _ANY for f in fields})
    return _obj({"items": {"type": "array", "items": one}}, ["items"]) if many else one


def _shape_problem(v, schema, where="the reply"):
    """What's wrong with v for this schema, in a sentence, or None. Numbers written as text count as numbers."""
    if "anyOf" in schema:
        return None if any(_shape_problem(v, o, where) is None for o in schema["anyOf"]) else f"{where} has the wrong kind of value"
    t = schema.get("type")
    if t == "object":
        if not isinstance(v, dict):
            return f"{where} should be a JSON object"
        for k in schema.get("required", []):
            if k not in v:
                return f"{where} is missing \"{k}\""
        for k, sub_ in schema.get("properties", {}).items():
            if k in v:
                bad = _shape_problem(v[k], sub_, f"\"{k}\"")
                if bad:
                    return bad
        return None
    if t == "array":
        if not isinstance(v, list):
            return f"{where} should be a list"
        for i, x in enumerate(v):
            bad = _shape_problem(x, schema.get("items", {}), f"item {i + 1} of {where}")
            if bad:
                return bad
        return None
    if t == "boolean" and not isinstance(v, bool):
        return f"{where} should be true or false"
    if t in ("number", "integer") and (isinstance(v, bool) or not _num_like(v)):
        return f"{where} should be a number"
    if t == "string" and not isinstance(v, str):
        return f"{where} should be text"
    if "enum" in schema and (num(v) if t in ("number", "integer") else v) not in schema["enum"]:
        return f"{where} should be one of {', '.join(json.dumps(e) for e in schema['enum'])}"
    return None


def _fit(v, schema):
    """Small, safe fixes before checking: a bare list where {"items": [...]} is wanted, one record sent as a list of one."""
    props = schema.get("properties", {})
    if isinstance(v, list) and list(props) == ["items"]:
        return {"items": v}
    if isinstance(v, list) and len(v) == 1 and isinstance(v[0], dict) and schema.get("type") == "object":
        return v[0]
    return v


def _short(s, n):
    s = re.sub(r"\s+", " ", to_str(s)).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


# ----- Files that several programs can share (memory.json, the Telegram messages) -----
# Two programs can point at the same file (RB_MEMORY_FILE). Each change to one is a read, a change and a write, done
# while holding a lock on "<file>.lock", so two programs saving at once take turns instead of one losing the other's
# change. Writes go to a temporary file first, which then replaces the real one, so a crash mid-save can't leave half a file.
_FILE_LOCKS = {}                 # path -> [open lock file, how many times this program holds it]
_FILE_LOCKS_GUARD = threading.RLock()


@contextlib.contextmanager
def _locked(path):
    """Holds the lock for a shared file. This program can take it again while holding it (memory blocks nest)."""
    key = os.path.abspath(path)
    with _FILE_LOCKS_GUARD:
        held = _FILE_LOCKS.get(key)
        if held:
            held[1] += 1
        else:
            try:
                f = open(key + ".lock", "a+b")
            except OSError:  # a folder we can't write to: carry on without the lock rather than fail
                f = None
            if f is not None:
                if os.name == "nt":
                    import msvcrt
                    give_up = time.monotonic() + 120
                    while True:
                        try:
                            f.seek(0)
                            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)  # retries for 10 s, then raises
                            break
                        except OSError:
                            if time.monotonic() > give_up:
                                f.close()
                                raise RunError(f"Another program has been using {os.path.basename(key)} for over two minutes, so this one gave up waiting.")
                else:
                    import fcntl
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            held = _FILE_LOCKS[key] = [f, 1]
        try:
            yield
        finally:
            held[1] -= 1
            if not held[1]:
                del _FILE_LOCKS[key]
                f = held[0]
                if f is not None:
                    try:
                        if os.name == "nt":
                            import msvcrt
                            f.seek(0)
                            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                        else:
                            import fcntl
                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    finally:
                        f.close()


class _WebSocket:
    """Just enough of a WebSocket client (RFC 6455) for Home Assistant's API, using only the standard library."""

    def __init__(self, reader, writer):
        self.reader, self.writer = reader, writer

    @classmethod
    async def connect(cls, url, timeout=20):
        import ssl
        u = urllib.parse.urlparse(url)
        secure = u.scheme in ("wss", "https")
        port = u.port or (443 if secure else 80)
        reader, writer = await asyncio.wait_for(asyncio.open_connection(
            u.hostname, port, ssl=ssl.create_default_context() if secure else None, limit=2 ** 24), timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        host = u.hostname + (f":{u.port}" if u.port else "")
        writer.write((f"GET {u.path or '/'}{'?' + u.query if u.query else ''} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\n"
                      f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        await writer.drain()
        head = (await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout)).decode("latin-1")
        want = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        if " 101 " not in head.split("\r\n", 1)[0] or want not in head:
            writer.close()
            raise RunError(f"{u.hostname} didn't accept a WebSocket connection at {u.path} ({head.split(chr(13), 1)[0]}).")
        return cls(reader, writer)

    async def _send(self, opcode, payload):
        n, mask = len(payload), os.urandom(4)
        head = bytes([0x80 | opcode]) + (bytes([0x80 | n]) if n < 126 else bytes([0x80 | 126]) + n.to_bytes(2, "big") if n < 65536
                                          else bytes([0x80 | 127]) + n.to_bytes(8, "big"))
        self.writer.write(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))
        await self.writer.drain()

    async def send_json(self, obj):
        await self._send(1, json.dumps(obj).encode())

    async def recv_json(self):
        parts = []
        while True:
            b0, b1 = await self.reader.readexactly(2)
            n = b1 & 0x7F
            if n == 126:
                n = int.from_bytes(await self.reader.readexactly(2), "big")
            elif n == 127:
                n = int.from_bytes(await self.reader.readexactly(8), "big")
            mask = await self.reader.readexactly(4) if b1 & 0x80 else None
            data = await self.reader.readexactly(n)
            if mask:
                data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
            op = b0 & 0x0F
            if op == 8:
                raise RunError("Home Assistant closed the connection.")
            if op == 9:
                await self._send(10, data)  # a ping: answer it
                continue
            if op in (1, 2, 0):
                parts.append(data)
                if b0 & 0x80:  # the last piece of the message
                    return json.loads(b"".join(parts))

    def close(self):
        try:
            self.writer.close()
        except Exception:  # noqa: BLE001
            pass


def _write_json(path, data, **dump_args):
    """Writes JSON so the file is either all old or all new, even if the program stops part-way."""
    tmp = f"{path}.{os.getpid()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, **dump_args)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


# ----- The agent's ready-made helpers: sums, clock times and web pages (the page has the same sums and clock times) -----

class _Calc:
    """Works out a sum like (350 / 500) * 100 exactly, without running any code: numbers, + - * / ^, brackets and a few functions."""
    FUNCS = ("round", "min", "max", "sqrt", "abs", "floor", "ceil")

    def __init__(self, text):
        self.toks = re.findall(r"\d+(?:\.\d*)?|\.\d+|[A-Za-z_]+|\S", to_str(text).replace("×", "*").replace("÷", "/"))
        self.i = 0

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else None

    def take(self, want=None):
        t = self.peek()
        if t is None:
            raise ValueError("it ends too soon")
        if want is not None and t != want:
            raise ValueError(f"expected “{want}” but found “{t}”")
        self.i += 1
        return t

    def run(self):
        if not self.toks:
            raise ValueError("it's empty")
        v = self.expr()
        if self.peek() is not None:
            raise ValueError(f"I don't understand “{self.peek()}” there")
        if not math.isfinite(v):
            raise ValueError("the answer isn't a number")
        return v

    def expr(self):
        v = self.term()
        while self.peek() in ("+", "-"):
            v = v + self.term() if self.take() == "+" else v - self.term()
        return v

    def term(self):
        v = self.unary()
        while self.peek() in ("*", "/"):
            op, r = self.take(), self.unary()
            if op == "/" and r == 0:
                raise ValueError("it divides by zero")
            v = v * r if op == "*" else v / r
        return v

    def unary(self):
        if self.peek() in ("-", "+"):
            return -self.unary() if self.take() == "-" else self.unary()
        return self.power()

    def power(self):
        v = self.primary()
        if self.peek() == "^":
            self.take()
            try:
                v = math.pow(v, self.unary())
            except (ValueError, OverflowError):
                raise ValueError("the answer isn't a number") from None
        return v

    def primary(self):
        t = self.take()
        if t == "(":
            v = self.expr()
            self.take(")")
            return v
        if re.match(r"[\d.]", t):
            return float(t)
        name = t.lower()
        if name == "pi":
            return math.pi
        if name not in self.FUNCS:
            raise ValueError(f"I don't know “{t}” (it can use {', '.join(self.FUNCS)} and pi)")
        self.take("(")
        args = [self.expr()]
        while self.peek() == ",":
            self.take()
            args.append(self.expr())
        self.take(")")
        if name in ("min", "max"):
            return min(args) if name == "min" else max(args)
        if name == "round":
            places = max(0, min(10, int(round_js(args[1])))) if len(args) > 1 else 0
            f = 10 ** places
            return math.floor(args[0] * f + 0.5) / f
        if len(args) != 1:
            raise ValueError(f"{name} takes one number")
        if name == "sqrt" and args[0] < 0:
            raise ValueError("it takes the square root of a negative number")
        return {"sqrt": math.sqrt, "abs": abs, "floor": math.floor, "ceil": math.ceil}[name](args[0])


def read_text_file(path):
    """The words in a PDF, a .docx or a text file. Anything that can't be read becomes a plain RunError."""
    try:
        return _read_text_file(path)
    except RunError:
        raise
    except Exception as e:  # noqa: BLE001 - a damaged, locked or mislabelled file: say so, don't crash
        kind = "Word file" if path.lower().endswith(".docx") else "PDF" if path.lower().endswith(".pdf") else "file"
        raise RunError(f"That {kind} couldn't be read ({type(e).__name__}: {_short(e, 120)}). It may be damaged, locked, or not really a {kind}.") from None


def _read_text_file(path):
    low = path.lower()
    if low.endswith(".pdf"):
        try:
            from pypdf import PdfReader  # pip install pypdf
        except ImportError:
            raise RunError("Reading PDFs needs the pypdf package: pip install pypdf") from None
        return "\n\n".join((p.extract_text() or "") for p in PdfReader(path).pages[:300])
    if low.endswith(".docx"):
        import zipfile
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", "replace")
        xml = re.sub(r"<w:tab/>", "\t", xml)
        xml = re.sub(r"</w:p>|<w:br[^>]*/>", "\n", xml)
        text = re.sub(r"<[^>]+>", "", xml)
        for a, b in (("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&apos;", "'"), ("&amp;", "&")):
            text = text.replace(a, b)
        return text
    with open(path, "rb") as f:
        raw = f.read(25 * 1024 * 1024)
    if b"\x00" in raw[:4000]:
        raise RunError("That file isn't text. Use a PDF, a .docx or a text file.")
    return raw.decode("utf-8", "replace")


def calc_text(expression):
    """'(350 / 500) * 100' -> '(350 / 500) * 100 = 70'."""
    expression = to_str(expression).strip()
    try:
        v = _Calc(expression).run()
    except ValueError as e:
        raise RunError(f"calculate couldn't work out “{_short(expression, 80)}”: {e}.") from None
    v = float(f"{v:.12g}")
    shown = str(int(v)) if v.is_integer() and abs(v) < 1e15 else repr(v)
    return f"{expression} = {shown}"


WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def time_plus_text(when, minutes):
    """'09:30' plus 270 -> '14:00'; '2026-10-10 22:00' plus 600 -> '2026-10-11 08:00 (Sunday)'. Negative minutes go back."""
    m = re.match(r"^\s*(?:(\d{4})-(\d{1,2})-(\d{1,2})[ T]+)?(\d{1,2})[:.](\d{2})\s*(am|pm)?\s*$", to_str(when), re.I)
    if not m:
        raise RunError(f"time_plus needs a time like 09:30 or 2026-10-10 09:30, not “{_short(when, 40)}”.")
    h, mi, ampm = int(m.group(4)), int(m.group(5)), (m.group(6) or "").lower()
    if ampm:
        if not 1 <= h <= 12:
            raise RunError(f"“{to_str(when).strip()}” isn't a time.")
        h = h % 12 + (12 if ampm == "pm" else 0)
    if h > 23 or mi > 59:
        raise RunError(f"“{to_str(when).strip()}” isn't a time.")
    add = round_js(num(minutes))
    if m.group(1):
        try:
            start = datetime.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), h, mi)
        except ValueError:
            raise RunError(f"“{to_str(when).strip()}” isn't a real date.") from None
        t = start + datetime.timedelta(minutes=add)
        return t.strftime("%Y-%m-%d %H:%M") + f" ({WEEKDAYS[t.weekday()]})"
    total = h * 60 + mi + add
    days, t = total // 1440, total % 1440
    note = {0: "", 1: " (next day)", -1: " (the day before)"}.get(days, f" ({days} days later)" if days > 0 else f" ({-days} days earlier)")
    return f"{t // 60:02d}:{t % 60:02d}" + note


def current_time_text():
    d = datetime.datetime.now()
    return f"{WEEKDAYS[d.weekday()]} {d:%Y-%m-%d %H:%M}"
