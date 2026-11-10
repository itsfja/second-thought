"""A stand-in for a Tesla Powerwall gateway's local API (#362), serving the sample the page uses
(samples/connections.json, "powerwall"), shaped the way the gateway answers: a login at /api/login/Basic that checks
the customer password and gives a Bearer token, then the four reads the runtime makes, and /api/operation as the one
thing it accepts a write on.

A wrong password is answered 401, a wrong Bearer token 401 (so a re-login can be tested), and each request is
recorded in .calls, so a test can show only the calls in SAFETY were ever made. The reserve change is kept in
.operation, so a test can see it happened.

    pw = FakePowerwall()
    url = pw.start()          # then POWERWALL_URL = url, POWERWALL_PASSWORD = secret
    pw.calls, pw.data["operation"]["backup_reserve_percent"]
"""
import json
import pathlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parent.parent
PASSWORD = "secret"


class FakePowerwall:
    def __init__(self, data=None, password=PASSWORD):
        self.data = data or json.loads((ROOT / "samples" / "connections.json").read_text(encoding="utf-8"))["powerwall"]
        self.password, self.calls, self.token, self.reserve = password, [], "a-token", 20

    def answer(self, method, path, body):
        if method == "POST" and path == "/api/login/Basic":
            ok = isinstance(body, dict) and body.get("username") == "customer" and body.get("password") == self.password
            self.calls.append((method, path, "login" if ok else "refused"))
            return (200, {"token": self.token}) if ok else (401, {})
        if path not in ("/api/meters/aggregates", "/api/system_status/soe", "/api/system_status/grid_status", "/api/operation"):
            self.calls.append((method, path, "not allowed"))
            return (404, {})
        if method == "GET":
            self.calls.append((method, path, "read"))
            return 200, self.data[
                {"/api/meters/aggregates": "meters_aggregates", "/api/system_status/soe": "system_status_soe",
                 "/api/system_status/grid_status": "system_status_grid_status", "/api/operation": "operation"}[path]]
        if method == "POST" and path == "/api/operation":  # the one change the runtime may make, after a yes
            if not isinstance(body, dict) or set(body) - {"backup_reserve_percent"} or not str(body.get("backup_reserve_percent", "")).isdigit():
                self.calls.append((method, path, "not allowed"))
                return (400, {})
            self.calls.append((method, path, "write"))
            self.reserve = int(body["backup_reserve_percent"])
            self.data["operation"]["backup_reserve_percent"] = str(self.reserve)
            return (200, {})
        self.calls.append((method, path, "not allowed"))
        return (405, {})

    def start(self, check_token=True):
        pw = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                try:
                    body = json.loads(self.rfile.read(length) or b"null")
                except ValueError:
                    body = None
                self.go("POST", body)

            def do_GET(self):
                self.go("GET", None)

            def go(self, method, body):
                if check_token and not (self.path == "/api/login/Basic" and method == "POST"):
                    if self.headers.get("Authorization") != "Bearer " + pw.token:
                        pw.calls.append((method, self.path, "bad token"))
                        self.reply(401, {})
                        return
                status, out = pw.answer(method, self.path, body)
                self.reply(status, out)

            def reply(self, status, out):
                payload = json.dumps(out).encode()
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
        return f"http://127.0.0.1:{server.server_address[1]}"


if __name__ == "__main__":
    pw = FakePowerwall()
    print("Serving on", pw.start())
    threading.Event().wait()
