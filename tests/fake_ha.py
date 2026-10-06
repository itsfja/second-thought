"""A tiny stand-in for Home Assistant's REST API, serving the same sample house the page uses."""
import datetime
import json
import pathlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOKEN = "test-token"


def start():
    house = json.loads((ROOT / "ha" / "sample-house.json").read_text(encoding="utf-8"))
    states = {e["entity_id"]: e for e in house["entities"]}
    picture = (ROOT / "tests" / "fixtures" / "crumb.png").read_bytes()
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _authorised(self):
            if self.headers.get("Authorization") != "Bearer " + TOKEN:
                self._send(401, {"message": "Unauthorized"})
                return False
            return True

        def do_GET(self):
            if not self._authorised():
                return
            url = urlparse(self.path)
            path = unquote(url.path)
            if path == "/api/states":
                return self._send(200, list(states.values()))
            if path.startswith("/api/states/"):
                e = states.get(path[len("/api/states/"):])
                return self._send(200, e) if e else self._send(404, {"message": "Entity not found."})
            if path.startswith("/api/history/period/"):
                eid = dict(p.split("=", 1) for p in url.query.split("&") if "=" in p).get("filter_entity_id", "")
                e = states.get(unquote(eid))
                if not e:
                    return self._send(200, [])
                now = datetime.datetime.now(datetime.timezone.utc)
                rows = [{"state": e["state"], "last_changed": (now - datetime.timedelta(hours=h)).isoformat()} for h in (6, 4, 2, 0)]
                return self._send(200, [rows])
            if path.startswith("/api/camera_proxy/"):
                return self._send(200, picture, "image/png")
            self._send(404, {"message": "Not found"})

        def do_POST(self):
            if not self._authorised():
                return
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
            path = urlparse(self.path).path
            if path.startswith("/api/services/"):
                domain, service = path[len("/api/services/"):].split("/", 1)
                calls.append((domain + "." + service, body))
                e = states.get(body.get("entity_id", ""))
                if e is not None:
                    e["state"] = {"turn_on": "on", "turn_off": "off", "lock": "locked", "unlock": "unlocked"}.get(service, e["state"])
                return self._send(200, [])
            self._send(404, {"message": "Not found"})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_port}", calls
