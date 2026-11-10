"""A stand-in for Proxmox VE's REST API (#357), serving the sample cluster the page uses (samples/connections.json,
"proxmox"), shaped the way Proxmox answers ({"data": ...}).

It checks the API token (PVEAPIToken=user@pam!test=secret), answers the reads, and records power actions in .powered
(as "start 104"). Anything else is recorded in .refused and answered 501, so a test can show nothing else was sent.
With tls=True it serves HTTPS with a new self-signed certificate, as a Proxmox node does; .fingerprint is its SHA-256.
With can_power=False the token is an auditor's, and a power action is answered 403.

    pve = FakeProxmox()
    url = pve.start()          # then PROXMOX_URL = url, PROXMOX_TOKEN_ID = fake_proxmox.TOKEN_ID, PROXMOX_TOKEN_SECRET = fake_proxmox.SECRET
"""
import hashlib
import json
import pathlib
import re
import ssl
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOKEN_ID, SECRET = "monitor@pve!second-thought", "11111111-2222-3333-4444-555555555555"
API = "/api2/json"


class FakeProxmox:
    def __init__(self, tls=False, data=None, can_power=True, permissions=None):
        self.data = data or json.loads((ROOT / "samples" / "connections.json").read_text(encoding="utf-8"))["proxmox"]
        if permissions is not None:
            self.data = dict(self.data, permissions=permissions)
        self.tls, self.can_power = tls, can_power
        self.calls, self.refused, self.powered = [], [], []
        self.fingerprint = None

    def answer(self, method, path, query):
        d = self.data
        if method == "GET":
            if path == f"{API}/version":
                return 200, d["version"]
            if path == f"{API}/access/permissions":
                return 200, d["permissions"]
            if path == f"{API}/nodes":
                return 200, d["nodes"]
            if path == f"{API}/cluster/resources":
                kind = query.get("type", [""])[0]
                if kind == "vm":
                    return 200, [{k: v for k, v in g.items() if k != "onboot"} | {"id": f"{g['type']}/{g['vmid']}"} for g in d["guests"]]
                if kind == "storage":
                    return 200, [dict(s, id=f"storage/{s['node']}/{s['storage']}", type="storage") for s in d["storage"]]
            if path == f"{API}/cluster/tasks":
                now = int(time.time())
                return 200, [{k: v for k, v in t.items() if k not in ("ago", "took")} | {"starttime": now - t["ago"], "endtime": now - t["ago"] + t["took"],
                             "upid": f"UPID:{t['node']}:0000:{t['type']}:{t['id']}:"} for t in d["tasks"]]
            m = re.fullmatch(rf"{API}/nodes/([\w.-]+)/(qemu|lxc)/(\d+)/config", path)
            if m:
                g = next((g for g in d["guests"] if g["vmid"] == int(m[3]) and g["node"] == m[1] and g["type"] == m[2]), None)
                return (200, {"name": g["name"], "onboot": g.get("onboot", 0)}) if g else (500, {"message": "no such guest"})
        m = re.fullmatch(rf"{API}/nodes/([\w.-]+)/(qemu|lxc)/(\d+)/status/(start|shutdown|reboot)", path)
        if method == "POST" and m:
            if not self.can_power:
                return 403, {"message": "Permission check failed (/vms/" + m[3] + ", VM.PowerMgmt)"}
            self.powered.append(f"{m[4]} {m[3]}")
            return 200, f"UPID:{m[1]}:0000:{m[4]}:{m[3]}:"
        self.refused.append(f"{method} {path}")
        return 501, {"message": "not in the stand-in"}

    def start(self):
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _go(self, method):
                u = urlparse(self.path)
                if method != "GET":
                    self.rfile.read(int(self.headers.get("Content-Length") or 0))
                fake.calls.append(f"{method} {u.path}")
                if self.headers.get("Authorization") != f"PVEAPIToken={TOKEN_ID}={SECRET}":
                    status, out = 401, None
                else:
                    status, out = fake.answer(method, u.path, parse_qs(u.query))
                data = json.dumps({"data": out} if status < 400 else (out or {"message": "authentication failure"})).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                self._go("GET")

            def do_POST(self):
                self._go("POST")

            def do_PUT(self):
                self._go("PUT")

            def do_DELETE(self):
                self._go("DELETE")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.handle_error = lambda request, address: None
        if self.tls:
            from fake_mikrotik import self_signed
            self._dir = tempfile.TemporaryDirectory()
            cert, key, der = self_signed(self._dir.name)
            self.fingerprint = hashlib.sha256(der).hexdigest()
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(cert, key)
            self.server.socket = ctx.wrap_socket(self.server.socket, server_side=True)
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
        return f"{'https' if self.tls else 'http'}://127.0.0.1:{self.server.server_address[1]}"

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
