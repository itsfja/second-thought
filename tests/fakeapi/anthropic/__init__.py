import asyncio, json, os
class _B:
    def __init__(self, t): self.type="text"; self.text=t
class _U:
    def __init__(self, t): self.input_tokens=120; self.output_tokens=len(t)//4+1
class _M:
    def __init__(self, t): self.content=[_B(t)]; self.usage=_U(t)
class BadRequestError(Exception):
    status_code = 400
def _check_schema(sc, path="schema"):
    """What the real API refuses: a root that isn't an object, or an object with properties but extra keys allowed."""
    if path == "schema" and sc.get("type") != "object":
        raise BadRequestError(f"{path}: the root must be an object")
    if sc.get("type") == "object" and sc.get("properties") and sc.get("additionalProperties") is not False:
        raise BadRequestError(f"{path}: objects need additionalProperties: false")
    for k, v in (sc.get("properties") or {}).items():
        _check_schema(v, path + "." + k)
    if isinstance(sc.get("items"), dict):
        _check_schema(sc["items"], path + "[]")
    for v in sc.get("anyOf", []):
        _check_schema(v, path + "|")
class _Messages:
    rev = 0
    scripted = 0
    async def create(self, model, max_tokens, messages, **kw):
        oc = kw.get("output_config")
        if oc:
            if os.environ.get("FAKE_REJECT_SCHEMA"):
                raise BadRequestError("output_config: this model does not support structured outputs (test)")
            assert oc["format"]["type"] == "json_schema", oc
            _check_schema(oc["format"]["schema"])
            with open(os.environ.get("FAKE_LOG", os.devnull), "a") as f: f.write("SCHEMA ok\n")
            script = json.loads(os.environ.get("FAKE_JSON_SCRIPT") or "null")
            if script and _Messages.scripted < len(script):  # a test's script of raw replies for JSON requests
                _Messages.scripted += 1
                return _M(script[_Messages.scripted - 1])
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
        if "one step at a time, using tools" in p:
            import re
            steps = len(re.findall(r"\nStep \d+: ", p))
            script = json.loads(os.environ.get("FAKE_AGENT_SCRIPT") or "null")
            if script:  # a test's script: one reply per step; "BAD" is an unreadable reply
                r = script[min(steps, len(script) - 1)]
                return _M("this is not json at all" if r == "BAD" else json.dumps(r))
            m = re.search(r"TOOLS:\n- ([a-z0-9_]+)\(([^)]*)\)", p)
            if steps or not m or "This is your last step" in p:
                return _M(json.dumps({"done": True, "answer": f"AGENT ANSWER after {steps} step(s)"}))
            keys = [k.strip() for k in m.group(2).split(",") if k.strip()]
            r = {"tool": m.group(1), "input": {k: str(500 + i * 350) for i, k in enumerate(keys)}, "why": "test"}
            if "Planning is on" in p:
                r["plan"] = ["test plan step"]
            return _M(json.dumps(r))
        if "SVG" in p and "Reply with only the SVG" in p:
            return _M('Here you go:\n<svg viewBox="0 0 100 80" onload="alert(1)"><script>alert(2)</script><rect width="100" height="80" fill="#c96"/><circle cx="50" cy="40" r="20" fill="#fff" onclick="x()"/></svg>')
        if '"items": [<objects' in p:
            return _M(json.dumps([{"title":"Rye basics","score":4,"why":"x"},{"title":"Rye starter","score":9,"why":"y"}]))
        if '{"approved"' in p:
            _Messages.rev += 1
            return _M(json.dumps({"approved": _Messages.rev % 2 == 0, "problems": [] if _Messages.rev % 2 == 0 else ["too vague"]}))
        if '"answer"' in p: return _M('{"answer": true}')
        if '"number"' in p: return _M('Sure: {"number": 7}')
        if '"items": [<short strings>]' in p: return _M('```json\n["idea one", "idea two", "idea three"]\n```')
        if '"score"' in p: return _M(json.dumps({"score": 3 + len(p) % 7}))
        if '"pick"' in p: return _M('{"pick": 2, "reason": "clearer"}')
        return _M("TEXT[" + p[:30].replace("\n"," ") + "]")
class AsyncAnthropic:
    def __init__(self): self.messages=_Messages()
