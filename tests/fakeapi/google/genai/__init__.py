"""Test stand-in for the google-genai SDK. Replies come from the fake Anthropic
stand-in, so both providers answer the same way in tests."""
import json
import os
from types import SimpleNamespace

from . import types  # noqa: F401  (imported as google.genai.types by the runtime)


class _Models:
    async def generate_content(self, model, contents, config=None):
        from anthropic import _Messages  # the shared fake reply logic
        last = contents[-1]
        text = " ".join(p.text for p in last.parts if p.text)
        has_image = any(p.data for p in last.parts)
        with open(os.environ.get("FAKE_LOG", os.devnull), "a") as f:
            f.write("GEMINI " + json.dumps({"model": model, "turns": len(contents), "image": has_image,
                                            "system": getattr(config, "system_instruction", None),
                                            "search": bool(getattr(config, "tools", None)),
                                            "json": getattr(config, "response_mime_type", None)}) + "\n")
        msg = await _Messages().create(model=model, max_tokens=0, messages=[{"role": "user", "content": text}])
        return SimpleNamespace(text=msg.content[0].text,
                               usage_metadata=SimpleNamespace(prompt_token_count=10, candidates_token_count=5))


class Client:
    def __init__(self, *a, **kw):
        self.aio = SimpleNamespace(models=_Models())
