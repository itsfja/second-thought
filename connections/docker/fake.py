"""A stand-in for Docker's Engine API (#358), serving the sample stack the page uses (samples/connections.json,
"docker"), shaped the way the Engine answers: the container list, inspect, stats and logs (framed, as Docker frames a
container's output and errors).

Restart, stop and start are recorded in .powered (as "restart sonarr"). Anything else is recorded in .refused and
answered 403, the way a socket proxy answers what it doesn't allow, so a test can show nothing else was sent.

    docker = FakeDocker()
    host = docker.start()                 # tcp://127.0.0.1:port, for DOCKER_HOST
    host = docker.start(unix=path)        # unix://path, a socket like /var/run/docker.sock (not on Windows)
    host = docker.start(tls=folder)       # TLS, with ca.pem written to folder for DOCKER_CERT_PATH
"""
import json
import pathlib
import re
import shutil
import socketserver
import ssl
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
NAME = r"[A-Za-z0-9][A-Za-z0-9_.-]*"


class FakeDocker:
    def __init__(self, data=None):
        self.data = data or json.loads((ROOT / "samples" / "connections.json").read_text(encoding="utf-8"))["docker"]
        self.calls, self.refused, self.powered = [], [], []

    def answer(self, method, path, query):
        """(status, body, content type)."""
        d = self.data
        by_name = {c["name"]: c for c in d["containers"]}
        as_json = lambda o: (200, json.dumps(o).encode(), "application/json")  # noqa: E731
        if method == "GET" and path == "/version":
            return as_json(d["version"])
        if method == "GET" and path == "/containers/json":
            every = query.get("all", ["0"])[0] in ("1", "true")
            return as_json([{"Id": "id-" + c["name"], "Names": ["/" + c["name"]], "Image": c["image"], "State": c["state"], "Status": c["status"]}
                            for c in d["containers"] if every or c["state"] in ("running", "restarting")])
        m = re.fullmatch(rf"/containers/({NAME})/(json|stats|logs)", path)
        if method == "GET" and m:
            c = by_name.get(m[1])
            if not c:
                return 404, json.dumps({"message": f"No such container: {m[1]}"}).encode(), "application/json"
            if m[2] == "json":
                state = {"Status": c["state"], "StartedAt": c["started"]}
                if c["health"]:
                    state["Health"] = {"Status": c["health"]}
                return as_json({"Name": "/" + c["name"], "RestartCount": c["restarts"], "State": state, "Config": {"Image": c["image"]}})
            if m[2] == "stats":
                return as_json(c["stats"])
            lines = d["logs"].get(c["name"], [])[-int(query.get("tail", ["100"])[0]):]
            frames = b"".join(bytes([2 if i % 2 else 1, 0, 0, 0]) + len(raw).to_bytes(4, "big") + raw
                              for i, raw in enumerate((line + "\n").encode() for line in lines))
            return 200, frames, "application/vnd.docker.multiplexed-stream"
        m = re.fullmatch(rf"/containers/({NAME})/(restart|stop|start)", path)
        if method == "POST" and m and m[1] in by_name:
            self.powered.append(f"{m[2]} {m[1]}")
            return 204, b"", "application/json"
        self.refused.append(f"{method} {path}")
        return 403, json.dumps({"message": "Forbidden"}).encode(), "application/json"

    def start(self, unix=None, tls=None):
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def address_string(self):
                return "client"

            def _go(self, method):
                u = urlparse(self.path)
                if method != "GET":
                    self.rfile.read(int(self.headers.get("Content-Length") or 0))
                fake.calls.append(f"{method} {u.path}")
                status, body, kind = fake.answer(method, u.path, parse_qs(u.query))
                self.send_response(status)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                self._go("GET")

            def do_POST(self):
                self._go("POST")

            def do_DELETE(self):
                self._go("DELETE")

            def do_PUT(self):
                self._go("PUT")

        if unix:
            class UnixServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
                daemon_threads = True

                def get_request(self):
                    request, _ = super().get_request()
                    return request, ("unix", 0)
            self.server = UnixServer(str(unix), Handler)
            host = f"unix://{unix}"
        else:
            self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            host = f"tcp://127.0.0.1:{self.server.server_address[1]}"
            if tls:
                from fake_mikrotik import self_signed
                cert, key, _ = self_signed(tls)
                shutil.copy(cert, pathlib.Path(tls) / "ca.pem")  # signed by itself, so it is its own authority
                ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ctx.load_cert_chain(cert, key)
                self.server.socket = ctx.wrap_socket(self.server.socket, server_side=True)
        self.server.handle_error = lambda request, address: None
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
        return host

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
