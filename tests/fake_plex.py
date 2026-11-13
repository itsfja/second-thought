"""A stand-in for Plex's HTTP API and Tautulli's API (#402), serving the sample the page uses (samples/
connections.json, "plex"), shaped the way they answer: GET /, /library/sections, /library/sections/{id}/all,
/library/recentlyAdded and /status/sessions give the sample, with the token checked as X-Plex-Token; GET
/api/v2?cmd=get_history answers Tautulli's history rows (with the columns the real one sends), and
cmd=terminate_session is recorded in .changed. A library scan (GET /library/sections/{id}/refresh) is recorded
in .changed too.

Anything else, a request without the token, or a Tautulli request without the right api_key, is recorded in
.refused and answered 401, so a test can show nothing else was sent. The history rows carry dates made from
time.time(), so "last N days" always covers them.

    plex = FakePlex()
    host = plex.start()          # http://127.0.0.1:port, for PLEX_URL and TAUTULLI_URL
"""
import json
import pathlib
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = pathlib.Path(__file__).resolve().parent.parent

COLS = ["row_id", "date", "user", "platform", "device", "ip", "location", "bandwidth", "transcode_decision",
        "duration", "percent_complete", "progress", "media_type", "title", "grandtitle", "parenttitle",
        "full_title", "original_title"]


class FakePlex:
    def __init__(self, data=None, token="tok", api_key="key"):
        self.data = data or json.loads((ROOT / "samples" / "connections.json").read_text(encoding="utf-8"))["plex"]
        self.token, self.api_key = token, api_key
        self.calls, self.refused, self.changed = [], [], []

    AGO_HOURS = [26, 27, 70, 500]  # last night, last night, three days ago, beyond a week

    def history_rows(self, after):
        """Tautulli's rows, oldest first, with dates relative to now and the columns the real one sends."""
        rows = []
        for i, h in enumerate(self.data["history"]):
            when = time.time() - self.AGO_HOURS[i] * 3600
            if when < after:
                continue
            rows.append([i, int(when), h["user"], "Plex Web", "", "127.0.0.1", "lan", "",
                         "transcode" if h["transcode"] else "direct play", h["duration"], 100, 100,
                         "episode" if "s0" in h["title"] else "film", h["title"], "", "",
                         h["title"], ""])
        return rows

    def answer(self, method, path, query, body, headers):
        """(status, body)."""
        as_json = lambda o: (200, json.dumps(o).encode())  # noqa: E731
        if path.startswith("/api/v2"):  # Tautulli
            q = {k: v[0] for k, v in (query or {}).items()}
            if q.get("api_key") != self.api_key:
                return 401, b'{"error": "unauthorized"}'
            cmd = q.get("cmd", "")
            if cmd == "get_history":
                after = q.get("after")
                try:
                    cutoff = time.mktime(time.strptime(after, "%Y-%m-%d")) if after else 0
                except ValueError:
                    cutoff = 0
                rows = self.history_rows(cutoff)
                return as_json({"response": {"result": "success", "data": {"columns": COLS, "data": rows,
                                                                          "recordsFiltered": len(rows)}}})
            if cmd == "terminate_session":
                self.changed.append("terminate " + q.get("session_key", ""))
                return as_json({"response": {"result": "success", "message": "Session terminated"}})
            self.refused.append(f"TAUTULLI {method} {path}")
            return 401, b'{"error": "unauthorized"}'
        if headers.get("X-Plex-Token") != self.token:
            return 401, b'{"error": "unauthorized"}'
        d = self.data
        if method == "GET" and path == "/":
            return as_json({"MediaContainer": {"friendlyName": d["server"]["name"], "version": d["server"]["version"]}})
        if method == "GET" and path == "/library/sections":
            return as_json({"MediaContainer": {"Directory": [{"key": str(l["id"]), "title": l["name"],
                                                              "type": l["type"]} for l in d["libraries"]]}})
        if method == "GET" and path.startswith("/library/sections/") and path.endswith("/all"):
            key = path.split("/")[3]
            lib = next((l for l in d["libraries"] if str(l["id"]) == key), None)
            return as_json({"MediaContainer": {"size": lib["count"] if lib else 0}}) if lib else (404, b"{}")
        if method == "GET" and path.startswith("/library/sections/") and path.endswith("/refresh"):
            self.changed.append("scan " + path.split("/")[3])
            return as_json({"MediaContainer": {}})
        if method == "GET" and path == "/library/recentlyAdded":
            return as_json({"MediaContainer": {"Metadata": [{"title": r["title"], "addedAt": r["added"],
                                                             "librarySectionTitle": r["library"]} for r in d["recent"]]}})
        if method == "GET" and path == "/status/sessions":
            vid = []
            for s in d["sessions"]:
                show, _, title = s["title"].partition(" - ")
                v = {"sessionKey": s["id"], "title": title or show, "User": {"title": s["user"]},
                     "Player": {"title": s["player"], "state": s["state"]}}
                if s["transcode"]:
                    v["TranscodeSession"] = {"key": s["id"]}
                if " - " in s["title"]:
                    v["grandparentTitle"] = show
                vid.append(v)
            return as_json({"MediaContainer": {"size": len(vid), "Video": vid}})
        self.refused.append(f"{method} {path}")
        return 401, b'{"error": "unauthorized"}'

    def start(self):
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def address_string(self):
                return "client"

            def do_GET(self):
                u = urlparse(self.path)
                fake.calls.append(f"GET {u.path}")
                status, out = fake.answer("GET", u.path, parse_qs(u.query), b"", dict(self.headers))
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.handle_error = lambda request, address: None
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
