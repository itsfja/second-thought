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
    RunError, WEB_SEARCH_TOOL, _fit, _parse_json, _shape_problem, _short, to_str)
# ---- package only: tools/sync.py leaves everything above this line out of python/runtime.py ----


def _anthropic_client(**kw):
    """The Claude client. Imported when first needed, so the rest of this file loads (and can be tested) without the SDK."""
    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        raise RunError("Claude needs the Anthropic SDK. Install it with:  pip install anthropic") from None
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
# Model names change over time. To use a different model for a tier without editing this file, put
# MODEL_<TIER> = <model name> in second-thought.ini, like  MODEL_OPENAI_DEFAULT = gpt-6.2-sol  or  MODEL_QUICK = claude-haiku-5.
SERVICES = [
    # Check https://docs.claude.com for current model names.
    {"name": "Claude", "menu": "Claude", "api": "anthropic", "prefix": "", "keys": ["ANTHROPIC_API_KEY"],
     "signup": "https://console.anthropic.com", "pip": ["anthropic"], "always": True,
     "tiers": {"quick": ("claude-haiku-4-5-20251001", "Claude, quick", "Quick"),
               "default": ("claude-sonnet-5-5", "Claude, balanced", "Balanced"),
               "complex": ("claude-opus-5-5", "Claude, most capable", "Most capable")}},
    # Gemini: needs  pip install google-genai  and GEMINI_API_KEY. See https://ai.google.dev/gemini-api/docs/models
    {"name": "Gemini", "menu": "Gemini", "api": "gemini", "prefix": "gemini-", "keys": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
     "signup": "https://aistudio.google.com", "pip": ["google-genai"],
     "note": ["Gemini calls go through the Gemini API and are billed to your Google account."],
     "tiers": {"quick": ("gemini-3.5-flash-lite", "Gemini Flash-Lite"), "default": ("gemini-3.8-flash", "Gemini Flash"),
               "complex": ("gemini-3.1-pro-preview", "Gemini Pro")}},
    # Llama: any OpenAI-compatible server. Default is Ollama on this computer: install from https://ollama.com,
    # then  ollama pull llama3.2-vision:11b  (and the others if you use them). See https://ollama.com/library
    # llama-quick is small and fast and runs on most computers; llama-default can look at pictures and needs about
    # 8 GB of graphics memory; llama-complex is Llama 4 Scout and needs a lot of memory.
    {"name": "Llama", "menu": "Llama", "api": "openai", "prefix": "llama-", "base": "http://localhost:11434/v1",
     "base_env": "LLAMA_BASE_URL", "keys": ["LLAMA_API_KEY"], "signup": None,
     "setup": ["Llama runs on any OpenAI-compatible server. By default that's Ollama on this computer:",
               "install it from https://ollama.com, then  ollama pull llama3.2-vision:11b  (see MODELS below).",
               "Elsewhere? Change LLAMA_BASE_URL in second-thought.ini (and LLAMA_API_KEY if the server needs one)."],
     "tiers": {"quick": ("llama3.2:3b", "Llama, small"), "default": ("llama3.2-vision:11b", "Llama, vision"),
               "complex": ("llama4:16x17b", "Llama 4")}},
    # DeepSeek: needs DEEPSEEK_API_KEY (https://platform.deepseek.com). Flash can look at pictures; Pro can't.
    {"name": "DeepSeek", "menu": "DeepSeek", "api": "openai", "prefix": "deepseek-", "base": "https://api.deepseek.com",
     "base_env": "DEEPSEEK_BASE_URL", "keys": ["DEEPSEEK_API_KEY"], "signup": "https://platform.deepseek.com",
     "note": ["DeepSeek calls go to DeepSeek's servers (in China), under DeepSeek's terms, billed to your DeepSeek account."],
     "tiers": {"quick": ("deepseek-flash", "DeepSeek Flash"), "default": ("deepseek-flash", "DeepSeek Flash"),
               "complex": ("deepseek-v4-pro", "DeepSeek V4 Pro")}, "no_vision": ["deepseek-v4-pro"]},
    # xAI (Grok): needs XAI_API_KEY (https://console.x.ai). Both can look at pictures. See https://docs.x.ai/docs/models
    {"name": "xAI", "who": "Grok", "key_label": "Grok (xAI)", "menu": "Grok, from xAI", "api": "openai", "prefix": "xai-",
     "base": "https://api.x.ai/v1", "base_env": "XAI_BASE_URL", "keys": ["XAI_API_KEY"], "signup": "https://console.x.ai",
     "note": ["Grok calls go to xAI's servers, under xAI's terms, billed to your xAI account (https://console.x.ai)."],
     "tiers": {"quick": ("grok-4.3", "Grok 4.3"), "default": ("grok-4.3", "Grok 4.3"), "complex": ("grok-4.7", "Grok 4.7")}},
    # OpenAI: needs OPENAI_API_KEY (https://platform.openai.com). All three can look at pictures.
    # See https://developers.openai.com/api/docs/models
    {"name": "OpenAI", "menu": "OpenAI", "api": "openai", "prefix": "openai-", "base": "https://api.openai.com/v1",
     "base_env": "OPENAI_BASE_URL", "keys": ["OPENAI_API_KEY"], "signup": "https://platform.openai.com",
     "note": ["OpenAI calls go through the OpenAI API and are billed to your OpenAI API account, not a ChatGPT plan."],
     "tiers": {"quick": ("gpt-6-luna", "GPT-6 Luna"), "default": ("gpt-6.1-sol", "GPT-6.1 Sol"),
               "complex": ("gpt-6-astra", "GPT-6 Astra")}},
    # Mistral (France): needs MISTRAL_API_KEY (https://console.mistral.ai). See https://docs.mistral.ai/getting-started/models
    {"name": "Mistral", "menu": "Mistral", "api": "openai", "prefix": "mistral-", "base": "https://api.mistral.ai/v1",
     "base_env": "MISTRAL_BASE_URL", "keys": ["MISTRAL_API_KEY"], "signup": "https://console.mistral.ai",
     "note": ["Mistral calls go to Mistral AI's servers in the EU, billed to your Mistral account (https://console.mistral.ai)."],
     "tiers": {"quick": ("mistral-small-latest", "Mistral Small"), "default": ("mistral-medium-latest", "Mistral Medium"),
               "complex": ("mistral-large-latest", "Mistral Large")}},
    # Qwen (Alibaba Cloud Model Studio): needs DASHSCOPE_API_KEY (https://modelstudio.console.alibabacloud.com).
    # Pictures go to its vision model instead. See https://www.alibabacloud.com/help/en/model-studio/models
    {"name": "Qwen", "menu": "Qwen, from Alibaba", "api": "openai", "prefix": "qwen-",
     "base": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1", "base_env": "QWEN_BASE_URL",
     "keys": ["DASHSCOPE_API_KEY", "QWEN_API_KEY"], "signup": "https://modelstudio.console.alibabacloud.com",
     "note": ["Qwen calls go to Alibaba Cloud Model Studio (international region; set QWEN_BASE_URL for another), billed to your Alibaba Cloud account."],
     "tiers": {"quick": ("qwen3.8-flash", "Qwen Flash"), "default": ("qwen3.7-plus", "Qwen Plus"),
               "complex": ("qwen3.8-max", "Qwen Max")}, "vision": ("QWEN_VISION_MODEL", "qwen3-vl-plus")},
    # Kimi (Moonshot AI): needs MOONSHOT_API_KEY (https://platform.moonshot.ai). Both can look at pictures.
    {"name": "Kimi", "menu": "Kimi, from Moonshot", "api": "openai", "prefix": "kimi-", "base": "https://api.moonshot.ai/v1",
     "base_env": "MOONSHOT_BASE_URL", "keys": ["MOONSHOT_API_KEY", "KIMI_API_KEY"], "signup": "https://platform.moonshot.ai",
     "note": ["Kimi calls go to Moonshot AI's servers (a Chinese company), under Moonshot's terms, billed to your Moonshot account."],
     "tiers": {"quick": ("kimi-k2.6", "Kimi K2.6"), "default": ("kimi-k2.6", "Kimi K2.6"), "complex": ("kimi-k3", "Kimi K3")}},
    # Perplexity: needs PERPLEXITY_API_KEY (https://www.perplexity.ai/account/api). Always searches the web and
    # lists its sources. These are Agent API presets, not model names. See https://docs.perplexity.ai
    {"name": "Perplexity", "menu": "Perplexity, searches the web", "api": "perplexity", "prefix": "perplexity-",
     "base": "https://api.perplexity.ai", "base_env": "PERPLEXITY_BASE_URL", "keys": ["PERPLEXITY_API_KEY"],
     "signup": "https://www.perplexity.ai/account/api",
     "note": ["Perplexity searches the web for every step it answers and lists its sources; billed to your Perplexity API account."],
     "tiers": {"quick": ("fast", "Perplexity, fast"), "default": ("low", "Perplexity, research"),
               "complex": ("high", "Perplexity, deep research")}},
    # Hugging Face: open models run by Hugging Face's partners. Needs HF_TOKEN (https://huggingface.co/settings/tokens).
    # Any model name from https://huggingface.co/models?inference_provider=all works here.
    {"name": "Hugging Face", "menu": "Open models on Hugging Face", "api": "openai", "prefix": "hf-",
     "base": "https://router.huggingface.co/v1", "base_env": "HF_BASE_URL", "keys": ["HF_TOKEN", "HUGGINGFACE_API_KEY"],
     "signup": "https://huggingface.co/settings/tokens",
     "note": ["Hugging Face passes open-model calls to one of its partner services; billed to your Hugging Face account. Any model from huggingface.co works: edit MODELS below."],
     "tiers": {"quick": ("google/gemma-4-26B-A4B-it", "Gemma 4, small"), "default": ("google/gemma-4-31B-it", "Gemma 4"),
               "complex": ("openai/gpt-oss-120b", "GPT-OSS 120B")}, "vision": ("HF_VISION_MODEL", "google/gemma-4-31B-it")},
    # Groq: open models, very fast. Needs GROQ_API_KEY (https://console.groq.com). See https://console.groq.com/docs/models
    {"name": "Groq", "menu": "Groq, very fast", "api": "openai", "prefix": "groq-", "base": "https://api.groq.com/openai/v1",
     "base_env": "GROQ_BASE_URL", "keys": ["GROQ_API_KEY"], "signup": "https://console.groq.com",
     "note": ["Groq calls go to Groq's servers (US), billed to your Groq account. Groq has a free tier with rate limits."],
     "tiers": {"quick": ("llama-3.1-8b-instant", "Llama 3.1 8B (Groq)"), "default": ("llama-3.3-70b-versatile", "Llama 3.3 70B (Groq)"),
               "complex": ("openai/gpt-oss-120b", "GPT-OSS 120B (Groq)")}, "vision": ("GROQ_VISION_MODEL", "qwen/qwen3.8-27b")},
    # GLM (Z.ai, formerly Zhipu): needs ZAI_API_KEY (https://z.ai/manage-apikey/apikey-list). Both can look at pictures.
    {"name": "GLM", "menu": "GLM, from Z.ai", "api": "openai", "prefix": "glm-", "base": "https://api.z.ai/api/paas/v4",
     "base_env": "ZAI_BASE_URL", "keys": ["ZAI_API_KEY", "ZHIPUAI_API_KEY"], "signup": "https://z.ai/manage-apikey/apikey-list",
     "note": ["GLM calls go to Z.ai (formerly Zhipu AI, a Chinese company), under Z.ai's terms, billed to your Z.ai account."],
     "tiers": {"quick": ("glm-5.3-flash", "GLM-5.3 Flash"), "default": ("glm-5.3-flash", "GLM-5.3 Flash"),
               "complex": ("glm-5.3", "GLM-5.3")}},
    # MiniMax: needs MINIMAX_API_KEY (https://platform.minimax.io). M3 can look at pictures; M2.7 can't.
    {"name": "MiniMax", "menu": "MiniMax", "api": "openai", "prefix": "minimax-", "base": "https://api.minimax.io/v1",
     "base_env": "MINIMAX_BASE_URL", "keys": ["MINIMAX_API_KEY"], "signup": "https://platform.minimax.io",
     "note": ["MiniMax calls go to MiniMax's international servers (a Chinese company), under MiniMax's terms, billed to your MiniMax account."],
     "tiers": {"quick": ("MiniMax-M2.7-highspeed", "MiniMax M2.7"), "default": ("MiniMax-M3", "MiniMax M3"),
               "complex": ("MiniMax-M3", "MiniMax M3")}, "no_vision": ["MiniMax-M2.7-highspeed"]},
    # OpenRouter: one key for hundreds of models (https://openrouter.ai/keys). openrouter/auto picks a model for each
    # step. For one particular model use the "with OpenRouter model" block, or a tier like "openrouter:mistralai/..."
    # with any name from https://openrouter.ai/models
    {"name": "OpenRouter", "menu": "OpenRouter, hundreds of models", "api": "openai", "prefix": "openrouter-",
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


def model_label(tier):
    if str(tier).startswith("openrouter:"):
        return "OpenRouter: " + tier.split(":", 1)[1]
    return MODEL_LABELS.get(tier, tier)


class ModelCalls:
    """Calling the model services. Part of Runtime (see runtime.py)."""
    async def _call_live(self, prompt, want_json=False, picture=None, history=None, web=False):
        if self.ending:
            raise asyncio.CancelledError()
        self.calls += 1
        if self.calls > MAX_AI_CALLS:
            raise RunError(f"Stopped after {MAX_AI_CALLS} model calls in one run, to protect your usage.")
        if self.budget and self.tokens_used() >= self.budget:
            raise RunError(f"Stopped: this run has used {self.tokens_used():,} tokens, which reaches its budget of {self.budget:,}. "
                           "Raise the number in the 'limit this run' block (or budget in second-thought.ini).")
        tier = self.current_tier
        # Backups stand in for the primary model only. A block that names its own model keeps that model.
        tiers = [tier] + (self.backups if tier == self.primary else [])
        last = None
        for n, t in enumerate(tiers):
            if n:
                self.log("Backup", f"{model_label(tiers[n - 1])} failed: {str(last)[:160]}\nTrying {model_label(t)} instead.", "warn", calls=False)
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
                self.log("Unreadable reply", f"{e}\nAsking once more for a corrected reply.", "repair", calls=False)
                self.calls += 1
                if self.calls > MAX_AI_CALLS:
                    raise RunError(f"Stopped after {MAX_AI_CALLS} model calls in one run, to protect your usage.")
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
        self.log("Reply continued", "The reply reached the length limit, so the model was asked to carry on from where it stopped.",
                 "continued", calls=False)
        self.calls += 1
        if self.calls > MAX_AI_CALLS:
            raise RunError(f"Stopped after {MAX_AI_CALLS} model calls in one run, to protect your usage.")
        turns = (history or []) + [{"role": "user", "content": to_str(prompt)}, {"role": "assistant", "content": to_str(text)}]
        more = await self._timed_call(tier, CONTINUE_PROMPT, False, None, turns, web)
        joined = to_str(text) + to_str(more)  # the continuation picks up exactly where the first part stopped
        if getattr(more, "truncated", False):
            self.out_of_rounds_hit = True
            self.log("Cut short", "Even after carrying on, the reply was still too long, so it stops part-way. It's kept as it is, marked best effort. "
                     "Ask for something shorter, or split the job into smaller steps.", "warn", calls=False)
        return joined

    @staticmethod
    def _read_json(text, schema):
        """Parses a reply and checks it against the schema. Raises BadJSON with a plain reason."""
        v = _parse_json(text)
        if schema:
            v = _fit(v, schema)
            bad = _shape_problem(v, schema)
            if bad:
                raise BadJSON(f"The reply didn't have the expected shape: {bad}.")
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
            raise Retryable(f"{who} returned nothing for this step. Simplify it and try again.")
        return text

    async def _call_claude(self, model, prompt, picture, history, web, schema=None):
        if self.client is None:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise RunError(f"Claude needs a key. Put ANTHROPIC_API_KEY = your-key {WHERE_KEYS} (https://console.anthropic.com).")
            self.client = _anthropic_client(timeout=CALL_TIMEOUT, max_retries=2)
        args = dict(model=model, max_tokens=MAX_TOKENS,
                    messages=(history or []) + [{"role": "user", "content": self._content(prompt, picture)}])
        if self.instructions:
            args["system"] = self.instructions
        if web:
            args["tools"] = [WEB_SEARCH_TOOL]
        if schema and not web and model not in self.no_schema:
            # Structured outputs: Claude can only write JSON of this shape. https://platform.claude.com/docs/en/build-with-claude/structured-outputs
            args["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
        try:
            msg = await (self._claude_stream(args) if "output_config" not in args and self._streaming() else self.client.messages.create(**args))
        except Exception as e:  # noqa: BLE001
            if "output_config" not in args or getattr(e, "status_code", None) != 400:
                raise
            # This model or account won't take the shape: ask without it (the reply is still checked), and stop sending it.
            self.no_schema.add(model)
            self.log("Structured replies", f"{model} wouldn't accept a reply shape ({_short(str(e), 160)}), so its replies "
                     "are checked after they arrive instead.", "note")
            del args["output_config"]
            msg = await self.client.messages.create(**args)
        usage = getattr(msg, "usage", None)
        self._count("Claude", getattr(usage, "input_tokens", 0), getattr(usage, "output_tokens", 0))
        text = "".join(getattr(b, "text", "") or "" for b in msg.content if getattr(b, "type", "text") == "text").strip()
        return Reply(text, getattr(msg, "stop_reason", None) in ("max_tokens", "model_context_window_exceeded"))

    @staticmethod
    def _streaming():
        """Stream Claude's text replies? stream = yes/no in second-thought.ini; by default only in an interactive terminal."""
        v = os.environ.get("RB_STREAM", "").strip().lower()
        if v in ("1", "yes", "true", "on"):
            return True
        if v in ("0", "no", "false", "off"):
            return False
        return sys.stdout.isatty()

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
                self.log("Structured replies", f"{provider} ({model}) wouldn't take that JSON mode, so it's asked "
                         + ("for plain JSON instead." if mode == "object" else "without one, and its replies are checked after they arrive."),
                         "note", calls=False)

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
            with urllib.request.urlopen(req, timeout=CALL_TIMEOUT) as r:
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

    JSON_MODES = ("schema", "object", "none")

    async def _call_openai(self, provider, model, prompt, picture, history, web, schema=None):
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

    async def _call_gemini(self, model, prompt, picture, history, web, schema=None):
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
        json_out = bool(schema) and not web and self.json_modes.get(("Gemini", model)) != "none"
        config = types.GenerateContentConfig(
            system_instruction=self.instructions or None,
            max_output_tokens=MAX_TOKENS,
            tools=[types.Tool(google_search=types.GoogleSearch())] if web else None,
            **({"response_mime_type": "application/json"} if json_out else {}),  # Gemini then writes only JSON
        )
        try:
            resp = await self.gemini.aio.models.generate_content(model=model, contents=contents, config=config)
        except Exception as e:  # noqa: BLE001
            if not json_out or (getattr(e, "code", None) or getattr(e, "status_code", None)) not in (400, 422):
                raise
            self.json_modes[("Gemini", model)] = "none"
            self.log("Structured replies", f"Gemini ({model}) wouldn't take JSON mode, so its replies are checked after they arrive.",
                     "note", calls=False)
            config.response_mime_type = None
            resp = await self.gemini.aio.models.generate_content(model=model, contents=contents, config=config)
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
