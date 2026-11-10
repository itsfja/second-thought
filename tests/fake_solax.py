"""A stand-in for SolaxCloud's end-user API (#361), serving the sample inverter the page uses
(samples/connections.json, "solax"), shaped the way the API answers: one GET of getRealtimeInfo.do with tokenId and
sn in the query, and a JSON object back with {exception, result, success}.

A wrong token or Registration No. is answered the way SolaxCloud answers it, and each request is recorded in .calls,
so a test can show the five-minute cache at work.

    solax = FakeSolax()
    url = solax.start()        # then SOLAX_API_URL = url, SOLAX_TOKEN_ID = token, SOLAX_SN = ABCDEFGHIJ
    solax.calls
"""
import json
import pathlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOKEN, SN = "20240722185111234567890", "ABCDEFGHIJ"


class FakeSolax:
    def __init__(self, data=None, token=TOKEN, sn=SN):
        self.data = data or json.loads((ROOT / "samples" / "connections.json").read_text(encoding="utf-8"))["solax"]
        self.token, self.sn, self.calls = token, sn, []

    def answer(self, method, path, query):
        if method != "GET" or path != "/getRealtimeInfo.do":
            return 404, {"exception": "not found", "result": None, "success": False}
        if query.get("tokenId") != [self.token] or query.get("sn") != [self.sn]:
            self.calls.append((method, path, "refused", query))
            return 200, {"exception": "SN or Token is incorrect", "result": None, "success": False}
        self.calls.append((method, path, "read", query))
        return 200, self.data

    def start(self):
        solax = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                u = urlparse(self.path)
                status, body = solax.answer(self.command, u.path, parse_qs(u.query))
                payload = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *a):
                pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.stop = server.shutdown
        return f"http://127.0.0.1:{server.server_address[1]}/getRealtimeInfo.do"


if __name__ == "__main__":
    solax = FakeSolax()
    print("Serving on", solax.start())
    threading.Event().wait()
