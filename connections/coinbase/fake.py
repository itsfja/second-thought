"""A stand-in for Coinbase's Advanced Trade API (#371), serving the sample portfolio the page uses
(samples/connections.json, "coinbase"), shaped the way Coinbase answers.

Every request must carry a JWT signed with the test key, the way Coinbase checks one: ES256, the key's name as kid and
sub, iss "cdp", a "METHOD host/path" uri matching the request, two minutes at most, and a nonce not seen before. A
request that fails any of that is answered 401, as Coinbase would.

    coinbase = FakeCoinbase(key_file, can_trade=False)
    url = coinbase.start()          # then COINBASE_API_URL = url, COINBASE_KEY_FILE = key_file
    coinbase.calls, coinbase.placed, coinbase.cancelled
"""
import base64
import json
import math
import pathlib
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
KEY_NAME = "organizations/test-org/apiKeys/test-key"


def make_key(path, name=KEY_NAME):
    """Writes a CDP-style key file (name and an EC private key in PEM) and gives back its path."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()).decode()
    pathlib.Path(path).write_text(json.dumps({"name": name, "privateKey": pem}), encoding="utf-8")
    return str(path)


def _b64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def cents(v):
    return math.floor(v * 100 + 0.5) / 100


class FakeCoinbase:
    def __init__(self, key_file, can_trade=False, can_transfer=False, data=None):
        from cryptography.hazmat.primitives import serialization
        key = json.loads(pathlib.Path(key_file).read_text(encoding="utf-8"))
        self.name = key["name"]
        self.public = serialization.load_pem_private_key(key["privateKey"].encode(), password=None).public_key()
        self.data = data or json.loads((ROOT / "samples" / "connections.json").read_text(encoding="utf-8"))["coinbase"]
        self.can_trade, self.can_transfer = can_trade, can_transfer
        self.calls, self.placed, self.cancelled, self.refused = [], [], [], []
        self.nonces = set()
        self.previews = {}

    # ----- the JWT -----
    def _token_problem(self, method, host, path, auth):
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec, utils
        if not auth.startswith("Bearer "):
            return "no bearer token"
        try:
            head, claims, sig = auth[7:].split(".")
            h, c, s = json.loads(_b64(head)), json.loads(_b64(claims)), _b64(sig)
        except ValueError:
            return "not a JWT"
        if h.get("alg") != "ES256" or h.get("kid") != self.name or not h.get("nonce"):
            return "bad header"
        if h["nonce"] in self.nonces:
            return "nonce used before"
        now = time.time()
        if c.get("sub") != self.name or c.get("iss") != "cdp" or not (c.get("nbf", 0) - 5 <= now <= c.get("exp", 0)) or c["exp"] - c["nbf"] > 120:
            return "bad claims"
        if c.get("uri") != f"{method} {host}{path}":
            return f"uri {c.get('uri')!r} isn't {method} {host}{path}"
        if len(s) != 64:
            return "signature isn't r and s"
        try:
            self.public.verify(utils.encode_dss_signature(int.from_bytes(s[:32], "big"), int.from_bytes(s[32:], "big")),
                               f"{head}.{claims}".encode(), ec.ECDSA(hashes.SHA256()))
        except InvalidSignature:
            return "signature doesn't verify"
        self.nonces.add(h["nonce"])
        return None

    # ----- the API -----
    def answer(self, method, path, query, body):
        """(status, JSON) for one request whose token was good. path starts /api/v3/brokerage/."""
        d, p = self.data, path[len("/api/v3/brokerage"):]
        q = {k: v[-1] for k, v in query.items()}
        products = d["products"]
        if method == "GET" and p == "/key_permissions":
            return 200, {"can_view": True, "can_trade": self.can_trade, "can_transfer": self.can_transfer,
                         "portfolio_uuid": d["portfolio"]["uuid"], "portfolio_type": "DEFAULT"}
        if method == "GET" and p == "/accounts":
            return 200, {"accounts": [{"uuid": "acc-" + x["asset"], "currency": x["asset"], "available_balance": {"value": str(x["total_balance_crypto"]), "currency": x["asset"]}}
                                      for x in d["positions"]][:int(q.get("limit", 49))], "has_next": False}
        if method == "GET" and p == "/portfolios/" + d["portfolio"]["uuid"]:
            total = sum(x["total_balance_fiat"] for x in d["positions"])
            return 200, {"breakdown": {"portfolio": dict(d["portfolio"], type="DEFAULT"),
                                       "portfolio_balances": {"total_balance": {"value": str(total), "currency": q.get("currency", "GBP")}},
                                       "spot_positions": d["positions"]}}
        if method == "GET" and p.startswith("/products/") and p.endswith("/candles"):
            rows = d["candles"].get(p.split("/")[2], {}).get({"ONE_DAY": "day", "ONE_HOUR": "hour"}.get(q.get("granularity"), ""))
            if not rows:
                return 404, {"error": "NOT_FOUND", "message": "no candles"}
            step = 3600 if q["granularity"] == "ONE_HOUR" else 86400
            some = rows[-int(q.get("limit", 350)):]
            top = int(q["end"]) // step * step
            out = [{"start": str(top - (len(some) - 1 - i) * step), "open": str(r[0]), "high": str(r[1]), "low": str(r[2]), "close": str(r[3]),
                    "volume": str(r[4])} for i, r in enumerate(some)]
            return 200, {"candles": out[::-1]}  # Coinbase gives the newest first
        if method == "GET" and p.startswith("/products/"):
            pr = products.get(p.split("/")[2])
            return (200, dict(pr, base_currency_id=pr["product_id"].split("-")[0], quote_currency_id=pr["product_id"].split("-")[1])) if pr else \
                (404, {"error": "NOT_FOUND", "message": "product not found"})
        if method == "GET" and p == "/orders/historical/batch":
            return 200, {"orders": [o for o in d["orders"] if q.get("order_status") in (None, o["status"])], "has_next": False, "cursor": ""}
        if method == "GET" and p == "/orders/historical/fills":
            return 200, {"fills": d["fills"], "cursor": ""}
        if method == "POST" and p == "/orders/preview":
            return 200, self.preview(body)
        if method == "POST" and p == "/orders":
            if not self.can_trade:
                return 403, {"error": "PERMISSION_DENIED", "message": "Missing required scopes"}
            pre = self.preview(body)
            if pre["errs"]:
                return 200, {"success": False, "error_response": {"message": pre["errs"][0]}}
            self.placed.append(body)
            return 200, {"success": True, "success_response": {"order_id": f"order-{len(self.placed)}", "product_id": body["product_id"],
                                                               "side": body["side"], "client_order_id": body["client_order_id"]}}
        if method == "POST" and p == "/orders/batch_cancel":
            if not self.can_trade:
                return 403, {"error": "PERMISSION_DENIED", "message": "Missing required scopes"}
            out = []
            for oid in body.get("order_ids") or []:
                known = any(o["order_id"] == oid for o in d["orders"])
                if known:
                    self.cancelled.append(oid)
                out.append({"success": known, "failure_reason": "" if known else "UNKNOWN_CANCEL_ORDER", "order_id": oid})
            return 200, {"results": out}
        return 404, {"error": "NOT_FOUND", "message": f"{method} {path} isn't in the stand-in"}

    def preview(self, body):
        """A 0.6% fee and no slippage, as the page's sample account works it out (coinbasePreview in 18-connections.js)."""
        pid = body["product_id"]
        base, quote = pid.split("-")
        price = float(self.data["products"][pid]["price"])
        cfg = body["order_configuration"]["market_market_ioc"]
        have = {x["asset"]: x["total_balance_crypto"] for x in self.data["positions"]}
        if body["side"] == "BUY":
            a = float(cfg["quote_size"])
            fee = cents(a * 0.006)
            size, spend, total, short = math.floor((a - fee) / price * 1e8) / 1e8, a, a, a > have.get(quote, 0)
        else:
            a = float(cfg["base_size"])
            gross = cents(a * price)
            fee = cents(gross * 0.006)
            size, spend, total, short = a, gross, cents(gross - fee), a > have.get(base, 0)
        self.previews[pid] = len(self.previews) + 1
        return {"order_total": repr(total), "commission_total": repr(fee), "errs": ["PREVIEW_INSUFFICIENT_FUND"] if short else [], "warning": [],
                "quote_size": repr(spend), "base_size": repr(size), "best_bid": repr(price), "best_ask": repr(price), "is_max": False,
                "slippage": "0", "preview_id": f"preview-{self.previews[pid]}"}

    # ----- the server -----
    def start(self):
        """Serves on 127.0.0.1 in the background; gives back the base URL to use as COINBASE_API_URL."""
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _go(self, method):
                u = urlparse(self.path)
                raw = self.rfile.read(int(self.headers.get("Content-Length") or 0)) if method != "GET" else b""
                fake.calls.append(f"{method} {u.path}")
                problem = fake._token_problem(method, self.headers.get("Host", ""), u.path, self.headers.get("Authorization", ""))
                if problem:
                    fake.refused.append(problem)
                    status, out = 401, {"error": "UNAUTHENTICATED", "message": problem}
                elif not u.path.startswith("/api/v3/brokerage/"):
                    status, out = 404, {"error": "NOT_FOUND", "message": "not found"}
                else:
                    try:
                        body = json.loads(raw) if raw else {}
                    except ValueError:
                        body = None
                    status, out = (400, {"error": "INVALID_ARGUMENT", "message": "bad JSON"}) if body is None else \
                        fake.answer(method, u.path, parse_qs(u.query), body)
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

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
