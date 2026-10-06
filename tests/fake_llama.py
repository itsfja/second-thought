"""A tiny stand-in for an OpenAI-compatible Llama server (like Ollama), for the tests."""
import asyncio
import json
import pathlib
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "fakeapi"))
from anthropic import _Messages  # noqa: E402  (shared fake replies)


def start():
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            last = body["messages"][-1]["content"]
            text = last if isinstance(last, str) else " ".join(p.get("text", "") for p in last if p.get("type") == "text")
            calls.append({"model": body.get("model"), "image": not isinstance(last, str),
                          "system": body["messages"][0]["role"] == "system"})
            msg = asyncio.run(_Messages().create(model=body.get("model"), max_tokens=0, messages=[{"role": "user", "content": text}]))
            out = json.dumps({"choices": [{"message": {"role": "assistant", "content": msg.content[0].text}}],
                              "usage": {"prompt_tokens": 12, "completion_tokens": 6}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_port}/v1", calls
