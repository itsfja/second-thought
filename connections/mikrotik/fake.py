"""A stand-in for RouterOS 7's REST API (#360), serving the sample switch the page uses (samples/connections.json,
"mikrotik"), shaped the way RouterOS answers.

It checks the user and password (monitor / secret by default) and answers only reading: GET on the paths the runtime
reads, and the monitor command. Anything else is recorded in .refused and answered 400, so a test can show nothing
else was ever sent. With tls=True it serves HTTPS with a new self-signed certificate (needs the cryptography package),
like a router does; .fingerprint is its SHA-256.

    mt = FakeMikrotik(tls=True)
    url = mt.start()            # then MIKROTIK_URL = url, MIKROTIK_USER = monitor, MIKROTIK_PASSWORD = secret
    mt.calls, mt.refused, mt.fingerprint
"""
import base64
import datetime
import hashlib
import ipaddress
import json
import pathlib
import ssl
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
USER, PASSWORD = "monitor", "secret"


def self_signed(folder):
    """A certificate and key for 127.0.0.1, signed by themselves, as a router's are. Gives back (cert, key, DER)."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "router")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
            .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=30)).sign(key, hashes.SHA256()))
    cert_path, key_path = pathlib.Path(folder) / "router.crt", pathlib.Path(folder) / "router.key"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
    return str(cert_path), str(key_path), cert.public_bytes(serialization.Encoding.DER)


class FakeMikrotik:
    def __init__(self, tls=False, data=None, user=USER, password=PASSWORD, group=None):
        self.data = data or json.loads((ROOT / "samples" / "connections.json").read_text(encoding="utf-8"))["mikrotik"]
        if group:  # put the user in another group, say "full"
            self.data = dict(self.data, users=[dict(u, group=group) if u["name"] == user else u for u in self.data["users"]])
        self.tls, self.user, self.password = tls, user, password
        self.calls, self.refused = [], []
        self.fingerprint = None

    def answer(self, method, path, query, body):
        d = self.data
        if method == "GET" and path == "/rest/interface":
            return 200, d["interfaces"]
        if method == "GET" and path == "/rest/system/resource":
            return 200, d["resource"]
        if method == "GET" and path == "/rest/system/health":
            return 200, d["health"]
        if method == "GET" and path == "/rest/log":
            return 200, d["log"]
        if method == "GET" and path == "/rest/user":
            return 200, d["users"]
        if method == "GET" and path == "/rest/user/group":
            return 200, d["groups"]
        if method == "POST" and path == "/rest/interface/ethernet/monitor" and "once" in body:
            names = [n for n in str(body.get("numbers", "")).split(",") if n]
            return 200, [d["monitor"][n] for n in names if n in d["monitor"]]
        self.refused.append(f"{method} {path}")
        return 400, {"error": 400, "message": "Bad Request", "detail": "not in the stand-in"}

    def start(self):
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _go(self, method):
                u = urlparse(self.path)
                raw = self.rfile.read(int(self.headers.get("Content-Length") or 0)) if method != "GET" else b""
                fake.calls.append(f"{method} {u.path}")
                want = "Basic " + base64.b64encode(f"{fake.user}:{fake.password}".encode()).decode()
                if self.headers.get("Authorization") != want:
                    status, out = 401, {"error": 401, "message": "Unauthorized"}
                else:
                    try:
                        body = json.loads(raw) if raw else {}
                    except ValueError:
                        body = {}
                    status, out = fake.answer(method, u.path, parse_qs(u.query), body)
                data = json.dumps(out).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                self._go("GET")

            def do_POST(self):
                self._go("POST")

            def do_PATCH(self):
                self._go("PATCH")

            def do_PUT(self):
                self._go("PUT")

            def do_DELETE(self):
                self._go("DELETE")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.handle_error = lambda request, address: None  # a client that hangs up on a certificate it won't take
        if self.tls:
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
