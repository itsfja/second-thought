"""The model services: which models each tier means, and how each service is called.

Part of the second_thought package. tools/sync.py joins these files, in order, into
python/runtime.py, which is what ships inside every exported program and the page.
"""
import asyncio
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from .settings import WHERE_KEYS
from .core import (BadJSON, CALL_TIMEOUT, CONTINUE_PROMPT, Finish, MAX_AI_CALLS, MAX_TOKENS, Reply, Retryable,
    MEMORY_FILE, RunError, WEB_SEARCH_TOOL, _fit, _number_setting, _parse_json, _shape_problem, _short, to_str)
from .settings import tr  # noqa: F401
# ---- package only: tools/sync.py leaves everything above this line out of python/runtime.py ----


def _anthropic_client(**kw):
    """The Claude client. Imported when first needed, so the rest of this file loads (and can be tested) without the SDK.
    A key made for a whole Console organisation, not one workspace, needs to say which workspace: ANTHROPIC_WORKSPACE_ID."""
    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        raise RunError(tr("Claude needs the Anthropic SDK. Install it with:  pip install anthropic")) from None
    workspace = os.environ.get("ANTHROPIC_WORKSPACE_ID", "").strip()
    if workspace:
        kw["default_headers"] = {**kw.get("default_headers", {}), "anthropic-workspace-id": workspace}
    return AsyncAnthropic(**kw)

# ----- The model services -----
# One entry per service. The page reads this list too (tools/sync.py copies it in), so a service added here shows up
# in the page's model menus, the exported files' notes and settings, and here, with nothing else to change, as long
# as it speaks OpenAI's chat format ("api": "openai"). The other kinds ("anthropic", "gemini", "perplexity") each
# have their own code in ModelCalls below.
#
#   name        the service's name in messages and usage counts (and in PROVIDERS)
#   who         a shorter name the page uses when Claude stands in for it, if not name
#   key_label   how second-thought.ini and the export header label its key, if not name
#   menu        the heading over its models in the page's menu
#   api         "openai" (OpenAI's chat format), "anthropic", "gemini" or "perplexity"
#   prefix      the start of its tier names: "xai-" makes xai-quick, xai-default and xai-complex
#   any_model   a tier start that names any of its models, like "openrouter:mistralai/mistral-small"
#   base        the address of its API; base_env is the setting that changes it
#   keys        the settings its key can be in; the first is the one shown. No signup page means a key is optional
#   signup      where to get a key
#   headers     extra HTTP headers to send
#   tiers       quick, default and complex: (model, label) or (model, label, label in the page's menu). The menus
#               leave out a quick or complex tier whose model is the same as the default's (it would be the same choice)
#   no_vision   models that can't look at pictures
#   vision      (setting, model): where its text models can't see, pictures go to this model instead
#   pip         packages exported programs need for it
#   note        lines for the export header: where calls go and who bills them
#   setup       lines for the export header on setting it up (after the notes)
#   always      exported programs always need it (Claude)
#   maker       who makes its models, if not the service itself; makers: {start of a model's name: maker} where its
#               models come from several (a router like Hugging Face). The run log says "by Google, through Hugging Face"
#   prices      {model: (US dollars per million tokens in, out)}, for the run's cost; a model with none shows no cost
#   prices_checked, prices_source   when the prices were looked up (YYYY-MM-DD) and where. Prices change:
#               python tools/smoke_test.py models notes any older than 90 days
# Model names change over time. To use a different model for a tier without editing this file, put
# MODEL_<TIER> = <model name> in second-thought.ini, like  MODEL_OPENAI_DEFAULT = gpt-6.2-sol  or  MODEL_QUICK = claude-haiku-5.
SERVICES = [
    # Check https://docs.claude.com for current model names.
    {"name": "Claude", "maker": "Anthropic", "menu": "Claude", "api": "anthropic", "prefix": "", "keys": ["ANTHROPIC_API_KEY"],
     "signup": "https://console.anthropic.com", "pip": ["anthropic"], "always": True,
     "tiers": {"quick": ("claude-haiku-4-5-20251001", "Claude, quick", "Quick"),
               "default": ("claude-sonnet-5-5", "Claude, balanced", "Balanced"),
               "complex": ("claude-opus-5-5", "Claude, most capable", "Most capable")},
     "prices": {"claude-haiku-4-5-20251001": (1, 5), "claude-sonnet-5-5": (2, 10), "claude-opus-5-5": (4, 20)},
     "prices_checked": "2026-10-30", "prices_source": "https://platform.claude.com/docs/en/about-claude/pricing"},
    # Gemini: needs  pip install google-genai  and GEMINI_API_KEY. See https://ai.google.dev/gemini-api/docs/models
    {"name": "Gemini", "maker": "Google", "menu": "Gemini", "api": "gemini", "prefix": "gemini-", "keys": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
     "signup": "https://aistudio.google.com", "pip": ["google-genai"],
     "note": ["Gemini calls go through the Gemini API and are billed to your Google account."],
     "tiers": {"quick": ("gemini-3.5-flash-lite", "Gemini Flash-Lite"), "default": ("gemini-3.8-flash", "Gemini Flash"),
               "complex": ("gemini-3.1-pro-preview", "Gemini Pro")},
     # Standard paid tier; Pro's is for prompts up to 200k tokens. Gemini 3.8 Flash goes up to (1.50, 7.50) on 2027-01-01.
     "prices": {"gemini-3.5-flash-lite": (0.30, 2.50), "gemini-3.8-flash": (0.75, 3.75), "gemini-3.1-pro-preview": (2, 12)},
     "prices_checked": "2026-11-03", "prices_source": "https://ai.google.dev/gemini-api/docs/pricing"},
    # Llama: any OpenAI-compatible server. Default is Ollama on this computer: install from https://ollama.com,
    # then  ollama pull llama3.2-vision:11b  (and the others if you use them). See https://ollama.com/library
    # llama-quick is small and fast and runs on most computers; llama-default can look at pictures and needs about
    # 8 GB of graphics memory; llama-complex is Llama 4 Scout and needs a lot of memory.
    {"name": "Llama", "maker": "Meta", "menu": "Llama", "api": "openai", "prefix": "llama-", "base": "http://localhost:11434/v1",
     "base_env": "LLAMA_BASE_URL", "keys": ["LLAMA_API_KEY"], "signup": None,
     "setup": ["Llama runs on any OpenAI-compatible server. By default that's Ollama on this computer:",
               "install it from https://ollama.com, then  ollama pull llama3.2-vision:11b  (see MODELS below).",
               "Elsewhere? Change LLAMA_BASE_URL in second-thought.ini (and LLAMA_API_KEY if the server needs one)."],
     "tiers": {"quick": ("llama3.2:3b", "Llama, small"), "default": ("llama3.2-vision:11b", "Llama, vision"),
               "complex": ("llama4:16x17b", "Llama 4")}},
    # DeepSeek: needs DEEPSEEK_API_KEY (https://platform.deepseek.com). Flash can look at pictures; Pro can't.
    {"name": "DeepSeek", "maker": "DeepSeek", "menu": "DeepSeek", "api": "openai", "prefix": "deepseek-", "base": "https://api.deepseek.com",
     "base_env": "DEEPSEEK_BASE_URL", "keys": ["DEEPSEEK_API_KEY"], "signup": "https://platform.deepseek.com",
     "note": ["DeepSeek calls go to DeepSeek's servers (in China), under DeepSeek's terms, billed to your DeepSeek account."],
     "tiers": {"quick": ("deepseek-flash", "DeepSeek Flash"), "default": ("deepseek-flash", "DeepSeek Flash"),
               "complex": ("deepseek-v4-pro", "DeepSeek V4 Pro")}, "no_vision": ["deepseek-v4-pro"],
     # Peak-hour prices (01:00-04:00 and 06:00-10:00 UTC on weekdays); off-peak is half.
     "prices": {"deepseek-flash": (0.30, 1.20), "deepseek-v4-pro": (1.32, 3.96)},
     "prices_checked": "2026-10-30", "prices_source": "https://api-docs.deepseek.com/quick_start/pricing"},
    # xAI (Grok): needs XAI_API_KEY (https://console.x.ai). Both can look at pictures. See https://docs.x.ai/docs/models
    {"name": "xAI", "maker": "xAI", "who": "Grok", "key_label": "Grok (xAI)", "menu": "Grok, from xAI", "api": "openai", "prefix": "xai-",
     "base": "https://api.x.ai/v1", "base_env": "XAI_BASE_URL", "keys": ["XAI_API_KEY"], "signup": "https://console.x.ai",
     "note": ["Grok calls go to xAI's servers, under xAI's terms, billed to your xAI account (https://console.x.ai)."],
     "tiers": {"quick": ("grok-4.3", "Grok 4.3"), "default": ("grok-4.3", "Grok 4.3"), "complex": ("grok-4.7", "Grok 4.7")},
     # Grok 4.7 from the models page; Grok 4.3 is on https://x.ai/api instead.
     "prices": {"grok-4.3": (1.25, 2.50), "grok-4.7": (2, 6)}, "prices_checked": "2026-11-03", "prices_source": "https://docs.x.ai/developers/models"},
    # OpenAI: needs OPENAI_API_KEY (https://platform.openai.com). All three can look at pictures.
    # See https://developers.openai.com/api/docs/models
    {"name": "OpenAI", "maker": "OpenAI", "menu": "OpenAI", "api": "openai", "prefix": "openai-", "base": "https://api.openai.com/v1",
     "base_env": "OPENAI_BASE_URL", "keys": ["OPENAI_API_KEY"], "signup": "https://platform.openai.com",
     "note": ["OpenAI calls go through the OpenAI API and are billed to your OpenAI API account, not a ChatGPT plan."],
     "tiers": {"quick": ("gpt-6-luna", "GPT-6 Luna"), "default": ("gpt-6.1-sol", "GPT-6.1 Sol"),
               "complex": ("gpt-6-astra", "GPT-6 Astra")},
     "prices": {"gpt-6-luna": (0.10, 0.50), "gpt-6.1-sol": (2, 10), "gpt-6-astra": (10, 50)},
     "prices_checked": "2026-11-03", "prices_source": "https://developers.openai.com/api/docs/pricing"},
    # Mistral (France): needs MISTRAL_API_KEY (https://console.mistral.ai). See https://docs.mistral.ai/getting-started/models
    {"name": "Mistral", "maker": "Mistral AI", "menu": "Mistral", "api": "openai", "prefix": "mistral-", "base": "https://api.mistral.ai/v1",
     "base_env": "MISTRAL_BASE_URL", "keys": ["MISTRAL_API_KEY"], "signup": "https://console.mistral.ai",
     "note": ["Mistral calls go to Mistral AI's servers in the EU, billed to your Mistral account (https://console.mistral.ai)."],
     "tiers": {"quick": ("mistral-small-latest", "Mistral Small"), "default": ("mistral-medium-latest", "Mistral Medium"),
               "complex": ("mistral-large-latest", "Mistral Large")},
     # Small 4 and Large 4 from the API price list; Medium 3.5 isn't on it, so it's from Mistral's own announcement
     # (https://mistral.ai/news/vibe-remote-agents-mistral-medium-3-5/). mistral.ai/pricing gives Large as (0.5, 1.5).
     "prices": {"mistral-small-latest": (0.15, 0.60), "mistral-medium-latest": (1.50, 7.50), "mistral-large-latest": (0.70, 2.10)},
     "prices_checked": "2026-11-03", "prices_source": "https://docs.mistral.ai/inference/pricing"},
    # Qwen (Alibaba Cloud Model Studio): needs DASHSCOPE_API_KEY (https://modelstudio.console.alibabacloud.com).
    # Pictures go to its vision model instead. See https://www.alibabacloud.com/help/en/model-studio/models
    {"name": "Qwen", "maker": "Alibaba", "menu": "Qwen, from Alibaba", "api": "openai", "prefix": "qwen-",
     "base": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1", "base_env": "QWEN_BASE_URL",
     "keys": ["DASHSCOPE_API_KEY", "QWEN_API_KEY"], "signup": "https://modelstudio.console.alibabacloud.com",
     "note": ["Qwen calls go to Alibaba Cloud Model Studio (international region; set QWEN_BASE_URL for another), billed to your Alibaba Cloud account."],
     "tiers": {"quick": ("qwen3.8-flash", "Qwen Flash"), "default": ("qwen3.7-plus", "Qwen Plus"),
               "complex": ("qwen3.8-max", "Qwen Max")}, "vision": ("QWEN_VISION_MODEL", "qwen3-vl-plus"),
     # International (Singapore) list prices; Plus's for prompts up to 256k tokens.
     "prices": {"qwen3.8-flash": (0.15, 0.47), "qwen3.7-plus": (0.40, 1.60), "qwen3.8-max": (2, 6)},
     "prices_checked": "2026-11-03", "prices_source": "https://www.alibabacloud.com/help/en/model-studio/model-pricing"},
    # Kimi (Moonshot AI): needs MOONSHOT_API_KEY (https://platform.moonshot.ai). Both can look at pictures.
    {"name": "Kimi", "maker": "Moonshot AI", "menu": "Kimi, from Moonshot", "api": "openai", "prefix": "kimi-", "base": "https://api.moonshot.ai/v1",
     "base_env": "MOONSHOT_BASE_URL", "keys": ["MOONSHOT_API_KEY", "KIMI_API_KEY"], "signup": "https://platform.moonshot.ai",
     "note": ["Kimi calls go to Moonshot AI's servers (a Chinese company), under Moonshot's terms, billed to your Moonshot account."],
     "tiers": {"quick": ("kimi-k2.6", "Kimi K2.6"), "default": ("kimi-k2.6", "Kimi K2.6"), "complex": ("kimi-k3", "Kimi K3")},
     # Kimi K2.6 has no price on Kimi's own pages yet, so it shows none.
     "prices": {"kimi-k3": (3, 15)}, "prices_checked": "2026-11-03", "prices_source": "https://www.kimi.ai/resources/kimi-k3-pricing"},
    # Perplexity: needs PERPLEXITY_API_KEY (https://www.perplexity.ai/account/api). Always searches the web and
    # lists its sources. These are Agent API presets, not model names. See https://docs.perplexity.ai
    {"name": "Perplexity", "maker": "Perplexity", "menu": "Perplexity, searches the web", "api": "perplexity", "prefix": "perplexity-",
     "base": "https://api.perplexity.ai", "base_env": "PERPLEXITY_BASE_URL", "keys": ["PERPLEXITY_API_KEY"],
     "signup": "https://www.perplexity.ai/account/api",
     "note": ["Perplexity searches the web for every step it answers and lists its sources; billed to your Perplexity API account."],
     "tiers": {"quick": ("fast", "Perplexity, fast"), "default": ("low", "Perplexity, research"),
               "complex": ("high", "Perplexity, deep research")}},
    # Hugging Face: open models run by Hugging Face's partners. Needs HF_TOKEN (https://huggingface.co/settings/tokens).
    # Any model name from https://huggingface.co/models?inference_provider=all works here.
    {"name": "Hugging Face", "makers": {"google/": "Google", "openai/": "OpenAI"}, "menu": "Open models on Hugging Face", "api": "openai", "prefix": "hf-",
     "base": "https://router.huggingface.co/v1", "base_env": "HF_BASE_URL", "keys": ["HF_TOKEN", "HUGGINGFACE_API_KEY"],
     "signup": "https://huggingface.co/settings/tokens",
     "note": ["Hugging Face passes open-model calls to one of its partner services; billed to your Hugging Face account. Any model from huggingface.co works: edit MODELS below."],
     "tiers": {"quick": ("google/gemma-4-26B-A4B-it", "Gemma 4, small"), "default": ("google/gemma-4-31B-it", "Gemma 4"),
               "complex": ("openai/gpt-oss-120b", "GPT-OSS 120B")}, "vision": ("HF_VISION_MODEL", "google/gemma-4-31B-it")},
    # Groq: open models, very fast. Needs GROQ_API_KEY (https://console.groq.com). See https://console.groq.com/docs/models
    {"name": "Groq", "makers": {"llama": "Meta", "openai/": "OpenAI"}, "menu": "Groq, very fast", "api": "openai", "prefix": "groq-", "base": "https://api.groq.com/openai/v1",
     "base_env": "GROQ_BASE_URL", "keys": ["GROQ_API_KEY"], "signup": "https://console.groq.com",
     "note": ["Groq calls go to Groq's servers (US), billed to your Groq account. Groq has a free tier with rate limits."],
     "tiers": {"quick": ("llama-3.1-8b-instant", "Llama 3.1 8B (Groq)"), "default": ("llama-3.3-70b-versatile", "Llama 3.3 70B (Groq)"),
               "complex": ("openai/gpt-oss-120b", "GPT-OSS 120B (Groq)")}, "vision": ("GROQ_VISION_MODEL", "qwen/qwen3.8-27b"),
     # Groq's model list gives its Llama models' prices as "contact sales", so they show none.
     "prices": {"openai/gpt-oss-120b": (0.15, 0.60)}, "prices_checked": "2026-11-03", "prices_source": "https://console.groq.com/docs/models"},
    # GLM (Z.ai, formerly Zhipu): needs ZAI_API_KEY (https://z.ai/manage-apikey/apikey-list). Both can look at pictures.
    {"name": "GLM", "maker": "Z.ai", "menu": "GLM, from Z.ai", "api": "openai", "prefix": "glm-", "base": "https://api.z.ai/api/paas/v4",
     "base_env": "ZAI_BASE_URL", "keys": ["ZAI_API_KEY", "ZHIPUAI_API_KEY"], "signup": "https://z.ai/manage-apikey/apikey-list",
     "note": ["GLM calls go to Z.ai (formerly Zhipu AI, a Chinese company), under Z.ai's terms, billed to your Z.ai account."],
     "tiers": {"quick": ("glm-5.3-flash", "GLM-5.3 Flash"), "default": ("glm-5.3-flash", "GLM-5.3 Flash"),
               "complex": ("glm-5.3", "GLM-5.3")},
     "prices": {"glm-5.3-flash": (0.15, 0.50), "glm-5.3": (1.40, 4.40)},
     "prices_checked": "2026-11-03", "prices_source": "https://docs.z.ai/guides/overview/pricing"},
    # MiniMax: needs MINIMAX_API_KEY (https://platform.minimax.io). M3 and M3.1 Flash both look at pictures.
    {"name": "MiniMax", "maker": "MiniMax", "menu": "MiniMax", "api": "openai", "prefix": "minimax-", "base": "https://api.minimax.io/v1",
     "base_env": "MINIMAX_BASE_URL", "keys": ["MINIMAX_API_KEY"], "signup": "https://platform.minimax.io",
     "note": ["MiniMax calls go to MiniMax's international servers (a Chinese company), under MiniMax's terms, billed to your MiniMax account."],
     # The quick tier was M2.7-highspeed until #281: it's no longer on MiniMax's price list or its API's list of models.
     # M3.1 Flash (released 2026-10-19) is its everyday model; MODEL_MINIMAX_QUICK = MiniMax-M2.7-highspeed keeps the old one.
     "tiers": {"quick": ("MiniMax-M3.1-Flash", "MiniMax M3.1 Flash"), "default": ("MiniMax-M3", "MiniMax M3"),
               "complex": ("MiniMax-M3", "MiniMax M3")},
     # Standard tier, prompts up to 512k tokens.
     "prices": {"MiniMax-M3.1-Flash": (0.15, 0.60), "MiniMax-M3": (0.30, 1.20)}, "prices_checked": "2026-11-04",
     "prices_source": "https://platform.minimax.io/docs/pricing/overview"},
    # OpenRouter: one key for hundreds of models (https://openrouter.ai/keys). openrouter/auto picks a model for each
    # step. For one particular model use the "with OpenRouter model" block, or a tier like "openrouter:mistralai/..."
    # with any name from https://openrouter.ai/models
    {"name": "OpenRouter", "makers": {}, "menu": "OpenRouter, hundreds of models", "api": "openai", "prefix": "openrouter-",
     "any_model": "openrouter:", "base": "https://openrouter.ai/api/v1", "base_env": "OPENROUTER_BASE_URL",
     "keys": ["OPENROUTER_API_KEY"], "signup": "https://openrouter.ai/keys", "headers": {"X-OpenRouter-Title": "Second Thought"},
     "note": ["OpenRouter passes each call to the company that makes the model you chose, under that company's terms; billed to your OpenRouter credit (https://openrouter.ai/keys)."],
     "tiers": {"quick": ("openrouter/auto", "OpenRouter, auto-pick"), "default": ("openrouter/auto", "OpenRouter, auto-pick"),
               "complex": ("openrouter/auto", "OpenRouter, auto-pick")}},
]
TIER_NAMES = ("quick", "default", "complex")


def _tier(service, size):
    """The tier name for one of a service's sizes: "xai-" and "default" make "xai-default" (Claude's are plain "default")."""
    return service["prefix"] + size


# The tables the rest of the runtime uses, made from SERVICES.
# MODELS: every tier's model, like MODELS["xai-default"] == "grok-4.3". To change one, edit that service's "tiers" in
# SERVICES above, or put MODEL_<TIER> = <model name> in second-thought.ini (no editing needed).
MODELS ={_tier(s, k): s["tiers"][k][0] for s in SERVICES for k in TIER_NAMES if k in s["tiers"]}
# Where a service's text models can't see, pictures go to one of its models that can.
VISION_MODELS = {s["name"]: os.environ.get(s["vision"][0], s["vision"][1]) for s in SERVICES if s.get("vision")}


def _provider(name, prefix, base_env, base, key_envs, signup, headers=None):
    key = next((os.environ[k] for k in key_envs if os.environ.get(k)), "")
    return {"name": name, "prefix": prefix, "base": os.environ.get(base_env, base).rstrip("/"), "base_env": base_env,
            "key": key, "key_env": key_envs[0], "signup": signup, "headers": headers or {}}


# Model services that speak OpenAI's chat format (and Perplexity, whose agent API is close to it). Change a service's
# address with its *_BASE_URL setting.
PROVIDERS = {s["name"]: _provider(s["name"], s["prefix"], s["base_env"], s["base"], tuple(s["keys"]), s["signup"], s.get("headers"))
             for s in SERVICES if s["api"] in ("openai", "perplexity")}
for _tier_name in list(MODELS):
    _name = os.environ.get("MODEL_" + _tier_name.upper().replace("-", "_"), "").strip()
    if _name:
        MODELS[_tier_name] = _name
NO_VISION = {m for s in SERVICES for m in s.get("no_vision", ())}  # models that can't look at photos
MODEL_LABELS = {_tier(s, k): s["tiers"][k][1] for s in SERVICES for k in TIER_NAMES if k in s["tiers"]}
# PRICES: what each tier's model costs, in US dollars per million tokens (in, out), from its service's "prices" (each
# service says when they were checked, and where: services change them). A tier whose model has no price, or was
# changed with MODEL_<TIER>, has none, and a run that uses it shows no cost rather than a wrong one.
PRICES = {_tier(s, k): tuple(s["prices"][MODELS[_tier(s, k)]]) for s in SERVICES for k in TIER_NAMES
          if k in s["tiers"] and MODELS.get(_tier(s, k)) in s.get("prices", {})}


def call_cost(tier, tokens_in, tokens_out):
    """What one model call cost in US dollars, or None if its model's price isn't known."""
    p = PRICES.get(tier)
    return None if p is None else ((tokens_in or 0) * p[0] + (tokens_out or 0) * p[1]) / 1_000_000


# ----- Currencies -----
# Prices are in US dollars, as the services publish and bill them. A run's cost and its money budget can be shown in
# another currency: currency = gbp in second-thought.ini. Each has a symbol before the amount, or a code after it (yuan,
# so it isn't mistaken for yen), and its decimals (yen has none). The page reads this and RATES too (tools/sync.py).
CURRENCIES = {"usd": {"symbol": "$", "decimals": 2}, "gbp": {"symbol": "£", "decimals": 2}, "eur": {"symbol": "€", "decimals": 2},
              "jpy": {"symbol": "¥", "decimals": 0}, "cny": {"code": "CNY", "decimals": 2}}
# RATES: the European Central Bank's euro reference rates on one day. Exported programs fetch the day's rates (once a
# day, kept next to memory.json); these are what they fall back on, and the page's only rates, since it can't fetch
# them. python tools/smoke_test.py models notes them when they're more than 30 days old.
RATES = {"date": "2026-10-30", "per_euro": {"usd": 1.1172, "gbp": 0.8338, "jpy": 175.68, "cny": 7.4326},
         "source": "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html"}
ECB_DAILY = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
CURRENCY = (os.environ.get("RB_CURRENCY") or "usd").strip().lower()
if CURRENCY not in CURRENCIES:
    sys.exit(tr("currency must be usd, gbp, eur, jpy or cny, not “{raw}”. Fix it {where_keys}.", raw=CURRENCY, where_keys=WHERE_KEYS))
_RATES = {}  # the rates this program is using: per_euro, where they came from, and any problem fetching them


def _rates_file():
    return os.path.join(os.path.dirname(os.path.abspath(MEMORY_FILE)), ".second-thought-rates.json")


def rates():
    """{"per_euro": {...}, "date", "how": "ecb" or "built-in", "problem"}: fetched from the ECB at most once a day, kept
    next to memory.json, else the last kept, else RATES. Never fails, so a money budget always has a rate."""
    if _RATES:
        return _RATES
    kept = None
    try:
        with open(_rates_file(), encoding="utf-8") as f:
            kept = json.load(f)
        if time.time() - kept.get("fetched", 0) < 12 * 3600 and isinstance(kept.get("per_euro"), dict):
            _RATES.update(per_euro=kept["per_euro"], date=kept.get("date", ""), how="ecb", problem="")
            return _RATES
    except (OSError, ValueError, AttributeError):
        kept = None
    problem = ""
    try:
        url = os.environ.get("RB_RATES_URL") or ECB_DAILY
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "second-thought"}), timeout=10) as r:
            xml = r.read(200_000).decode("utf-8", "replace")
        per = {m.group(1).lower(): float(m.group(2)) for m in re.finditer(r"currency=['\"]([A-Z]{3})['\"]\s+rate=['\"]([\d.]+)['\"]", xml)}
        day = re.search(r"time=['\"](\d{4}-\d{2}-\d{2})['\"]", xml)
        if not all(c in per for c in CURRENCIES if c != "eur"):
            raise ValueError("the rates file didn't have every currency")
        _RATES.update(per_euro=per, date=day.group(1) if day else "", how="ecb", problem="")
        try:
            with open(_rates_file(), "w", encoding="utf-8") as f:
                json.dump({"per_euro": per, "date": _RATES["date"], "fetched": time.time()}, f)
        except OSError:
            pass
        return _RATES
    except (urllib.error.URLError, OSError, ValueError) as e:
        problem = _short(to_str(getattr(e, "reason", None) or e), 100)
    if kept and isinstance(kept.get("per_euro"), dict):
        _RATES.update(per_euro=kept["per_euro"], date=kept.get("date", ""), how="ecb", problem=problem)
    else:
        _RATES.update(per_euro=RATES["per_euro"], date=RATES["date"], how="built-in", problem=problem)
    return _RATES


def fixed_rate():
    """exchange_rate in second-thought.ini: one US dollar in the program's currency, instead of the ECB's rate; or 0."""
    if CURRENCY == "usd":
        return 0
    return _number_setting("RB_EXCHANGE_RATE", 0, "how much one US dollar is in your currency, like 0.79")


def per_dollar(cur):
    """How much one US dollar is in this currency."""
    if cur == "usd":
        return 1.0
    if cur == CURRENCY and fixed_rate():
        return fixed_rate()
    per = rates()["per_euro"]
    return (1.0 if cur == "eur" else per[cur]) / per["usd"]


def amount_text(value, cur):
    """An amount in a currency, exactly: '$0.50', '£12.00', '¥75', '0.40 CNY', and its digits under the smallest coin."""
    c = CURRENCIES[cur]
    smallest = 10 ** -c["decimals"]
    text = (f"{value:.6f}".rstrip("0").rstrip(".") if 0 < value < smallest else f"{value:,.{c['decimals']}f}")
    return c["symbol"] + text if "symbol" in c else text + " " + c["code"]


def money(dollars, cur=None):
    """A cost for people, in the program's currency (or cur): 'about £0.02', 'under ¥1', 'about $1.20'."""
    cur = cur or CURRENCY
    value = dollars * per_dollar(cur)
    smallest = 10 ** -CURRENCIES[cur]["decimals"]
    if value < smallest / 2:
        return tr("under {cost}", cost=amount_text(smallest, cur))
    return tr("about {cost}", cost=amount_text(max(round(value, CURRENCIES[cur]["decimals"]), smallest), cur))


def dollars(amount):
    """An exact amount in US dollars, like a budget: '$0.50', '$12.00', and '$0.004' under a cent, rather than '$0.00'."""
    return amount_text(amount, "usd")


def rate_note():
    """Where the run's rate came from, for the saved log and --doctor: '' in US dollars."""
    if CURRENCY == "usd":
        return ""
    if fixed_rate():
        return tr("at the rate set {where_keys}", where_keys=WHERE_KEYS)
    return tr("at the ECB rate of {date}", date=rates()["date"])


# How expensive a model is, from its list price per million output tokens: up to each amount, that band; above the
# last, premium. A model run on this computer (Llama through Ollama) is free; one with no known price has no band.
# The page reads these too (tools/sync.py).
BANDS = [[0, "free"], [5, "budget"], [15, "standard"]]


def service_of(tier):
    """The SERVICES entry a tier belongs to (Claude's are quick, default and complex), or None."""
    tier = to_str(tier)
    for s in SERVICES:
        if s.get("any_model") and tier.startswith(s["any_model"]):
            return s
        if any(_tier(s, k) == tier for k in s["tiers"]):
            return s
    return None


def runs_here(tier):
    """Whether this tier's model runs on this computer: Llama on Ollama at localhost, as set up by default."""
    s = service_of(tier)
    base = (os.environ.get(s["base_env"]) or s.get("base") or "") if s and s.get("base_env") else ""
    return bool(s and s["name"] == "Llama" and re.match(r"https?://(localhost|127\.0\.0\.1|\[::1\])(:|/|$)", base))


def price_band(tier):
    """free, budget, standard or premium; None when the model's price isn't known."""
    if runs_here(tier):
        return "free"
    p = PRICES.get(tier)
    if p is None:
        return None
    return next((name for top, name in BANDS if p[1] <= top), "premium")


def band_text(tier):
    band = price_band(tier)
    return {"free": tr("free"), "budget": tr("budget"), "standard": tr("standard"), "premium": tr("premium")}.get(band) or tr("price unknown")


def maker_of(tier):
    """Who makes the model a tier uses, or ''."""
    s = service_of(tier)
    if not s:
        return ""
    model = MODELS.get(tier) or to_str(tier).split(":", 1)[-1]
    return next((m for start, m in (s.get("makers") or {}).items() if model.startswith(start)), s.get("maker", ""))


def model_byline(tier):
    """'Gemma 4, by Google, through Hugging Face' for a router's model (a service with makers), 'Llama 4, by Meta, on
    this computer' for one run here; otherwise the model's name, since the service is its maker's own."""
    s, maker = service_of(tier), maker_of(tier)
    if not s or not maker or not (s.get("makers") is not None or runs_here(tier)):
        return model_label(tier)
    where = tr("on this computer") if runs_here(tier) else tr("through {service}", service=s["name"])
    return tr("{model}, by {maker}, {where}", model=model_label(tier), maker=maker, where=where)


# What each service last reported about its rate limits, from the headers of its replies (#270):
# {service: {"model": the model called, "limits": {kind: {"limit", "remaining", "reset"}}}}. Claude, OpenAI and Groq send
# them; others don't. Kinds are requests, tokens, input-tokens and output-tokens.
REPORTED = {}


def limits_from_headers(headers):
    """{kind: {"limit": n, "remaining": n, "reset": text}} from a reply's rate-limit headers: Claude's
    anthropic-ratelimit-<kind>-<what>, and OpenAI's and Groq's x-ratelimit-<what>-<kind>."""
    found = {}
    for name, value in (dict(headers or {})).items():
        name = to_str(name).lower()
        m = re.match(r"anthropic-ratelimit-(requests|tokens|input-tokens|output-tokens)-(limit|remaining|reset)$", name)
        kind, what = (m.group(1), m.group(2)) if m else (None, None)
        if not m:
            m = re.match(r"x-ratelimit-(limit|remaining|reset)-(requests|tokens)$", name)
            kind, what = (m.group(2), m.group(1)) if m else (None, None)
        if kind:
            found.setdefault(kind, {})[what] = to_str(value).strip()
    out = {}
    for kind, v in found.items():
        try:
            limit, remaining = int(float(v["limit"])), int(float(v["remaining"]))
        except (KeyError, ValueError):
            continue
        if limit > 0:
            out[kind] = {"limit": limit, "remaining": max(0, remaining), "reset": v.get("reset", "")}
    return out


def record_limits(service, model, headers):
    limits = limits_from_headers(headers)
    if limits:
        REPORTED[service] = {"model": model, "limits": limits}


def model_label(tier):
    if str(tier).startswith("openrouter:"):
        return "OpenRouter: " + tier.split(":", 1)[1]
    return MODEL_LABELS.get(tier, tier)


class ModelCalls:
    """Calling the model services. Part of Runtime (see runtime.py)."""
    def _within_money_budget(self, tiers):
        """With a budget in dollars: stops the run once it's spent, or if the model to be called has no known price (it
        couldn't be counted, so the run would have no limit). Backups with no price are left out. Gives the tiers to try."""
        budget = self.budget_dollars
        if call_cost(tiers[0], 0, 0) is None:
            raise RunError(tr("Stopped: {model} has no known price, so this run can't be held to its budget of {x}. Use a model with a price, or a budget in tokens.",
                              model=model_label(tiers[0]), x=self.budget_text()))
        if not self.cost[1]:
            raise RunError(tr("Stopped: a model this run has already used has no known price, so it can't be held to its budget of {x}. Use models with a price, or a budget in tokens.",
                              x=self.budget_text()))
        if self.cost[0] >= budget:
            raise RunError(tr("Stopped: this run has spent {x} at list prices, which reaches its budget of {x2}. Raise the amount in the 'limit this run' block (or budget_dollars in second-thought.ini).",
                              x=money(self.cost[0], self.budget_unit), x2=self.budget_text()))
        return [t for t in tiers if call_cost(t, 0, 0) is not None]

    async def _call_live(self, prompt, want_json=False, picture=None, history=None, web=False):
        if self.ending:
            raise asyncio.CancelledError()
        self.calls += 1
        if self.calls > MAX_AI_CALLS:
            raise RunError(tr("Stopped after {max_ai_calls} model calls in one run, to protect your usage.", max_ai_calls=MAX_AI_CALLS))
        if self.budget and self.tokens_used() >= self.budget:
            raise RunError(tr("Stopped: this run has used {x} tokens, which reaches its budget of {x2}. Raise the number in the 'limit this run' block (or budget in second-thought.ini).", x=format(self.tokens_used(), ','), x2=format(self.budget, ',')))
        tier = self.current_tier
        # Backups stand in for the primary model only. A block that names its own model keeps that model.
        tiers = [tier] + (self.backups if tier == self.primary else [])
        if self.budget_dollars:
            tiers = self._within_money_budget(tiers)
        tiers = self._within_allowances(tiers)  # each key's hourly, daily, weekly and monthly allowance (#269)
        last = None
        for n, t in enumerate(tiers):
            if n:
                self.log(tr("Backup"), tr("{x} failed: {x2}\nTrying {x3} instead.", x=model_label(tiers[n - 1]), x2=str(last)[:160], x3=model_label(t)), tr("warn"), calls=False)
            try:
                text = await self._timed_call(t, prompt, want_json, picture, history, web)
            except (asyncio.CancelledError, Finish):
                raise
            except Exception as e:  # no key, out of credit, service down: try the next backup
                last = e
                continue
            if n:
                self.backup_used = self.backup_used + 1
            if not want_json:
                if getattr(text, "truncated", False):
                    text = await self._continue(t, prompt, text, history, web)
                return text
            schema = want_json if isinstance(want_json, dict) else None
            try:
                return self._read_json(text, schema)
            except BadJSON as e:
                # One more try on the same model, showing it what went wrong. Counts as a call like any other.
                self.log(tr("Unreadable reply"), tr("{e}\nAsking once more for a corrected reply.", e=e), tr("repair"), calls=False)
                self.calls += 1
                if self.calls > MAX_AI_CALLS:
                    raise RunError(tr("Stopped after {max_ai_calls} model calls in one run, to protect your usage.", max_ai_calls=MAX_AI_CALLS))
                fix = await self._timed_call(t, prompt + "\n\nYour previous reply couldn't be used: " + str(e) +
                                            "\nPrevious reply:\n" + _short(text, 2000) +
                                            "\n\nReply again with only the corrected JSON.", want_json, picture, history, web)
                return self._read_json(fix, schema)
        if len(tiers) > 1:
            both = "its backup" if len(tiers) == 2 else f"all {len(tiers) - 1} backups"
            msg = f"The primary model and {both} failed. Last error: {last}"
            raise (Retryable if isinstance(last, Retryable) else RunError)(msg) from last
        raise last

    async def _continue(self, tier, prompt, text, history, web):
        """A reply cut off by the length limit: ask once for the rest, on the same model, and join the two parts."""
        self.log(tr("Reply continued"), tr("The reply reached the length limit, so the model was asked to carry on from where it stopped."),
                 tr("continued"), calls=False)
        self.calls += 1
        if self.calls > MAX_AI_CALLS:
            raise RunError(tr("Stopped after {max_ai_calls} model calls in one run, to protect your usage.", max_ai_calls=MAX_AI_CALLS))
        turns = (history or []) + [{"role": "user", "content": to_str(prompt)}, {"role": "assistant", "content": to_str(text)}]
        more = await self._timed_call(tier, CONTINUE_PROMPT, False, None, turns, web)
        joined = to_str(text) + to_str(more)  # the continuation picks up exactly where the first part stopped
        if getattr(more, "truncated", False):
            self.out_of_rounds_hit = True
            self.log(tr("Cut short"), tr("Even after carrying on, the reply was still too long, so it stops part-way. It's kept as it is, marked best effort. Ask for something shorter, or split the job into smaller steps."), tr("warn"), calls=False)
        return joined

    @staticmethod
    def _read_json(text, schema):
        """Parses a reply and checks it against the schema. Raises BadJSON with a plain reason."""
        v = _parse_json(text)
        schema = getattr(schema, "check", schema)
        if schema:
            v = _fit(v, schema)
            bad = _shape_problem(v, schema)
            if bad:
                raise BadJSON(tr("The reply didn't have the expected shape: {bad}.", bad=bad))
        return v

    async def _call_tier(self, tier, prompt, want_json, picture, history, web):
        """One model call on one tier. Returns the reply text."""
        schema = want_json if isinstance(want_json, dict) else None
        if tier.startswith("gemini-"):
            text = await self._call_gemini(MODELS.get(tier, MODELS["gemini-default"]), prompt, picture, history, web, schema)
            who = "Gemini"
        elif tier.startswith("perplexity-"):
            text, sources = await self._call_perplexity(MODELS.get(tier, MODELS["perplexity-default"]), prompt, picture, history)
            who = "Perplexity"
            if text and sources and not want_json:
                text += "\n\nSources:\n" + "\n".join(sources)
        elif tier.startswith("openrouter:"):
            who = "OpenRouter"
            text = await self._call_openai(who, tier.split(":", 1)[1].strip() or MODELS["openrouter-default"], prompt, picture, history, web, schema)
        elif any(tier.startswith(pv["prefix"]) for pv in PROVIDERS.values()):
            pv = next(pv for pv in PROVIDERS.values() if tier.startswith(pv["prefix"]))
            who = pv["name"]
            text = await self._call_openai(who, MODELS.get(tier, MODELS.get(pv["prefix"] + "default")), prompt, picture, history, web, schema)
        else:
            text = await self._call_claude(MODELS.get(tier, MODELS["default"]), prompt, picture, history, web, schema)
            who = "Claude"
        if not text:
            raise Retryable(tr("{who} returned nothing for this step. Simplify it and try again.", who=who))
        return text

    async def _call_claude(self, model, prompt, picture, history, web, schema=None):
        if self.client is None:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise RunError(tr("Claude needs a key. Put ANTHROPIC_API_KEY = your-key {where_keys} (https://console.anthropic.com).", where_keys=WHERE_KEYS))
            self.client = _anthropic_client(timeout=CALL_TIMEOUT, max_retries=2)
        args = dict(model=model, max_tokens=MAX_TOKENS,
                    messages=(history or []) + [{"role": "user", "content": self._content(prompt, picture)}])
        if self.instructions:
            args["system"] = self.instructions
        if web:
            args["tools"] = [WEB_SEARCH_TOOL]
        # A shape Claude won't take is remembered with its model, so the other shapes are still held while Claude writes.
        shape = (model, json.dumps(schema, sort_keys=True)) if schema else None
        if schema and not web and shape not in self.no_schema:
            # Structured outputs: Claude can only write JSON of this shape. https://platform.claude.com/docs/en/build-with-claude/structured-outputs
            args["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
        try:
            msg = await (self._claude_stream(args) if "output_config" not in args and self._streaming() else self._claude_create(args))
        except Exception as e:  # noqa: BLE001
            if "output_config" not in args or getattr(e, "status_code", None) != 400:
                raise
            # This model or account won't take the shape: ask without it (the reply is still checked), and stop sending it.
            self.no_schema.add(shape)
            self.no_schema_why = str(e)
            self.log(tr("Structured replies"), tr("{model} wouldn't accept a reply shape ({e}), so its replies are checked after they arrive instead.", model=model, e=_short(str(e), 160)), tr("note"))
            del args["output_config"]
            msg = await self._claude_create(args)
        usage = getattr(msg, "usage", None)
        self._count("Claude", getattr(usage, "input_tokens", 0), getattr(usage, "output_tokens", 0))
        text = "".join(getattr(b, "text", "") or "" for b in msg.content if getattr(b, "type", "text") == "text").strip()
        stop = getattr(msg, "stop_reason", None)
        if not text and stop == "refusal":
            # Claude declined to answer. Asking the same again gets the same answer, so it isn't retried.
            raise RunError(tr("Claude declined to answer this step. Look at what it was given (the step's prompt, in the log or "
                              "the saved log), and word it another way or leave out what it was reading."))
        if not text and stop:
            raise Retryable(tr("Claude returned nothing for this step (it stopped with “{stop}”). Simplify it and try again.", stop=stop))
        return Reply(text, stop in ("max_tokens", "model_context_window_exceeded"))

    @staticmethod
    def _streaming():
        """Stream Claude's text replies? stream = yes/no in second-thought.ini; by default only in an interactive terminal."""
        v = os.environ.get("RB_STREAM", "").strip().lower()
        if v in ("1", "yes", "true", "on"):
            return True
        if v in ("0", "no", "false", "off"):
            return False
        return sys.stdout.isatty()

    async def _claude_create(self, args):
        """One Claude reply, keeping the rate limits its headers report (#270). An SDK without with_raw_response just asks."""
        raw = getattr(self.client.messages, "with_raw_response", None)
        if raw is None:
            return await self.client.messages.create(**args)
        response = await raw.create(**args)
        record_limits("Claude", args.get("model", ""), getattr(response, "headers", {}))
        msg = response.parse()
        return (await msg) if asyncio.iscoroutine(msg) else msg

    async def _claude_stream(self, args):
        """Streams one reply, showing a single progress line that's cleared when it's done. Returns the final message."""
        written, shown, width = 0, 0.0, 0
        async with self.client.messages.stream(**args) as stream:
            async for chunk in stream.text_stream:
                written += len(chunk)
                if time.monotonic() - shown > 0.1:
                    shown = time.monotonic()
                    line = f"    … writing: {written:,} characters"
                    width = max(width, len(line))
                    sys.stdout.write("\r" + line)
                    sys.stdout.flush()
            msg = await stream.get_final_message()
            record_limits("Claude", args.get("model", ""), getattr(getattr(stream, "response", None), "headers", {}))
        if width:
            sys.stdout.write("\r" + " " * width + "\r")
            sys.stdout.flush()
        return msg

    async def _openai_json(self, provider, model, body, schema):
        """Asks for JSON the strongest way this service accepts: the full shape (json_schema), then any JSON
        (json_object), then plain. What works is remembered, and the reply is still checked afterwards."""
        mode = self.json_modes.get((provider, model), "schema") if schema else "none"
        while True:
            if mode == "schema":
                body["response_format"] = {"type": "json_schema", "json_schema": {"name": "reply", "schema": schema, "strict": False}}
            elif mode == "object":
                body["response_format"] = {"type": "json_object"}
            else:
                body.pop("response_format", None)
            try:
                return await asyncio.to_thread(self._openai_request, provider, body)
            except RunError as e:
                if mode == "none" or not ("(400)" in str(e) or "(422)" in str(e)):
                    raise
                mode = self.JSON_MODES[self.JSON_MODES.index(mode) + 1]
                self.json_modes[(provider, model)] = mode
                self.log(tr("Structured replies"), tr("{provider} ({model}) wouldn't take that JSON mode, so it's asked for plain JSON instead." if mode == "object" else
                            "{provider} ({model}) wouldn't take that JSON mode, so it's asked without one, and its replies are checked after they arrive.",
                            provider=provider, model=model),
                         tr("note"), calls=False)

    @staticmethod
    def _openai_request(provider, body, path="/chat/completions"):
        """One request to a model service that speaks OpenAI's format (Ollama, DeepSeek, xAI, OpenAI, Mistral, ...)."""
        pv = PROVIDERS[provider]
        if pv["signup"] and not pv["key"]:
            raise RunError(tr("This program uses {provider}. Put {key_env} = your-key {where_keys} ({signup}).", provider=provider, key_env=pv['key_env'], where_keys=WHERE_KEYS, signup=pv['signup']))
        headers = {"Content-Type": "application/json", **pv["headers"]}
        if pv["key"]:
            headers["Authorization"] = "Bearer " + pv["key"]
        req = urllib.request.Request(pv["base"] + path, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=CALL_TIMEOUT) as r:
                record_limits(provider, body.get("model", ""), r.headers)
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:200]
            if provider == "Llama" and e.code == 404 and "model" in detail.lower():
                raise RunError(tr("The Llama server doesn't have model {model}. Run:  ollama pull {model}", model=body['model']))
            if e.code == 401:
                raise RunError(tr("{provider} refused the API key (401). Check {key_env}.", provider=provider, key_env=pv['key_env']))
            if e.code == 402:
                raise RunError(tr("{provider} says the account has no credit left (402).", provider=provider))
            if e.code in (400, 403, 404, 422):
                raise RunError(tr("{provider} refused the request ({code}): {detail}", provider=provider, code=e.code, detail=detail))
            raise Retryable(tr("{provider} answered {code}: {detail}", provider=provider, code=e.code, detail=detail))
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            hint = " Is Ollama running? Start it with:  ollama serve" if provider == "Llama" else ""
            raise Retryable(tr("Couldn't reach {provider} at {base} ({x}).{hint}", provider=provider, base=pv['base'], x=getattr(e, 'reason', e), hint=hint))

    JSON_MODES = ("schema", "object", "none")

    async def _call_openai(self, provider, model, prompt, picture, history, web, schema=None):
        messages = [{"role": "system", "content": self.instructions}] if self.instructions else []
        messages += [{"role": t["role"], "content": to_str(t["content"])} for t in history or []]
        if web:
            prompt = "You can't browse the web, so answer from what you know and say clearly that it may be out of date.\n\n" + prompt
        if picture is not None and picture.svg is None:
            if model in NO_VISION:
                raise RunError(tr("{model} can't look at photos. Use a model that can, such as DeepSeek Flash or Claude.", model=model))
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
        data = await self._openai_json(provider, model, body, schema)
        usage = data.get("usage") or {}
        self._count(provider, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
        try:
            text = data["choices"][0]["message"]["content"] or ""
            cut = data["choices"][0].get("finish_reason") == "length"
            return Reply(re.sub(r"<think>.*?</think>\s*", "", text, flags=re.S).strip(), cut)  # some models think out loud first
        except (KeyError, IndexError, TypeError, AttributeError):
            return ""

    async def _call_perplexity(self, preset, prompt, picture, history):
        """Perplexity's Agent API: searches the web, then answers with numbered sources."""
        if picture is not None and picture.svg is None:
            raise RunError(tr("Perplexity can't look at photos here. Use Claude, GPT or Gemini for this step."))
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

    GEMINI_WAITS = (5, 15)  # seconds before the second and third tries

    async def _gemini_generate(self, model, contents, config):
        """One Gemini request, given up after CALL_TIMEOUT like every other service's (#329). The client's own timeout
        should end it first; the wait here is a backstop in case it doesn't. A busy answer (408, 429, 5xx, such as
        503 "high demand") or a timeout is tried twice more, as Anthropic's library does for Claude; then it's a
        Retryable, so backups and 'try … times' blocks take over."""
        tries = len(self.GEMINI_WAITS) + 1
        for attempt in range(1, tries + 1):
            try:
                return await asyncio.wait_for(self.gemini.aio.models.generate_content(model=model, contents=contents, config=config),
                                              CALL_TIMEOUT + min(30, CALL_TIMEOUT) if CALL_TIMEOUT else None)
            except Exception as e:  # noqa: BLE001
                code = getattr(e, "code", None) or getattr(e, "status_code", None)
                if isinstance(e, (TimeoutError, asyncio.TimeoutError)) or "Timeout" in type(e).__name__:
                    err = Retryable(tr("Couldn't reach {provider} at {base} ({x}).{hint}", provider="Gemini",
                                       base="generativelanguage.googleapis.com", x=f"{type(e).__name__}, {CALL_TIMEOUT} s", hint=""))
                elif code in (408, 429, 500, 502, 503, 504):
                    err = Retryable(tr("{provider} answered {code}: {detail}", provider="Gemini", code=code, detail=str(e)[:200]))
                else:
                    raise
                if attempt == tries:
                    raise err from e
                wait = self.GEMINI_WAITS[attempt - 1]
                self.log(tr("Retrying"), tr("Try {attempt} of {max_tries} failed: {last_error}\nTrying again in {wait}s.", attempt=attempt,
                                            max_tries=tries, last_error=str(err), wait=wait), tr("retry {x}", x=attempt + 1), calls=False)
                await asyncio.sleep(wait)

    async def _call_gemini(self, model, prompt, picture, history, web, schema=None):
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            raise RunError(tr("This program uses Gemini. Install its package first:  pip install google-genai"))
        if self.gemini is None:
            if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
                raise RunError(tr("Gemini needs a key. Put GEMINI_API_KEY = your-key {where_keys} (https://aistudio.google.com).", where_keys=WHERE_KEYS))
            # google-genai waits forever by default, so a dropped connection stalled the whole program (#329)
            self.gemini = genai.Client(http_options=types.HttpOptions(timeout=int(CALL_TIMEOUT * 1000))) if CALL_TIMEOUT else genai.Client()
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
        json_out = bool(schema) and not web and self.json_modes.get(("Gemini", model)) != "none"
        config = types.GenerateContentConfig(
            system_instruction=self.instructions or None,
            max_output_tokens=MAX_TOKENS,
            tools=[types.Tool(google_search=types.GoogleSearch())] if web else None,
            **({"response_mime_type": "application/json"} if json_out else {}),  # Gemini then writes only JSON
        )
        try:
            resp = await self._gemini_generate(model, contents, config)
        except Exception as e:  # noqa: BLE001
            if not json_out or (getattr(e, "code", None) or getattr(e, "status_code", None)) not in (400, 422):
                raise
            self.json_modes[("Gemini", model)] = "none"
            self.log(tr("Structured replies"), tr("Gemini ({model}) wouldn't take JSON mode, so its replies are checked after they arrive.", model=model),
                     tr("note"), calls=False)
            config.response_mime_type = None
            resp = await self._gemini_generate(model, contents, config)
        um = getattr(resp, "usage_metadata", None)
        self._count("Gemini",
                    getattr(um, "prompt_token_count", None) or getattr(um, "input_tokens", 0),
                    getattr(um, "candidates_token_count", None) or getattr(um, "output_tokens", 0))
        try:
            cands = getattr(resp, "candidates", None) or []
            cut = bool(cands) and "MAX_TOKENS" in str(getattr(cands[0], "finish_reason", ""))
            return Reply((resp.text or "").strip(), cut)
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
