"""A tiny stand-in for an OpenAI-compatible server (Ollama, DeepSeek, xAI, OpenAI, Mistral, Qwen, Kimi, Perplexity), for the tests."""
import asyncio
import json
import pathlib
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "fakeapi"))
from anthropic import _Messages  # noqa: E402  (shared fake replies)


REFUSE_JSON = set()  # JSON modes this stand-in refuses with a 400, like a service that doesn't support them ("json_schema", "json_object")


def start():
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            """GET .../models: the list --doctor reads to try a key. A key of "bad" is refused, like a wrong key."""
            if not self.path.split("?")[0].rstrip("/").endswith("/models"):
                self.send_response(404)
                self.end_headers()
                return
            key = (self.headers.get("Authorization") or "").replace("Bearer ", "") or self.headers.get("x-api-key") or self.headers.get("x-goog-api-key") or ""
            if key == "bad":
                self.send_response(401)
                self.end_headers()
                return
            ids = ["llama3.2:3b", "llama3.2-vision:11b", "deepseek-flash", "grok-4.3", "gpt-6.1-sol", "claude-sonnet-5-5", "claude-haiku-4-5-20251001"]
            out = json.dumps({"data": [{"id": i} for i in ids], "models": [{"name": "models/gemini-3.8-flash"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            if self.path.rstrip("/").endswith("/agent"):
                # Perplexity's Agent API: one input string, an answer plus the web pages it found.
                calls.append({"model": "perplexity:" + str(body.get("preset")), "image": False, "system": "instructions" in body})
                msg = asyncio.run(_Messages().create(model="sonar", max_tokens=0, messages=[{"role": "user", "content": body.get("input", "")}]))
                out = json.dumps({"status": "completed", "output_text": msg.content[0].text, "output": [
                    {"type": "search_results", "queries": ["test"], "results": [
                        {"id": 1, "title": "A test page", "url": "https://example.com/test", "snippet": "..."}]},
                    {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": msg.content[0].text}]}],
                    "usage": {"input_tokens": 20, "output_tokens": 9}}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)
                return
            last = body["messages"][-1]["content"]
            text = last if isinstance(last, str) else " ".join(p.get("text", "") for p in last if p.get("type") == "text")
            rf = (body.get("response_format") or {}).get("type")
            calls.append({"model": body.get("model"), "image": not isinstance(last, str),
                          "system": body["messages"][0]["role"] == "system", "json": rf})
            if rf and rf in REFUSE_JSON:
                # Like a service that doesn't support this JSON mode.
                err = json.dumps({"error": {"message": f"response_format type '{rf}' is not supported"}}).encode()
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err)))
                self.end_headers()
                self.wfile.write(err)
                return
            if str(body.get("model", "")).startswith("gpt-") and "max_tokens" in body:
                # Like the real OpenAI API: newer GPT models only accept max_completion_tokens.
                err = json.dumps({"error": {"message": "Unsupported parameter: 'max_tokens'. Use 'max_completion_tokens' instead."}}).encode()
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err)))
                self.end_headers()
                self.wfile.write(err)
                return
            msg = asyncio.run(_Messages().create(model=body.get("model"), max_tokens=0, messages=[{"role": "user", "content": text}]))
            reply = msg.content[0].text
            if str(body.get("model", "")).startswith("MiniMax"):
                reply = "<think>Some private reasoning that must not reach the user.</think>\n" + reply  # like MiniMax M2.x
            out = json.dumps({"choices": [{"message": {"role": "assistant", "content": reply}}],
                              "usage": {"prompt_tokens": 12, "completion_tokens": 6}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_port}/v1", calls
