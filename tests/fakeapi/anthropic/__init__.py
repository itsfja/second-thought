import asyncio, json, os
class _B:
    def __init__(self, t): self.type="text"; self.text=t
class _M:
    def __init__(self, t): self.content=[_B(t)]
class _Messages:
    rev = 0
    async def create(self, model, max_tokens, messages, **kw):
        with open(os.environ.get("FAKE_LOG", os.devnull),"a") as f: f.write("KW " + json.dumps({k: (v if k=="system" else str(v)[:60]) for k,v in kw.items()}) + " turns=" + str(len(messages)) + "\n")
        c = messages[0]["content"]
        img = isinstance(c, list)
        p = c[-1]["text"] if img else c
        with open(os.environ.get("FAKE_LOG", os.devnull),"a") as f: f.write(("IMG " if img else "") + ("" if not img else c[0]["source"]["media_type"]) + "\n")
        with open(os.environ.get("FAKE_LOG", os.devnull),"a") as f: f.write(model+" | "+p[:50].replace("\n"," ")+"\n")
        await asyncio.sleep(0.2)
        if os.environ.get("FAKE_FAIL_ONCE") and not getattr(_Messages, "_failed", False):
            _Messages._failed = True
            return _M("")
        if "SVG" in p and "Reply with only the SVG" in p:
            return _M('Here you go:\n<svg viewBox="0 0 100 80" onload="alert(1)"><script>alert(2)</script><rect width="100" height="80" fill="#c96"/><circle cx="50" cy="40" r="20" fill="#fff" onclick="x()"/></svg>')
        if "JSON array of objects" in p:
            return _M(json.dumps([{"title":"Rye basics","score":4,"why":"x"},{"title":"Rye starter","score":9,"why":"y"}]))
        if '{"approved"' in p:
            _Messages.rev += 1
            return _M(json.dumps({"approved": _Messages.rev % 2 == 0, "problems": [] if _Messages.rev % 2 == 0 else ["too vague"]}))
        if '"answer"' in p: return _M('{"answer": true}')
        if '"number"' in p: return _M('Sure: {"number": 7}')
        if 'JSON array' in p: return _M('```json\n["idea one", "idea two", "idea three"]\n```')
        if '"score"' in p: return _M(json.dumps({"score": 3 + len(p) % 7}))
        if '"pick"' in p: return _M('{"pick": 2, "reason": "clearer"}')
        return _M("TEXT[" + p[:30].replace("\n"," ") + "]")
class AsyncAnthropic:
    def __init__(self): self.messages=_Messages()
