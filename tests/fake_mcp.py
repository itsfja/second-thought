#!/usr/bin/env python3
"""A stand-in MCP server, for the tests. It speaks either era, over stdio or HTTP, and is strict about the parts a
client must get right, so a mistake in the client shows up as a failed check.

    python fake_mcp.py modern|legacy|silent|slow        # stdio
    (in Python) start_http(era, sse=False, token="")   # HTTP, in a thread; gives its URL

Its tools: list_loaves (read-only), add_loaf (changes things: writes to FAKE_MCP_LOG's .loaves file), fail (always
reports an error), bake_in (an x-mcp-header parameter), and over HTTP one with an invalid x-mcp-header (number type),
which a current-era HTTP client must leave out (only a current-era HTTP server offers it). tools/list comes in two pages. Every message it gets is logged, one
JSON line each, to FAKE_MCP_LOG.
"""
import json
import os
import sys
import threading
import time
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODERN, LEGACY = "2026-07-28", "2025-11-25"
LOG = os.environ.get("FAKE_MCP_LOG", os.devnull)
TOOLS = [
    {"name": "list_loaves", "description": "Lists the loaves baked so far.", "inputSchema": {"type": "object", "properties": {}},
     "annotations": {"readOnlyHint": True}},
    {"name": "add_loaf", "description": "Adds a loaf to the bake list.",
     "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}, "grams": {"type": "integer"}}, "required": ["name"]}},
    {"name": "fail", "description": "Always fails.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "bake_in", "description": "Bakes in a region.",
     "inputSchema": {"type": "object", "properties": {"region": {"type": "string", "x-mcp-header": "Region"}, "loaf": {"type": "string"}},
                     "required": ["region"]}},
]
BAD_HEADER_TOOL = {"name": "bad_header", "description": "Has an invalid x-mcp-header (a number).",
                   "inputSchema": {"type": "object", "properties": {"n": {"type": "number", "x-mcp-header": "N"}}}}


def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(msg) + "\n")


def loaves_file():
    return LOG + ".loaves" if LOG != os.devnull else os.devnull


def call_tool(name, args):
    if name == "list_loaves":
        try:
            with open(loaves_file(), encoding="utf-8") as f:
                got = f.read().split("\n")
        except OSError:
            got = []
        return {"content": [{"type": "text", "text": ", ".join(x for x in got if x) or "No loaves yet."}]}
    if name == "add_loaf":
        with open(loaves_file(), "a", encoding="utf-8") as f:
            f.write(f"{args.get('name')} ({args.get('grams', '?')} g)\n")
        return {"content": [{"type": "text", "text": f"Added {args.get('name')}."}], "structuredContent": {"ok": True}}
    if name == "fail":
        return {"content": [{"type": "text", "text": "The oven is off."}], "isError": True}
    if name == "bake_in":
        return {"content": [{"type": "text", "text": f"Baking {args.get('loaf', 'bread')} in {args.get('region')}."}]}
    return None


def handle(msg, era, http=False):
    """The reply to one request (or None for a notification), as the server of that era would give it."""
    method, params, rid = msg.get("method"), msg.get("params") or {}, msg.get("id")
    if rid is None:
        return None
    meta = (params.get("_meta") or {})
    err = lambda code, text, data=None: {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": text, **({"data": data} if data else {})}}  # noqa: E731
    ok = lambda result: {"jsonrpc": "2.0", "id": rid, "result": result}  # noqa: E731
    if era == "modern":
        if meta.get("io.modelcontextprotocol/protocolVersion") != MODERN or "io.modelcontextprotocol/clientCapabilities" not in meta:
            return err(-32602, "Missing _meta protocol fields")
        if method == "server/discover":
            return ok({"resultType": "complete", "supportedVersions": [MODERN], "capabilities": {"tools": {}},
                       "_meta": {"io.modelcontextprotocol/serverInfo": {"name": "fake", "version": "1"}}})
    else:
        if method == "initialize":
            if params.get("protocolVersion") != LEGACY:
                return err(-32602, "Unsupported protocol version")
            return ok({"protocolVersion": LEGACY, "capabilities": {"tools": {}}, "serverInfo": {"name": "fake", "version": "1"}})
        if method == "server/discover":
            return err(-32601, "Method not found")
        if "_meta" in params and "io.modelcontextprotocol/protocolVersion" in params["_meta"]:
            return err(-32600, "A legacy server doesn't take per-request versions")
    if method == "tools/list":
        tools = TOOLS + ([BAD_HEADER_TOOL] if http else [])
        page = 0 if not params.get("cursor") else 1
        chunk = tools[:2] if page == 0 else tools[2:]
        result = {"tools": chunk, **({"nextCursor": "page-2"} if page == 0 else {})}
        return ok(dict(result, resultType="complete") if era == "modern" else result)
    if method == "tools/call":
        r = call_tool(params.get("name"), params.get("arguments") or {})
        if r is None:
            return err(-32602, f"Unknown tool: {params.get('name')}")
        return ok(dict(r, resultType="complete") if era == "modern" else r)
    return err(-32601, "Method not found")


def stdio(era):
    initialized = False
    pinged = False
    if era == "slow":
        time.sleep(float(os.environ.get("FAKE_MCP_SLOW", "3")))
        era = "modern"
    for line in sys.stdin:
        msg = json.loads(line)
        log(msg)
        if "method" not in msg:  # a reply to our ping
            continue
        if era == "silent" and not initialized and msg.get("method") not in ("initialize", "notifications/initialized"):
            continue  # some earlier-era servers just ignore what comes before initialize
        if msg.get("method") == "notifications/initialized":
            initialized = True
            if not pinged:  # an earlier-era server may ping its client: the client must answer
                pinged = True
                sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": "srv-ping", "method": "ping"}) + "\n")
                sys.stdout.flush()
            continue
        reply = handle(msg, "legacy" if era in ("legacy", "silent") else era)
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()
        print("fake mcp: handled " + str(msg.get("method")), file=sys.stderr, flush=True)


def _b64(v):
    return base64.b64decode(v[9:-2]).decode("utf-8") if v.startswith("=?base64?") and v.endswith("?=") else v


def start_http(era, sse=False, token=""):
    sessions, made = set(), [0]

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, code, body, headers=()):
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            for k, v in headers:
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            self.send_response(405)
            self.end_headers()

        def do_POST(self):
            msg = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"null")
            log({"http": dict(self.headers), "body": msg})
            if token and self.headers.get("Authorization") != "Bearer " + token:
                return self._json(401, {"error": "unauthorised"})
            accept = self.headers.get("Accept", "")
            if "application/json" not in accept or "text/event-stream" not in accept:
                return self._json(406, {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Accept both"}})
            method, params = msg.get("method"), msg.get("params") or {}
            if era == "modern":
                bad = None
                if self.headers.get("MCP-Protocol-Version") != (params.get("_meta") or {}).get("io.modelcontextprotocol/protocolVersion"):
                    bad = "MCP-Protocol-Version"
                elif self.headers.get("Mcp-Method") != method:
                    bad = "Mcp-Method"
                elif method == "tools/call" and _b64(self.headers.get("Mcp-Name", "")) != params.get("name"):
                    bad = "Mcp-Name"
                elif method == "tools/call" and params.get("name") == "bake_in" and _b64(self.headers.get("Mcp-Param-Region", "")) != (params.get("arguments") or {}).get("region"):
                    bad = "Mcp-Param-Region"
                if bad:
                    return self._json(400, {"jsonrpc": "2.0", "id": msg.get("id"), "error": {"code": -32020, "message": "Header mismatch: " + bad}})
            else:
                if method == "server/discover":
                    return self._json(400, {"jsonrpc": "2.0", "id": msg.get("id"), "error": {"code": -32000, "message": "No valid session ID"}})
                if method != "initialize":
                    sid = self.headers.get("Mcp-Session-Id")
                    if sid not in sessions:
                        return self._json(404 if sid else 400, {"jsonrpc": "2.0", "error": {"code": -32000, "message": "Bad session"}})
                    if self.headers.get("MCP-Protocol-Version") != LEGACY:
                        return self._json(400, {"jsonrpc": "2.0", "error": {"code": -32000, "message": "Bad protocol version header"}})
            if "id" not in msg:
                self.send_response(202)
                self.end_headers()
                return
            reply = handle(msg, era, http=era == "modern")
            extra = []
            if era == "legacy" and method == "initialize":
                made[0] += 1
                sid = f"s-{made[0]}"
                sessions.add(sid)
                extra.append(("Mcp-Session-Id", sid))
            if sse:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                for k, v in extra:
                    self.send_header(k, v)
                self.end_headers()
                note = {"jsonrpc": "2.0", "method": "notifications/progress", "params": {"progressToken": 1, "progress": 1}}
                self.wfile.write(b": keep-alive\n\n")
                self.wfile.write(("event: message\ndata: " + json.dumps(note) + "\n\n").encode())
                body = json.dumps(reply)
                cut = body.index('"id"')  # one event over two data lines, split between two JSON tokens
                self.wfile.write(("data: " + body[:cut] + "\ndata: " + body[cut:] + "\n\n").encode())
                self.wfile.flush()
                return
            self._json(200, reply, extra)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    srv.sessions = sessions
    return f"http://127.0.0.1:{srv.server_address[1]}/mcp", srv


if __name__ == "__main__":
    stdio(sys.argv[1] if len(sys.argv) > 1 else "modern")
