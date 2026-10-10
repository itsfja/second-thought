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
# Model names change over time. To use a different model for a tier without editing this file, put
# MODEL_<TIER> = <model name> in second-thought.ini, like  MODEL_OPENAI_DEFAULT = gpt-6.2-sol  or  MODEL_QUICK = claude-haiku-5.
for _tier in list(MODELS):
    _name = os.environ.get("MODEL_" + _tier.upper().replace("-", "_"), "").strip()
    if _name:
        MODELS[_tier] = _name
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
