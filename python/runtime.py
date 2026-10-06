# ---------------------------------------------------------------------------
# Runtime: how each block behaves. You normally don't need to edit this part.
# ---------------------------------------------------------------------------
import asyncio
import base64
import contextlib
import contextvars
import datetime
import json
import math
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# Windows consoles and redirected output can't always show every character; never crash over one.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

# ----- Settings file -----
# Keys and settings live in second-thought.ini, next to this program (it comes in the exported zip).
# Python looks for it next to the program, then in the current folder, then in your home folder;
# SECOND_THOUGHT_INI can point somewhere else. A real environment variable wins over the file.
SETTINGS_FILE = "second-thought.ini"
SETTING_NAMES = {"primary": "RB_MODEL_TIER", "model": "RB_MODEL_TIER", "backups": "RB_BACKUPS"}


def _load_settings():
    import configparser
    here = os.path.dirname(os.path.abspath(sys.argv[0])) if sys.argv and sys.argv[0] else os.getcwd()
    places = [os.environ.get("SECOND_THOUGHT_INI", ""), os.path.join(here, SETTINGS_FILE),
              os.path.join(os.getcwd(), SETTINGS_FILE), os.path.join(os.path.expanduser("~"), SETTINGS_FILE)]
    path = next((p for p in places if p and os.path.isfile(p)), None)
    if not path:
        return None
    cp = configparser.ConfigParser(interpolation=None, inline_comment_prefixes=(";", "#"))
    cp.optionxform = str
    try:
        cp.read(path, encoding="utf-8-sig")  # -sig: Notepad sometimes adds a marker at the start
    except (configparser.Error, UnicodeDecodeError) as e:
        sys.exit(f"There's a mistake in {path}:\n{e}")
    for section in cp.sections():
        for name, value in cp.items(section):
            value = value.strip().strip('"').strip("'")
            key = SETTING_NAMES.get(name.lower(), name.upper())
            if value and not os.environ.get(key):
                os.environ[key] = value
    return path


SETTINGS_PATH = _load_settings()
WHERE_KEYS = f"in {SETTINGS_PATH}" if SETTINGS_PATH else f"in {SETTINGS_FILE}, next to this program"

try:
    from anthropic import AsyncAnthropic
except ImportError:
    sys.exit("This program needs the Anthropic SDK. Install it with:  pip install anthropic")

# Model names change over time. Check https://docs.claude.com for current ones.
MODELS = {
    "quick": "claude-haiku-4-5-20251001",
    "default": "claude-sonnet-5-5",
    "complex": "claude-opus-5-5",
    # Gemini: needs  pip install google-genai  and GEMINI_API_KEY. See https://ai.google.dev/gemini-api/docs/models
    "gemini-quick": "gemini-3.5-flash-lite",
    "gemini-default": "gemini-3.8-flash",
    "gemini-complex": "gemini-3.1-pro-preview",
    # Llama: any OpenAI-compatible server. Default is Ollama on this computer: install from https://ollama.com,
    # then  ollama pull llama3.2-vision:11b  (and the others if you use them). See https://ollama.com/library
    "llama-quick": "llama3.2:3b",              # small and fast; runs on most computers
    "llama-default": "llama3.2-vision:11b",    # can look at pictures; about 8 GB of graphics memory
    "llama-complex": "llama4:16x17b",          # Llama 4 Scout; needs a lot of memory
    # DeepSeek: needs DEEPSEEK_API_KEY (https://platform.deepseek.com). Flash can look at pictures; Pro can't.
    "deepseek-quick": "deepseek-flash",
    "deepseek-default": "deepseek-flash",
    "deepseek-complex": "deepseek-v4-pro",
    # xAI (Grok): needs XAI_API_KEY (https://console.x.ai). Both can look at pictures. See https://docs.x.ai/docs/models
    "xai-quick": "grok-4.3",
    "xai-default": "grok-4.3",
    "xai-complex": "grok-4.7",
    # OpenAI: needs OPENAI_API_KEY (https://platform.openai.com). All three can look at pictures.
    # See https://developers.openai.com/api/docs/models
    "openai-quick": "gpt-6-luna",
    "openai-default": "gpt-6.1-sol",
    "openai-complex": "gpt-6-astra",
    # Mistral (France): needs MISTRAL_API_KEY (https://console.mistral.ai). See https://docs.mistral.ai/getting-started/models
    "mistral-quick": "mistral-small-latest",
    "mistral-default": "mistral-medium-latest",
    "mistral-complex": "mistral-large-latest",
    # Qwen (Alibaba Cloud Model Studio): needs DASHSCOPE_API_KEY (https://modelstudio.console.alibabacloud.com).
    # Pictures go to VISION_MODELS["Qwen"] instead. See https://www.alibabacloud.com/help/en/model-studio/models
    "qwen-quick": "qwen3.8-flash",
    "qwen-default": "qwen3.7-plus",
    "qwen-complex": "qwen3.8-max",
    # Kimi (Moonshot AI): needs MOONSHOT_API_KEY (https://platform.moonshot.ai). Both can look at pictures.
    "kimi-quick": "kimi-k2.6",
    "kimi-default": "kimi-k2.6",
    "kimi-complex": "kimi-k3",
    # Perplexity: needs PERPLEXITY_API_KEY (https://www.perplexity.ai/account/api). Always searches the web and
    # lists its sources. These are Agent API presets, not model names. See https://docs.perplexity.ai
    "perplexity-quick": "fast",
    "perplexity-default": "low",
    "perplexity-complex": "high",
    # Hugging Face: open models run by Hugging Face's partners. Needs HF_TOKEN (https://huggingface.co/settings/tokens).
    # Any model name from https://huggingface.co/models?inference_provider=all works here.
    "hf-quick": "google/gemma-4-26B-A4B-it",
    "hf-default": "google/gemma-4-31B-it",
    "hf-complex": "openai/gpt-oss-120b",
    # Groq: open models, very fast. Needs GROQ_API_KEY (https://console.groq.com). See https://console.groq.com/docs/models
    "groq-quick": "llama-3.1-8b-instant",
    "groq-default": "llama-3.3-70b-versatile",
    "groq-complex": "openai/gpt-oss-120b",
    # GLM (Z.ai, formerly Zhipu): needs ZAI_API_KEY (https://z.ai/manage-apikey/apikey-list). Both can look at pictures.
    "glm-quick": "glm-5.3-flash",
    "glm-default": "glm-5.3-flash",
    "glm-complex": "glm-5.3",
    # MiniMax: needs MINIMAX_API_KEY (https://platform.minimax.io). M3 can look at pictures; M2.7 can't.
    "minimax-quick": "MiniMax-M2.7-highspeed",
    "minimax-default": "MiniMax-M3",
    "minimax-complex": "MiniMax-M3",
    # OpenRouter: one key for hundreds of models (https://openrouter.ai/keys). openrouter/auto picks a model for each
    # step. For one particular model use the "with OpenRouter model" block, or a tier like "openrouter:mistralai/..."
    # with any name from https://openrouter.ai/models
    "openrouter-quick": "openrouter/auto",
    "openrouter-default": "openrouter/auto",
    "openrouter-complex": "openrouter/auto",
}
# Where a service's text models can't see, pictures go to one of its models that can.
VISION_MODELS = {
    "Qwen": os.environ.get("QWEN_VISION_MODEL", "qwen3-vl-plus"),
    "Groq": os.environ.get("GROQ_VISION_MODEL", "qwen/qwen3.8-27b"),
    "Hugging Face": os.environ.get("HF_VISION_MODEL", "google/gemma-4-31B-it"),
}


def _provider(name, prefix, base_env, base, key_envs, signup, headers=None):
    key = next((os.environ[k] for k in key_envs if os.environ.get(k)), "")
    return {"name": name, "prefix": prefix, "base": os.environ.get(base_env, base).rstrip("/"), "base_env": base_env,
            "key": key, "key_env": key_envs[0], "signup": signup, "headers": headers or {}}


# Model services that speak OpenAI's chat format. Change a service's address with its *_BASE_URL variable.
PROVIDERS = {p["name"]: p for p in [
    _provider("Llama", "llama-", "LLAMA_BASE_URL", "http://localhost:11434/v1", ("LLAMA_API_KEY",), None),
    _provider("DeepSeek", "deepseek-", "DEEPSEEK_BASE_URL", "https://api.deepseek.com", ("DEEPSEEK_API_KEY",), "https://platform.deepseek.com"),
    _provider("xAI", "xai-", "XAI_BASE_URL", "https://api.x.ai/v1", ("XAI_API_KEY",), "https://console.x.ai"),
    _provider("OpenAI", "openai-", "OPENAI_BASE_URL", "https://api.openai.com/v1", ("OPENAI_API_KEY",), "https://platform.openai.com"),
    _provider("Mistral", "mistral-", "MISTRAL_BASE_URL", "https://api.mistral.ai/v1", ("MISTRAL_API_KEY",), "https://console.mistral.ai"),
    _provider("Qwen", "qwen-", "QWEN_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
              ("DASHSCOPE_API_KEY", "QWEN_API_KEY"), "https://modelstudio.console.alibabacloud.com"),
    _provider("Kimi", "kimi-", "MOONSHOT_BASE_URL", "https://api.moonshot.ai/v1", ("MOONSHOT_API_KEY", "KIMI_API_KEY"), "https://platform.moonshot.ai"),
    _provider("Hugging Face", "hf-", "HF_BASE_URL", "https://router.huggingface.co/v1", ("HF_TOKEN", "HUGGINGFACE_API_KEY"), "https://huggingface.co/settings/tokens"),
    _provider("Groq", "groq-", "GROQ_BASE_URL", "https://api.groq.com/openai/v1", ("GROQ_API_KEY",), "https://console.groq.com"),
    _provider("GLM", "glm-", "ZAI_BASE_URL", "https://api.z.ai/api/paas/v4", ("ZAI_API_KEY", "ZHIPUAI_API_KEY"), "https://z.ai/manage-apikey/apikey-list"),
    _provider("MiniMax", "minimax-", "MINIMAX_BASE_URL", "https://api.minimax.io/v1", ("MINIMAX_API_KEY",), "https://platform.minimax.io"),
    _provider("OpenRouter", "openrouter-", "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1", ("OPENROUTER_API_KEY",),
              "https://openrouter.ai/keys", {"X-OpenRouter-Title": "Second Thought"}),
    _provider("Perplexity", "perplexity-", "PERPLEXITY_BASE_URL", "https://api.perplexity.ai", ("PERPLEXITY_API_KEY",), "https://www.perplexity.ai/account/api"),
]}
NO_VISION = {"deepseek-v4-pro", "MiniMax-M2.7-highspeed"}  # models that can't look at photos
MODEL_LABELS = {"quick": "Claude, quick", "default": "Claude, balanced", "complex": "Claude, most capable",
                "gemini-quick": "Gemini Flash-Lite", "gemini-default": "Gemini Flash", "gemini-complex": "Gemini Pro",
                "llama-quick": "Llama, small", "llama-default": "Llama, vision", "llama-complex": "Llama 4",
                "deepseek-quick": "DeepSeek Flash", "deepseek-default": "DeepSeek Flash", "deepseek-complex": "DeepSeek V4 Pro",
                "xai-quick": "Grok 4.3", "xai-default": "Grok 4.3", "xai-complex": "Grok 4.7",
                "openai-quick": "GPT-6 Luna", "openai-default": "GPT-6.1 Sol", "openai-complex": "GPT-6 Astra",
                "mistral-quick": "Mistral Small", "mistral-default": "Mistral Medium", "mistral-complex": "Mistral Large",
                "qwen-quick": "Qwen Flash", "qwen-default": "Qwen Plus", "qwen-complex": "Qwen Max",
                "kimi-quick": "Kimi K2.6", "kimi-default": "Kimi K2.6", "kimi-complex": "Kimi K3",
                "perplexity-quick": "Perplexity, fast", "perplexity-default": "Perplexity, research", "perplexity-complex": "Perplexity, deep research",
                "hf-quick": "Gemma 4, small", "hf-default": "Gemma 4", "hf-complex": "GPT-OSS 120B",
                "groq-quick": "Llama 3.1 8B (Groq)", "groq-default": "Llama 3.3 70B (Groq)", "groq-complex": "GPT-OSS 120B (Groq)",
                "glm-quick": "GLM-5.3 Flash", "glm-default": "GLM-5.3 Flash", "glm-complex": "GLM-5.3",
                "minimax-quick": "MiniMax M2.7", "minimax-default": "MiniMax M3", "minimax-complex": "MiniMax M3",
                "openrouter-quick": "OpenRouter, auto-pick", "openrouter-default": "OpenRouter, auto-pick", "openrouter-complex": "OpenRouter, auto-pick"}


def model_label(tier):
    if str(tier).startswith("openrouter:"):
        return "OpenRouter: " + tier.split(":", 1)[1]
    return MODEL_LABELS.get(tier, tier)


MAX_TOKENS = 4096
MAX_AI_CALLS = 60       # per run, to protect your usage
MAX_STEPS = 20000       # stops loops that never end
MAX_SCRIPTS = 100       # scripts started by broadcasts in one run
MAX_DEPTH = 60          # My Blocks calling themselves
OUTPUT_DIR = "outputs"  # where pictures are saved
# 'forever' and timed memories live in this file, next to the program.
MEMORY_FILE = os.environ.get("RB_MEMORY_FILE") or os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "memory.json")


# Home Assistant: the address of your Home Assistant and a long-lived access token
# (your Home Assistant profile, Security tab, "Long-lived access tokens").
HA_URL = os.environ.get("HA_URL", "http://homeassistant.local:8123").rstrip("/")
HA_TOKEN = os.environ.get("HA_TOKEN", "")
HA_TTS_ENTITY = os.environ.get("HA_TTS_ENTITY", "tts.home_assistant_cloud")  # used by the 'say … on' block
HA_WATCH_SECONDS = 15  # how often 'when … changes' scripts check Home Assistant
HA_SENSITIVE = (r"^lock\.(unlock|open)$", r"^cover\.open", r"^alarm_control_panel\.alarm_disarm$", r"^valve\.open", r"^garage_door\.open")

MESSAGE_VALUE = contextvars.ContextVar("message_value", default="")
MODEL_OVERRIDE = contextvars.ContextVar("model_override", default=None)  # set by 'with model' blocks
# Server-side web search for the 'search the web' block. Your API organisation must allow it.
WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 3}


class Finish(Exception):
    """Raised by 'finish' and 'stop the run' blocks."""


class RunError(Exception):
    """A problem in the program itself."""


class Retryable(RunError):
    """A failure a second try could fix (a garbled or empty reply)."""


# ----- pictures -----

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


_BULLET = re.compile(r"^\s*[-*•\d.)]+\s*")


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
    raise Retryable("Claude's reply came back in an unreadable format. Run again.")


def _short(s, n):
    s = re.sub(r"\s+", " ", to_str(s)).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


class Runtime:
    def __init__(self):
        self.vars = {}
        self.receivers = {}
        self.client = None
        self.gemini = None
        self._input_lock = None
        self.schedule_mode = False
        self.transient_memory = {}   # kept across runs while this program keeps running
        self.reset()

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
        self.usage = {}  # provider -> [tokens in, tokens out]
        self.calls = 0
        self.steps = 0
        self.depth = 0
        self.started = 0
        self.timer_start = time.monotonic()
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
    def log(self, label, text=None, status=None):
        head = f"\n▸ {label}" + (f"  [{status}]" if status else "")
        print(head, flush=True)
        if text:
            for line in to_str(text).splitlines() or [""]:
                print("    " + line, flush=True)

    # ----- Claude -----
    @property
    def current_tier(self):
        return MODEL_OVERRIDE.get() or self.tier

    def _count(self, provider, tokens_in, tokens_out):
        u = self.usage.setdefault(provider, [0, 0])
        u[0] += tokens_in or 0
        u[1] += tokens_out or 0

    async def _call(self, prompt, want_json=False, picture=None, history=None, web=False):
        if self.ending:
            raise asyncio.CancelledError()
        self.calls += 1
        if self.calls > MAX_AI_CALLS:
            raise RunError(f"Stopped after {MAX_AI_CALLS} model calls in one run, to protect your usage.")
        tier = self.current_tier
        # Backups stand in for the primary model only. A block that names its own model keeps that model.
        tiers = [tier] + (self.backups if tier == self.primary else [])
        last = None
        for n, t in enumerate(tiers):
            if n:
                self.log("Backup", f"{model_label(tiers[n - 1])} failed: {str(last)[:160]}\nTrying {model_label(t)} instead.", "warn")
            try:
                text = await self._call_tier(t, prompt, want_json, picture, history, web)
            except (asyncio.CancelledError, Finish):
                raise
            except Exception as e:  # no key, out of credit, service down: try the next backup
                last = e
                continue
            if n:
                self.backup_used = self.backup_used + 1
            return _parse_json(text) if want_json else text
        if len(tiers) > 1:
            both = "its backup" if len(tiers) == 2 else f"all {len(tiers) - 1} backups"
            msg = f"The primary model and {both} failed. Last error: {last}"
            raise (Retryable if isinstance(last, Retryable) else RunError)(msg) from last
        raise last

    async def _call_tier(self, tier, prompt, want_json, picture, history, web):
        """One model call on one tier. Returns the reply text."""
        if tier.startswith("gemini-"):
            text = await self._call_gemini(MODELS.get(tier, MODELS["gemini-default"]), prompt, picture, history, web)
            who = "Gemini"
        elif tier.startswith("perplexity-"):
            text, sources = await self._call_perplexity(MODELS.get(tier, MODELS["perplexity-default"]), prompt, picture, history)
            who = "Perplexity"
            if text and sources and not want_json:
                text += "\n\nSources:\n" + "\n".join(sources)
        elif tier.startswith("openrouter:"):
            who = "OpenRouter"
            text = await self._call_openai(who, tier.split(":", 1)[1].strip() or MODELS["openrouter-default"], prompt, picture, history, web)
        elif any(tier.startswith(pv["prefix"]) for pv in PROVIDERS.values()):
            pv = next(pv for pv in PROVIDERS.values() if tier.startswith(pv["prefix"]))
            who = pv["name"]
            text = await self._call_openai(who, MODELS.get(tier, MODELS.get(pv["prefix"] + "default")), prompt, picture, history, web)
        else:
            text = await self._call_claude(MODELS.get(tier, MODELS["default"]), prompt, picture, history, web)
            who = "Claude"
        if not text:
            raise Retryable(f"{who} returned nothing for this step. Simplify it and try again.")
        return text

    async def _call_claude(self, model, prompt, picture, history, web):
        if self.client is None:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise RunError(f"Claude needs a key. Put ANTHROPIC_API_KEY = your-key {WHERE_KEYS} (https://console.anthropic.com).")
            self.client = AsyncAnthropic()
        args = dict(model=model, max_tokens=MAX_TOKENS,
                    messages=(history or []) + [{"role": "user", "content": self._content(prompt, picture)}])
        if self.instructions:
            args["system"] = self.instructions
        if web:
            args["tools"] = [WEB_SEARCH_TOOL]
        msg = await self.client.messages.create(**args)
        usage = getattr(msg, "usage", None)
        self._count("Claude", getattr(usage, "input_tokens", 0), getattr(usage, "output_tokens", 0))
        return "".join(getattr(b, "text", "") or "" for b in msg.content if getattr(b, "type", "text") == "text").strip()

    @staticmethod
    def _openai_request(provider, body, path="/chat/completions"):
        """One request to a model service that speaks OpenAI's format (Ollama, DeepSeek, xAI, OpenAI, Mistral, ...)."""
        pv = PROVIDERS[provider]
        if pv["signup"] and not pv["key"]:
            raise RunError(f"This program uses {provider}. Put {pv['key_env']} = your-key {WHERE_KEYS} ({pv['signup']}).")
        headers = {"Content-Type": "application/json", **pv["headers"]}
        if pv["key"]:
            headers["Authorization"] = "Bearer " + pv["key"]
        req = urllib.request.Request(pv["base"] + path, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:200]
            if provider == "Llama" and e.code == 404 and "model" in detail.lower():
                raise RunError(f"The Llama server doesn't have model {body['model']}. Run:  ollama pull {body['model']}")
            if e.code == 401:
                raise RunError(f"{provider} refused the API key (401). Check {pv['key_env']}.")
            if e.code == 402:
                raise RunError(f"{provider} says the account has no credit left (402).")
            if e.code in (400, 403, 404, 422):
                raise RunError(f"{provider} refused the request ({e.code}): {detail}")
            raise Retryable(f"{provider} answered {e.code}: {detail}")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            hint = " Is Ollama running? Start it with:  ollama serve" if provider == "Llama" else ""
            raise Retryable(f"Couldn't reach {provider} at {pv['base']} ({getattr(e, 'reason', e)}).{hint}")

    async def _call_openai(self, provider, model, prompt, picture, history, web):
        messages = [{"role": "system", "content": self.instructions}] if self.instructions else []
        messages += [{"role": t["role"], "content": to_str(t["content"])} for t in history or []]
        if web:
            prompt = "You can't browse the web, so answer from what you know and say clearly that it may be out of date.\n\n" + prompt
        if picture is not None and picture.svg is None:
            if model in NO_VISION:
                raise RunError(f"{model} can't look at photos. Use a model that can, such as DeepSeek Flash or Claude.")
            if provider in VISION_MODELS and model != VISION_MODELS[provider]:
                model = VISION_MODELS[provider]  # this service's text models can't see; this one can
            url = "data:" + picture.media_type + ";base64," + base64.b64encode(picture.data).decode("ascii")
            content = [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": url}}]
        else:
            content = prompt + ("\n\nThe picture is this SVG drawing:\n" + picture.svg if picture is not None else "")
        messages.append({"role": "user", "content": content})
        body = {"model": model, "messages": messages, "stream": False}
        if provider == "OpenAI":
            # OpenAI's newer models refuse max_tokens, and spend part of the budget thinking before they answer.
            body["max_completion_tokens"] = MAX_TOKENS * 4
        else:
            body["max_tokens"] = MAX_TOKENS
        if provider == "Qwen":
            body["enable_thinking"] = False  # Qwen only thinks out loud when streaming
        data = await asyncio.to_thread(self._openai_request, provider, body)
        usage = data.get("usage") or {}
        self._count(provider, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
        try:
            text = data["choices"][0]["message"]["content"] or ""
            return re.sub(r"<think>.*?</think>\s*", "", text, flags=re.S).strip()  # some models think out loud first
        except (KeyError, IndexError, TypeError):
            return ""

    async def _call_perplexity(self, preset, prompt, picture, history):
        """Perplexity's Agent API: searches the web, then answers with numbered sources."""
        if picture is not None and picture.svg is None:
            raise RunError("Perplexity can't look at photos here. Use Claude, GPT or Gemini for this step.")
        if picture is not None:
            prompt += "\n\nThe picture is this SVG drawing:\n" + picture.svg
        if history:
            past = "\n\n".join(("Me: " if t["role"] == "user" else "You: ") + to_str(t["content"]) for t in history)
            prompt = "Our conversation so far:\n\n" + past + "\n\nNow:\n" + prompt
        body = {"preset": preset, "input": prompt}
        if self.instructions:
            body["instructions"] = self.instructions
        data = await asyncio.to_thread(self._openai_request, "Perplexity", body, "/v1/agent")
        usage = data.get("usage") or {}
        self._count("Perplexity", usage.get("input_tokens", 0), usage.get("output_tokens", 0))
        text, sources, seen = data.get("output_text") or "", [], set()
        for item in data.get("output") or []:
            if item.get("type") == "message" and not data.get("output_text"):
                text += "".join(c.get("text", "") for c in item.get("content") or [] if c.get("type") == "output_text")
            if item.get("type") == "search_results":
                for res in item.get("results") or []:
                    if res.get("url") and res["url"] not in seen:
                        seen.add(res["url"])
                        sources.append(f"[{res.get('id', len(sources) + 1)}] {res.get('title') or res['url']}: {res['url']}")
        return text.strip(), sources

    async def _call_gemini(self, model, prompt, picture, history, web):
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            raise RunError("This program uses Gemini. Install its package first:  pip install google-genai")
        if self.gemini is None:
            if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
                raise RunError(f"Gemini needs a key. Put GEMINI_API_KEY = your-key {WHERE_KEYS} (https://aistudio.google.com).")
            self.gemini = genai.Client()
        contents = []
        for turn in history or []:
            maker = types.UserContent if turn["role"] == "user" else types.ModelContent
            contents.append(maker(parts=[types.Part.from_text(text=to_str(turn["content"]))]))
        if picture is not None and picture.svg is None:
            parts = [types.Part.from_bytes(data=picture.data, mime_type=picture.media_type), types.Part.from_text(text=prompt)]
        else:
            text = prompt + ("\n\nThe picture is this SVG drawing:\n" + picture.svg if picture is not None else "")
            parts = [types.Part.from_text(text=text)]
        contents.append(types.UserContent(parts=parts))
        config = types.GenerateContentConfig(
            system_instruction=self.instructions or None,
            max_output_tokens=MAX_TOKENS,
            tools=[types.Tool(google_search=types.GoogleSearch())] if web else None,
        )
        resp = await self.gemini.aio.models.generate_content(model=model, contents=contents, config=config)
        um = getattr(resp, "usage_metadata", None)
        self._count("Gemini",
                    getattr(um, "prompt_token_count", None) or getattr(um, "input_tokens", 0),
                    getattr(um, "candidates_token_count", None) or getattr(um, "output_tokens", 0))
        try:
            return (resp.text or "").strip()
        except ValueError:  # blocked or empty candidate
            return ""

    @staticmethod
    def _content(prompt, picture):
        if picture is None:
            return prompt
        if picture.svg is not None:
            return prompt + "\n\nThe picture is this SVG drawing:\n" + picture.svg
        return [{"type": "image", "source": {"type": "base64", "media_type": picture.media_type,
                                             "data": base64.b64encode(picture.data).decode("ascii")}},
                {"type": "text", "text": prompt}]

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
        r = await self._call('Answer the question. Reply with only JSON: {"answer": true} or {"answer": false}.\n\nQuestion:\n' + p, True)
        yes = isinstance(r, dict) and r.get("answer") is True
        self.log("Yes or no: " + _short(p, 60), "Yes" if yes else "No", "done")
        return yes

    async def ask_number(self, p):
        p = to_str(p)
        if not p.strip():
            raise RunError("An 'ask for a number' block is empty.")
        r = await self._call('Reply with only JSON: {"number": <a single number>}.\n\nRequest:\n' + p, True)
        n = num(r.get("number") if isinstance(r, dict) else 0)
        self.log("Number: " + _short(p, 60), n, "done")
        return n

    async def ask_list(self, p):
        p = to_str(p)
        if not p.strip():
            raise RunError("An 'ask for a list' block is empty.")
        r = await self._call("Reply with only a JSON array of short strings, no other text.\n\nRequest:\n" + p, True)
        items = r if isinstance(r, list) else (r.get("items", []) if isinstance(r, dict) else [])
        items = [to_str(i) for i in items if to_str(i)]
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
                             '\nBe strict and consistent. Reply with only JSON: {"score": <1-10>}.\n\nText:\n' + text, True)
        s = max(0, min(10, num(r.get("score") if isinstance(r, dict) else 0)))
        self.log("Score: " + _short(text, 50), f"{s}/10", "done")
        return s

    async def better(self, a, b, criteria):
        a, b, criteria = to_str(a), to_str(b), to_str(criteria)
        r = await self._call("Which text is better for: " + criteria +
                             '?\nReply with only JSON: {"pick": 1 or 2, "reason": "<one sentence>"}.\n\nText 1:\n' + a + "\n\nText 2:\n" + b, True)
        second = isinstance(r, dict) and r.get("pick") == 2
        self.log("Pick the better one", ("Picked the second" if second else "Picked the first") +
                 (". " + to_str(r.get("reason")) if isinstance(r, dict) and r.get("reason") else ""), "done")
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
        r = await self._call(("Reply with only a JSON array of objects, each shaped like " if many else "Reply with only one JSON object shaped like ") +
                             shape + ". Use these exact field names. Numbers as numbers.\n\nRequest:\n" + prompt, True)
        if many:
            items = r if isinstance(r, list) else (r.get("items", []) if isinstance(r, dict) else [])
            recs = [to_record(o, fields) for o in items]
            self.log("Records: " + _short(prompt, 55), "\n".join(" · ".join(f"{f}: {_short(x[f], 40)}" for f in fields) for x in recs), f"{len(recs)} records")
            return recs
        rec = to_record(r[0] if isinstance(r, list) and r else r, fields)
        self.log("Record: " + _short(prompt, 55), to_str(rec), "done")
        return rec

    # ----- Prompt library -----
    def prompt(self, name):
        text = PROMPTS.get(to_str(name).strip().lower()) if "PROMPTS" in globals() else None
        if text is None:
            raise RunError(f"There's no prompt called “{name}” in this program's prompt library.")
        return text

    # ----- Files -----
    async def choose_file(self):
        print("\n? Choose a file: type the path to a PDF, a .docx, or a text file (.txt, .md, .csv, .json ...).", flush=True)
        while True:
            path = (await self._input("Path > ")).strip().strip('"').strip("'")
            if not os.path.isfile(path):
                print("  That file doesn't exist. Try again.")
                continue
            if os.path.getsize(path) > 25 * 1024 * 1024:
                print("  That file is over 25 MB. Choose a smaller one.")
                continue
            low = path.lower()
            if low.endswith(".pdf"):
                try:
                    from pypdf import PdfReader  # pip install pypdf
                except ImportError:
                    print("  Reading PDFs needs the pypdf package: pip install pypdf")
                    continue
                text = "\n\n".join((p.extract_text() or "") for p in PdfReader(path).pages[:300])
            elif low.endswith(".docx"):
                import zipfile
                with zipfile.ZipFile(path) as z:
                    xml = z.read("word/document.xml").decode("utf-8", "replace")
                xml = re.sub(r"<w:tab/>", "\t", xml)
                xml = re.sub(r"</w:p>|<w:br[^>]*/>", "\n", xml)
                text = re.sub(r"<[^>]+>", "", xml)
                for a, b in (("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&apos;", "'"), ("&amp;", "&")):
                    text = text.replace(a, b)
            else:
                with open(path, "rb") as f:
                    raw = f.read()
                if b"\x00" in raw[:4000]:
                    print("  That file isn't text. Use a PDF, a .docx or a text file.")
                    continue
                text = raw.decode("utf-8", "replace")
            if not text.strip():
                print("  No text could be found in that file. A scanned PDF holds pictures of pages, not text.")
                continue
            self.log("Chose file", f"{path} \u00b7 {len(text):,} characters", "chosen")
            return text

    def save_file(self, value, name, ext):
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
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        base = re.sub(r"[^\w\-]+", "-", to_str(name)).strip("-") or "output"
        path = os.path.join(OUTPUT_DIR, f"{base}.{ext}")
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

    # ----- Home Assistant -----
    def _ha_request(self, method, path, body=None, raw=False):
        if not HA_TOKEN:
            raise RunError(f"This program uses Home Assistant. Put HA_URL (for example http://homeassistant.local:8123) "
                           f"and HA_TOKEN (a long-lived access token from your Home Assistant profile, Security tab) {WHERE_KEYS}.")
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(HA_URL + path, data=data, method=method,
                                     headers={"Authorization": "Bearer " + HA_TOKEN, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                payload = r.read()
                return (payload, r.headers.get("Content-Type", "")) if raw else (json.loads(payload or b"null"))
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise RunError("Home Assistant refused the token (401). Check HA_TOKEN.")
            if e.code == 404:
                raise RunError(f"Home Assistant has nothing at {path} (404). Check the entity or service name.")
            raise Retryable(f"Home Assistant answered {e.code} for {path}.")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise Retryable(f"Couldn't reach Home Assistant at {HA_URL} ({getattr(e, 'reason', e)}).")

    async def _ha(self, method, path, body=None, raw=False):
        return await asyncio.to_thread(self._ha_request, method, path, body, raw)

    @staticmethod
    def _ha_val(v):
        return num(v) if _num_like(v) else v

    async def _ha_entity(self, entity):
        entity = to_str(entity).strip()
        if not re.match(r"^[a-z_]+\.[a-z0-9_]+$", entity):
            raise RunError(f"“{entity}” isn't an entity id. Use something like light.kitchen.")
        return await self._ha("GET", "/api/states/" + entity)

    async def ha_state(self, entity):
        return self._ha_val((await self._ha_entity(entity))["state"])

    async def ha_attr(self, attr, entity):
        e = await self._ha_entity(entity)
        attr = to_str(attr).strip()
        if attr == "state":
            return self._ha_val(e["state"])
        v = e.get("attributes", {}).get(attr, "")
        return self._ha_val(v) if not isinstance(v, (list, dict)) else json.dumps(v)

    async def _ha_match(self, text):
        words = [w for w in re.split(r"[\s,]+", to_str(text).lower()) if w]
        out = []
        for e in await self._ha("GET", "/api/states"):
            a = e.get("attributes", {})
            hay = " ".join(to_str(x) for x in (e["entity_id"], a.get("friendly_name"), a.get("area"), e["state"],
                                                a.get("device_class"), a.get("unit_of_measurement"))).lower()
            if not words or "*" in words or all(w in hay for w in words):
                out.append(e)
        return out[:150]

    async def ha_find(self, text):
        return [{"entity": e["entity_id"], "name": e.get("attributes", {}).get("friendly_name", e["entity_id"]),
                 "state": self._ha_val(e["state"]), "unit": e.get("attributes", {}).get("unit_of_measurement", ""),
                 "area": e.get("attributes", {}).get("area", "")} for e in await self._ha_match(text)]

    async def ha_summary(self, text):
        lines = []
        for e in await self._ha_match(text):
            a = e.get("attributes", {})
            extra = "".join(f"; {k.replace('_', ' ')}: {v}" for k, v in a.items()
                            if k not in ("friendly_name", "area", "unit_of_measurement", "device_class", "icon", "entity_picture",
                                         "supported_features", "attribution", "state_class") and not isinstance(v, (list, dict)))
            unit = " " + a["unit_of_measurement"] if a.get("unit_of_measurement") else ""
            area = f" [{a['area']}]" if a.get("area") else ""
            lines.append(f"{a.get('friendly_name', e['entity_id'])} ({e['entity_id']}): {e['state']}{unit}{area}{extra}")
        return "\n".join(lines) or "(no matching entities)"

    async def ha_history(self, entity, hours):
        entity = to_str(entity).strip()
        hours = max(1, min(168, num(hours) or 24))
        start = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)).isoformat()
        q = urllib.parse.urlencode({"filter_entity_id": entity, "minimal_response": "", "no_attributes": ""})
        data = await self._ha("GET", "/api/history/period/" + urllib.parse.quote(start) + "?" + q)
        rows = data[0] if data else []
        if len(rows) > 48:
            step = len(rows) / 48
            rows = [rows[int(i * step)] for i in range(48)] + [rows[-1]]
        out = []
        for r in rows:
            try:
                t = datetime.datetime.fromisoformat(r.get("last_changed", "").replace("Z", "+00:00")).astimezone()
                label = t.strftime("%a %H:%M")
            except ValueError:
                label = r.get("last_changed", "")
            out.append({"time": label, "state": self._ha_val(r.get("state", ""))})
        return out

    async def ha_snapshot(self, camera):
        camera = to_str(camera).strip()
        data, ctype = await self._ha("GET", "/api/camera_proxy/" + camera, raw=True)
        pic = Picture(data, (ctype or "image/jpeg").split(";")[0], camera.replace("camera.", "") + "-snapshot")
        self.log("Snapshot: " + camera, "Saved to " + self._picture_path(pic), "done")
        return pic

    async def ha_call(self, service, entity, data_text=""):
        service, entity = to_str(service).strip(), to_str(entity).strip()
        if not re.match(r"^[a-z_]+\.[a-z0-9_]+$", service):
            raise RunError(f"“{service}” isn't a service name. Use domain.service, for example light.turn_off.")
        body = {}
        if to_str(data_text).strip():
            try:
                body = json.loads(to_str(data_text))
            except ValueError:
                raise RunError(f"The data for {service} isn't valid JSON. Use something like {{\"temperature\": 20}}.")
        if entity:
            body["entity_id"] = entity
        if any(re.match(p, service) for p in HA_SENSITIVE):
            if self.schedule_mode and not sys.stdin.isatty():
                self.log("Not done", f"{service} on {entity} needs your approval, and nobody is at the keyboard.", "refused")
                return
            if not await self.approve(f"Allow {service} on {entity or 'Home Assistant'}? (unlocking, opening and disarming always ask)"):
                self.log("Not done", f"{service} on {entity} was refused, so nothing happened.", "refused")
                return
        domain, action = service.split(".", 1)
        await self._ha("POST", f"/api/services/{domain}/{action}", body)
        self.log("Home Assistant: " + service, entity + (f" with {to_str(data_text).strip()}" if to_str(data_text).strip() else ""), "done")

    async def ha_notify(self, target, text):
        target, text = to_str(target).strip() or "persistent_notification", to_str(text)
        if not text.strip():
            raise RunError("The 'notify' block has no message.")
        if target in ("persistent_notification", "persistent_notification.create"):
            await self._ha("POST", "/api/services/persistent_notification/create", {"message": text, "title": "Second Thought"})
        else:
            svc = target.split(".", 1)[1] if target.startswith("notify.") else target
            await self._ha("POST", f"/api/services/notify/{svc}", {"message": text, "title": "Second Thought"})
        self.log("Notification → " + target, text, "sent")

    async def ha_speak(self, text, player):
        text, player = to_str(text), to_str(player).strip()
        if not text.strip():
            raise RunError("The 'say' block has nothing to say.")
        await self._ha("POST", "/api/services/tts/speak", {"entity_id": HA_TTS_ENTITY, "media_player_entity_id": player, "message": text})
        self.log("Spoken on " + player, text, "sent")

    @staticmethod
    def ha_trigger():
        v = MESSAGE_VALUE.get()
        return v if isinstance(v, dict) else {"entity": "", "name": "", "from": "", "to": ""}

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
        tmp = MEMORY_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, MEMORY_FILE)

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
                             '\nBe strict and consistent. Reply with only JSON: {"score": <1-10>}.', True, picture=pic)
        s = max(0, min(10, num(r.get("score") if isinstance(r, dict) else 0)))
        self.log("Score picture: " + _short(criteria, 55), f"{s}/10", "done")
        return s

    def show_picture(self, pic):
        pic = _need_picture(pic, "show picture")
        self.log("Picture", self._picture_path(pic), "shown")

    def save_picture(self, pic, fmt):
        pic = _need_picture(pic, "save picture")
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
        self.draft = await self._call("Revise the draft so it fixes every problem listed. Change nothing else that works. "
                                      "Reply with only the improved piece.\n\nTask:\n" + (self.task or "(none given)") +
                                      "\n\nProblems:\n" + "\n".join("- " + p for p in self.problems) + "\n\nDraft:\n" + self.draft)
        self.log("Revise to fix the problems", self.draft, "revised")

    def set_draft(self, t):
        self.draft = to_str(t)

    async def review(self, criteria, label="Review"):
        self._need_draft()
        v = await self._call("You are a strict reviewer. Judge the draft ONLY against these criteria (separated by semicolons):\n" +
                             to_str(criteria) + "\n\nTask:\n" + (self.task or "(none given)") + "\n\nDraft:\n" + self.draft +
                             '\n\nReply with only JSON like {"approved": false, "problems": ["specific fixable problem"]}. '
                             "approved is true only if every criterion is met; problems is empty when approved.", True)
        approved = isinstance(v, dict) and v.get("approved") is True
        problems = [to_str(p) for p in (v.get("problems") or [])] if isinstance(v, dict) else []
        self.approved = approved
        self.problems = [] if approved else ([p for p in problems if p] or ["Does not yet meet the criteria."])
        if approved:
            self.log(label, "Meets every criterion.", "approved")
        else:
            self.log(label, "\n".join("- " + p for p in self.problems), "needs work")
        return approved

    def rounds(self, n):
        return max(1, min(6, round_js(num(n)) or 3))

    def out_of_rounds(self):
        self.out_of_rounds_hit = True
        self.log("Review", "Out of rounds. Keeping the best effort.", "failed")

    # ----- You (the person at the keyboard) -----
    async def _input(self, prompt):
        if self._input_lock is None:
            self._input_lock = asyncio.Lock()
        async with self._input_lock:
            try:
                return await asyncio.to_thread(input, prompt)
            except EOFError:
                raise RunError("This step needs an answer typed at the keyboard, but there's no one to type it.")

    async def ask_me(self, q):
        q = to_str(q)
        print("\n? " + q, flush=True)
        while True:
            a = (await self._input("> ")).strip()
            if a:
                self.answer = a
                return a
            print("  Type an answer first.")

    async def approve(self, text):
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

    async def choose(self, items):
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
        print(f"\n=== {label} · {datetime.datetime.now():%H:%M} ===", flush=True)
        for fn in scripts:
            if isinstance(fn, tuple):
                self.start_script(fn[0], fn[1])
            else:
                self.start_script(fn)
        while self.tasks:
            await asyncio.wait(set(self.tasks), timeout=0.5, return_when=asyncio.FIRST_COMPLETED)
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
        print(f"\nDone · {self.calls} model call{'s' if self.calls != 1 else ''} · {used}{spare}", flush=True)
        return 0

    # ----- Schedules -----
    async def run_schedules(self, schedules, watches=()):
        if not schedules and not watches:
            sys.exit("This program has no scheduled or 'when … changes' scripts.")
        self.schedule_mode = True
        print("Schedules are on. Leave this running; press Ctrl+C to stop.", flush=True)
        if watches:
            asyncio.ensure_future(self._watch(watches))
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

    def main(self, start_scripts, receivers, schedules, watches=()):
        self.receivers = {k.lower(): v for k, v in receivers.items()}
        use_schedule = "--schedule" in sys.argv or ((schedules or watches) and not start_scripts)
        try:
            if use_schedule:
                asyncio.run(self.run_schedules(schedules, watches))
            else:
                if not start_scripts:
                    sys.exit("Nothing to run: this program has no 'when Run is clicked' script.")
                sys.exit(asyncio.run(self.run(start_scripts)))
        except KeyboardInterrupt:
            print("\nStopped.")
