"""A tiny stand-in for Home Assistant's REST and WebSocket APIs, serving the same sample house the page uses."""
import base64
import datetime
import hashlib
import json
import pathlib
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOKEN = "test-token"
subscribers = []  # [(send function, event type or None)] for every WebSocket subscription
_lock = threading.Lock()  # guards subscribers
ws_log = []  # (seconds, connection number, what happened) for every WebSocket connection, to explain a failing test
_t0 = time.time()


def _note(conn, what):
    ws_log.append((round(time.time() - _t0, 1), conn, what))


def fire_event(event_type, data):
    """Sends an event to every WebSocket subscriber that asked for this type (or for everything). Gives how many got it."""
    with _lock:
        subs = [s for s in subscribers if s[1] in (None, event_type)]
    sent = 0
    for send, _ in subs:
        try:
            _note(getattr(send, "conn", 0), "sending " + event_type)
            send({"type": "event", "event": {"event_type": event_type, "data": data, "origin": "LOCAL",
                                              "time_fired": datetime.datetime.now(datetime.timezone.utc).isoformat()}})
            sent += 1
        except OSError:
            pass
    return sent


def _frame(payload, opcode=1):
    n = len(payload)
    head = bytes([0x80 | opcode]) + (bytes([n]) if n < 126 else bytes([126]) + n.to_bytes(2, "big") if n < 65536 else bytes([127]) + n.to_bytes(8, "big"))
    return head + payload


def _read_frame(sock_file):
    b0, b1 = sock_file.read(2)
    n = b1 & 0x7F
    if n == 126:
        n = int.from_bytes(sock_file.read(2), "big")
    elif n == 127:
        n = int.from_bytes(sock_file.read(8), "big")
    mask = sock_file.read(4)
    data = bytes(b ^ mask[i % 4] for i, b in enumerate(sock_file.read(n)))
    return b0 & 0x0F, data


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

        def _websocket(self):
            key = self.headers.get("Sec-WebSocket-Key", "")
            accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
            self.send_response(101)
            self.send_header("Upgrade", "websocket")
            self.send_header("Connection", "Upgrade")
            self.send_header("Sec-WebSocket-Accept", accept)
            self.end_headers()
            out_lock = threading.Lock()

            def send(obj):
                with out_lock:
                    self.wfile.write(_frame(json.dumps(obj).encode()))
                    self.wfile.flush()
            send.conn = conn = len({c for _, c, _ in ws_log}) + 1
            _note(conn, "connected")
            mine = []
            try:
                send({"type": "auth_required", "ha_version": "2026.10.0"})
                op, data = _read_frame(self.rfile)
                if json.loads(data).get("access_token") != TOKEN:
                    send({"type": "auth_invalid", "message": "Invalid access token or password"})
                    _note(conn, "refused the token")
                    return
                send({"type": "auth_ok", "ha_version": "2026.10.0"})
                _note(conn, "signed in")
                while True:
                    op, data = _read_frame(self.rfile)
                    if op == 8:
                        return
                    msg = json.loads(data)
                    if msg.get("type") == "subscribe_events":
                        sub = (send, msg.get("event_type"))
                        with _lock:
                            subscribers.append(sub)
                        mine.append(sub)
                        _note(conn, "subscribed to " + str(msg.get("event_type") or "everything"))
                        send({"id": msg["id"], "type": "result", "success": True, "result": None})
            except (OSError, ValueError) as e:
                _note(conn, "closed: " + type(e).__name__)
                return
            finally:
                with _lock:
                    for sub in mine:
                        if sub in subscribers:
                            subscribers.remove(sub)

        def do_GET(self):
            if urlparse(self.path).path == "/api/websocket" and self.headers.get("Upgrade", "").lower() == "websocket":
                return self._websocket()  # signs in with a message, not a header, like Home Assistant
            if not self._authorised():
                return
            url = urlparse(self.path)
            path = unquote(url.path)
            if path == "/api/":
                return self._send(200, {"message": "API running."})
            if path == "/api/config":
                return self._send(200, {"version": "2026.10.0", "location_name": "Sample house"})
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
