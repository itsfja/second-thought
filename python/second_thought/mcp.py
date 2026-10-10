"""MCP (Model Context Protocol) servers: their tools, for the agent.

Part of the second_thought package. tools/sync.py joins these files, in order, into
python/runtime.py, which is what ships inside every exported program and the page.
"""
import asyncio
import base64
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from .settings import RUNTIME_VERSION, WHERE_KEYS
from .core import RunError, _number_setting, _short, to_str
# ---- package only: tools/sync.py leaves everything above this line out of python/runtime.py ----
import atexit  # noqa: E402,F811 - below the line, so python/runtime.py has them too (settings.py doesn't import these)
import shlex  # noqa: E402,F811
import shutil  # noqa: E402,F811
import subprocess  # noqa: E402,F811


# ----- MCP servers -----
# Set a server up in second-thought.ini as MCP_<NAME> = the command that starts it, or its https:// address:
#     MCP_FILES = npx -y @modelcontextprotocol/server-filesystem /home/me/recipes
#     MCP_TRACKER = https://mcp.example.com/mcp        (and MCP_TRACKER_TOKEN = ... if it needs one)
# A started server gets this program's settings as its environment, so its own keys can go in second-thought.ini too.
# Both kinds of MCP are spoken: the current one, where every request says its version (2026-07-28), and the earlier
# one that starts with an initialize handshake (2025-11-25 back to 2024-11-05). Which a server speaks is found out once.
MCP_MODERN = "2026-07-28"
MCP_LEGACY = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
MCP_MODERN_ERRORS = {-32020, -32021, -32022}  # errors only a current-era server sends
MCP_TIMEOUT = _number_setting("RB_MCP_TIMEOUT", 120, "a number of seconds")  # one tool call, at most
MCP_PROBE_SECONDS = 10  # how long a started server has to answer server/discover before it's taken to be an earlier-era one
MCP_MAX_TOOLS = 200
MCP_MAX_RESULT = 20000  # characters of a tool's result the agent sees
_HEADER_TOKEN = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")


def mcp_env_name(server):
    """'my files' -> 'MCP_MY_FILES'."""
    return "MCP_" + re.sub(r"[^A-Za-z0-9]+", "_", to_str(server).strip()).strip("_").upper()


class _RPCError(Exception):
    def __init__(self, code, message, data=None):
        super().__init__(message)
        self.code, self.message, self.data = code, message, data


class _NoAnswer(Exception):
    """A request got no reply in time."""


def _client_info():
    return {"name": "Second Thought", "version": RUNTIME_VERSION}


def _header_value(v):
    """A tool argument as an HTTP header value: plain when safe, else the =?base64?...?= form the spec gives."""
    s = ("true" if v else "false") if isinstance(v, bool) else str(v)
    safe = all(c == "\t" or 32 <= ord(c) <= 126 for c in s) and s == s.strip() and not (s.startswith("=?base64?") and s.endswith("?="))
    return s if safe else "=?base64?" + base64.b64encode(s.encode("utf-8")).decode("ascii") + "?="


def _header_params(schema):
    """The x-mcp-header annotations in a tool's input schema: [(header name, property path)], or None if any is invalid."""
    found, valid = [], []

    def walk(node, path, plain):
        if isinstance(node, dict):
            if "x-mcp-header" in node:
                found.append(path)
                h, t = node["x-mcp-header"], node.get("type")
                if plain and path and isinstance(h, str) and h and _HEADER_TOKEN.match(h) and t in ("string", "integer", "boolean"):
                    valid.append((h, path))
            for k, v in node.items():
                if k == "properties" and isinstance(v, dict):
                    for pk, pv in v.items():
                        walk(pv, path + [pk], plain)
                elif k != "x-mcp-header":
                    walk(v, path, False)
        elif isinstance(node, list):
            for v in node:
                walk(v, path, False)
    walk(schema, [], True)
    names = [h.lower() for h, _ in valid]
    if len(valid) != len(found) or len(names) != len(set(names)):
        return None
    return valid


def mcp_result_text(result):
    """A tools/call result as (text for the agent, whether the tool said it failed)."""
    parts = []
    for c in result.get("content") or []:
        if not isinstance(c, dict):
            continue
        t = c.get("type")
        if t == "text":
            parts.append(to_str(c.get("text")))
        elif t in ("image", "audio"):
            parts.append(f"[{t} from the tool ({c.get('mimeType', 'unknown type')}): not shown to the agent]")
        elif t == "resource_link":
            parts.append(f"Link: {c.get('name') or c.get('uri')} ({c.get('uri')})")
        elif t == "resource":
            r = c.get("resource") or {}
            parts.append(to_str(r.get("text")) if r.get("text") is not None else f"[a file from the tool: {r.get('uri')}]")
    if not parts and result.get("structuredContent") is not None:
        parts.append(json.dumps(result["structuredContent"], ensure_ascii=False))
    text = "\n".join(p for p in parts if p) or "(the tool gave no result)"
    if len(text) > MCP_MAX_RESULT:
        text = text[:MCP_MAX_RESULT] + f"\n\n… (cut: the result goes on for {len(text) - MCP_MAX_RESULT:,} more characters)"
    return text, result.get("isError") is True


class _MCPServer:
    """One MCP server, whichever era it speaks. Transports below supply _request and _notify."""

    def __init__(self, name):
        self.name, self.era, self.version, self.tools = name, None, None, None
        self._lock = threading.Lock()  # one era check at a time
        self._next, self._id_lock = 0, threading.Lock()

    def _id(self):
        with self._id_lock:
            self._next += 1
            return self._next

    def describe(self):
        return f"MCP server “{self.name}”"

    def _meta(self, params):
        params = dict(params or {})
        params["_meta"] = dict(params.get("_meta") or {}, **{
            "io.modelcontextprotocol/protocolVersion": MCP_MODERN, "io.modelcontextprotocol/clientInfo": _client_info(),
            "io.modelcontextprotocol/clientCapabilities": {}})
        return params

    def _versions(self, e):
        """The versions a current-era server listed in an UnsupportedProtocolVersion error."""
        data = e.data if isinstance(e.data, dict) else {}
        return [v for v in data.get("supported") or [] if isinstance(v, str)]

    def _modern_or_legacy(self, versions):
        if MCP_MODERN in versions:
            self.era, self.version = "modern", MCP_MODERN
            return
        old = next((v for v in versions if v in MCP_LEGACY), None)
        if not old:
            raise RunError(f"The {self.describe()} speaks MCP {', '.join(versions) or 'versions'} this runtime doesn't. "
                           "A newer Second Thought may.")
        self._initialize(old)

    def open(self):
        """Finds out which era the server speaks (once)."""
        with self._lock:
            if self.era:
                return
            self._find_era()

    def _initialize(self, version=MCP_LEGACY[0]):
        r = self._request("initialize", {"protocolVersion": version, "capabilities": {}, "clientInfo": _client_info()},
                          MCP_TIMEOUT, legacy=True)
        got = r.get("protocolVersion") if isinstance(r, dict) else None
        if got not in MCP_LEGACY:
            raise RunError(f"The {self.describe()} wants MCP version “{got}”, which this runtime doesn't speak.")
        self.era, self.version = "legacy", got
        self._notify("notifications/initialized")

    def request(self, method, params=None, schema=None):
        self.open()
        if self.era == "modern":
            r = self._request(method, self._meta(params), MCP_TIMEOUT, schema=schema)
            kind = r.get("resultType", "complete") if isinstance(r, dict) else "complete"
            if kind == "input_required":
                raise RunError(f"The {self.describe()} wants more input for {method} (a question for you, or a model call), "
                               "which Second Thought can't give it yet.")
            if kind != "complete":
                raise RunError(f"The {self.describe()} gave a kind of result this runtime doesn't know (“{kind}”).")
            return r
        return self._request(method, params or {}, MCP_TIMEOUT, schema=schema)

    def list_tools(self):
        if self.tools is None:
            tools, cursor = [], None
            for _ in range(50):
                r = self.request("tools/list", {"cursor": cursor} if cursor else {})
                for t in r.get("tools") or []:
                    if isinstance(t, dict) and isinstance(t.get("name"), str) and t["name"]:
                        if self.checks_headers() and _header_params(t.get("inputSchema") or {}) is None:
                            print(f"  ({self.describe()}: left out its tool “{t['name']}”, whose x-mcp-header settings are invalid)", flush=True)
                            continue
                        tools.append(t)
                cursor = r.get("nextCursor")
                if not cursor or len(tools) >= MCP_MAX_TOOLS:
                    break
            self.tools = tools[:MCP_MAX_TOOLS]
        return self.tools

    def checks_headers(self):
        return False

    def call_tool(self, name, args):
        schema = next((t.get("inputSchema") for t in (self.tools or []) if t.get("name") == name), None)
        try:
            r = self.request("tools/call", {"name": name, "arguments": args}, schema=schema)
        except _RPCError as e:
            return f"The {self.describe()} refused: {e.message}", True
        return mcp_result_text(r if isinstance(r, dict) else {})


class _MCPStdio(_MCPServer):
    """A server this program starts, talking over its standard input and output, one JSON message a line."""

    def __init__(self, name, command):
        super().__init__(name)
        self.command = command
        argv = shlex.split(command, posix=os.name != "nt")
        if os.name == "nt":  # Windows-style splitting keeps the quotes round a part: take them off
            argv = [a[1:-1] if len(a) > 1 and a[0] == a[-1] == '"' else a for a in argv]
        if not argv:
            raise RunError(f"{mcp_env_name(name)} is empty. Put the command that starts the server there.")
        exe = shutil.which(argv[0]) or argv[0]
        try:
            self.proc = subprocess.Popen([exe] + argv[1:], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                         env=dict(os.environ))
        except OSError as e:
            raise RunError(f"The {self.describe()} couldn't be started ({mcp_env_name(name)} = {command}): {e}") from None
        self._waiting, self._wlock, self._err, self._dead = {}, threading.Lock(), [], False
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=self._read_err, daemon=True).start()
        atexit.register(self.close)

    def describe(self):
        return f"MCP server “{self.name}” ({_short(self.command, 60)})"

    def _send(self, msg):
        data = (json.dumps(msg, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        with self._wlock:
            try:
                self.proc.stdin.write(data)
                self.proc.stdin.flush()
            except (OSError, ValueError):
                self._dead = True

    def _read(self):
        for line in self.proc.stdout:
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if not isinstance(msg, dict):
                continue
            if "method" in msg and "id" in msg:  # an earlier-era server asking something (it may ping)
                if msg["method"] == "ping":
                    self._send({"jsonrpc": "2.0", "id": msg["id"], "result": {}})
                else:
                    self._send({"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": "Not supported by this client"}})
            elif "id" in msg and msg["id"] in self._waiting:
                box = self._waiting[msg["id"]]
                box.append(msg)
                box[0].set()
        self._dead = True
        for box in list(self._waiting.values()):
            box[0].set()

    def _read_err(self):
        for line in self.proc.stderr:
            self._err = (self._err + [line.decode("utf-8", "replace").rstrip()])[-20:]

    def _stopped(self):
        tail = " ".join(x for x in self._err[-5:] if x)
        return RunError(f"The {self.describe()} stopped" + (f": {_short(tail, 300)}" if tail else ".") +
                        f" Check {mcp_env_name(self.name)} {WHERE_KEYS}.")

    def _request(self, method, params, timeout, legacy=False, schema=None):
        if self._dead:
            raise self._stopped()
        rid = self._id()
        box = [threading.Event()]
        self._waiting[rid] = box
        self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        try:
            if not box[0].wait(timeout):
                if self.era:  # before the era is known, an earlier-era server mustn't be sent anything but its handshake
                    self._send({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": rid, "reason": "timed out"}})
                raise _NoAnswer()
        finally:
            self._waiting.pop(rid, None)
        if len(box) < 2:
            raise self._stopped()
        msg = box[1]
        if "error" in msg:
            e = msg["error"] if isinstance(msg["error"], dict) else {}
            raise _RPCError(e.get("code"), to_str(e.get("message")) or "error", e.get("data"))
        return msg.get("result") or {}

    def _notify(self, method, params=None):
        self._send({"jsonrpc": "2.0", "method": method, **({"params": params} if params else {})})

    def _find_era(self):
        try:
            r = self._request("server/discover", self._meta({}), MCP_PROBE_SECONDS)
            self.era, self.version = "modern", MCP_MODERN
            self._modern_or_legacy([v for v in r.get("supportedVersions") or [] if isinstance(v, str)] or [MCP_MODERN])
            return
        except _RPCError as e:
            if e.code in MCP_MODERN_ERRORS:
                self._modern_or_legacy(self._versions(e))
                return
            timed_out = False
        except _NoAnswer:
            timed_out = True
        try:
            self._initialize()
        except _RPCError:
            if not timed_out:
                raise
            # It was slow to start (npx fetching it, say), not old: ask again, giving it the full time.
            r = self._request("server/discover", self._meta({}), MCP_TIMEOUT)
            self.era, self.version = "modern", MCP_MODERN
        except _NoAnswer:
            raise RunError(f"The {self.describe()} didn't answer.") from None

    def close(self):
        p = self.proc
        if p.poll() is None:
            try:
                p.stdin.close()
                p.wait(3)
            except (OSError, subprocess.TimeoutExpired, ValueError):
                p.terminate()
                try:
                    p.wait(3)
                except subprocess.TimeoutExpired:
                    p.kill()


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # the token must never follow a redirect elsewhere
        raise urllib.error.HTTPError(req.full_url, code, f"redirected to {newurl}; give the final address instead", headers, fp)


class _MCPHttp(_MCPServer):
    """A server at an address, over Streamable HTTP: each message its own POST; replies as JSON or an SSE stream."""

    def __init__(self, name, url, token=""):
        super().__init__(name)
        self.url, self.token, self.session = url, token, None
        self._open = urllib.request.build_opener(_NoRedirects).open

    def describe(self):
        return f"MCP server “{self.name}” ({_short(self.url, 60)})"

    def checks_headers(self):
        return self.era == "modern"

    def _headers(self, method, params, schema, legacy):
        h = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = "Bearer " + self.token
        if not legacy and self.era != "legacy":
            h["MCP-Protocol-Version"] = MCP_MODERN
            h["Mcp-Method"] = method
            name = (params or {}).get("name") if method in ("tools/call", "prompts/get") else (params or {}).get("uri") if method == "resources/read" else None
            if name is not None:
                h["Mcp-Name"] = _header_value(name)
            if method == "tools/call" and schema:
                args = (params or {}).get("arguments") or {}
                for header, path in _header_params(schema) or []:
                    v = args
                    for k in path:
                        v = v.get(k) if isinstance(v, dict) else None
                    if v is not None:
                        h["Mcp-Param-" + header] = _header_value(v)
        elif self.era == "legacy":
            h["MCP-Protocol-Version"] = self.version
            if self.session:
                h["Mcp-Session-Id"] = self.session
        return h

    def _post(self, msg, headers, timeout):
        """Sends one message. Gives (status, the reply to it or None)."""
        req = urllib.request.Request(self.url, data=json.dumps(msg, ensure_ascii=False).encode("utf-8"), headers=headers, method="POST")
        try:
            resp = self._open(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            try:
                body = json.loads(e.read() or b"null")
            except ValueError:
                body = None
            return e.code, body
        except (urllib.error.URLError, OSError) as e:
            raise RunError(f"The {self.describe()} couldn't be reached: {getattr(e, 'reason', e)}") from None
        with resp:
            if resp.headers.get("Mcp-Session-Id"):
                self.session = resp.headers["Mcp-Session-Id"]
            if resp.status == 202 or "id" not in msg:
                return resp.status, None
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if "text/event-stream" in ctype:
                return resp.status, self._from_stream(resp, msg["id"], timeout)
            try:
                body = json.loads(resp.read() or b"null")
            except ValueError:
                raise RunError(f"The {self.describe()} sent a reply that isn't JSON.") from None
            if isinstance(body, list):  # an early server answering in a batch
                body = next((m for m in body if isinstance(m, dict) and m.get("id") == msg["id"]), None)
            return resp.status, body

    def _from_stream(self, resp, rid, timeout):
        data, deadline = [], time.time() + timeout
        for raw in resp:
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            if line.startswith(":"):
                continue
            if line.startswith("data:"):
                data.append(line[5:].lstrip(" "))
                continue
            if line or not data:
                continue
            try:
                m = json.loads("\n".join(data))
            except ValueError:
                m = None
            data = []
            if isinstance(m, dict):
                if m.get("id") == rid and ("result" in m or "error" in m):
                    return m
                if "method" in m and "id" in m:  # an earlier-era server asking something on the stream
                    reply = {"jsonrpc": "2.0", "id": m["id"]}
                    reply.update({"result": {}} if m["method"] == "ping" else {"error": {"code": -32601, "message": "Not supported by this client"}})
                    self._post(reply, self._headers("", {}, None, True), 30)
            if time.time() > deadline:
                break
        if data:  # the last event, without the blank line that should end it
            try:
                m = json.loads("\n".join(data))
                if isinstance(m, dict) and m.get("id") == rid:
                    return m
            except ValueError:
                pass
        return None

    def _request(self, method, params, timeout, legacy=False, schema=None):
        msg = {"jsonrpc": "2.0", "id": self._id(), "method": method, "params": params}
        status, body = self._post(msg, self._headers(method, params, schema, legacy), timeout)
        if status == 404 and self.era == "legacy" and self.session and method != "initialize":
            self.session = None  # the session ended: start a new one, once
            self._initialize(self.version)
            msg["id"] = self._id()
            status, body = self._post(msg, self._headers(method, params, schema, legacy), timeout)
        if status in (401, 403):
            raise RunError(f"The {self.describe()} refused the request ({status}). Check {mcp_env_name(self.name)}_TOKEN {WHERE_KEYS}.")
        err = body.get("error") if isinstance(body, dict) else None
        if isinstance(err, dict):
            raise _RPCError(err.get("code"), to_str(err.get("message")) or "error", err.get("data"))
        if status >= 400:
            raise _RPCError(None, f"HTTP {status}", status)
        if not isinstance(body, dict) or "result" not in body:
            raise RunError(f"The {self.describe()} didn't reply to {method}.")
        return body.get("result") or {}

    def _notify(self, method, params=None):
        msg = {"jsonrpc": "2.0", "method": method, **({"params": params} if params else {})}
        self._post(msg, self._headers(method, params, None, True), 30)

    def _find_era(self):
        try:
            r = self._request("server/discover", self._meta({}), MCP_TIMEOUT)
            self.era, self.version = "modern", MCP_MODERN
            self._modern_or_legacy([v for v in r.get("supportedVersions") or [] if isinstance(v, str)] or [MCP_MODERN])
            return
        except _RPCError as e:
            if e.code in MCP_MODERN_ERRORS:
                self.era = "modern"
                self._modern_or_legacy(self._versions(e))
                return
        try:
            self._initialize()
        except _RPCError as e:
            if e.data in (404, 405):
                raise RunError(f"The {self.describe()} looks like it uses MCP's old HTTP+SSE way of connecting, "
                               "which Second Thought doesn't speak. Check the address, or use a newer server.") from None
            raise RunError(f"The {self.describe()} wouldn't start talking: {e.message}") from None


def mcp_server(name):
    """A server from its MCP_<NAME> setting: a command (started here) or an http(s) address."""
    key = mcp_env_name(name)
    if key == "MCP_":
        raise RunError("An MCP tool block needs the server's name.")
    where = os.environ.get(key, "").strip()
    if not where:
        raise RunError(f"The agent's MCP server “{to_str(name).strip()}” isn't set up. Put {key} = <the command that starts it, "
                       f"or its https:// address> {WHERE_KEYS}.")
    if re.match(r"^https?://", where, re.I):
        return _MCPHttp(to_str(name).strip(), where, os.environ.get(key + "_TOKEN", "").strip())
    return _MCPStdio(to_str(name).strip(), where)


class MCPTools:
    """MCP servers' tools for the agent. Part of Runtime."""

    def _mcp(self, name):
        servers = self.__dict__.setdefault("_mcp_servers", {})
        key = mcp_env_name(name)
        if key not in servers:
            servers[key] = mcp_server(name)
        return servers[key]

    async def mcp_tools(self, name):
        """The tools a server offers, as it describes them (name, description, inputSchema, annotations)."""
        server = self._mcp(name)
        try:
            tools = await asyncio.to_thread(server.list_tools)
        except _RPCError as e:
            raise RunError(f"The {server.describe()} wouldn't list its tools: {e.message}") from None
        except _NoAnswer:
            raise RunError(f"The {server.describe()} didn't answer when asked for its tools.") from None
        self.log(f"MCP server “{server.name}”", f"{len(tools)} tool{'s' if len(tools) != 1 else ''}: " +
                 _short(", ".join(t["name"] for t in tools), 300) + f"  ·  MCP {server.version}", "connected", calls=False)
        return tools

    async def mcp_call(self, name, tool, args):
        """Calls one tool. Gives (text, failed). Journaled, so resuming a stopped run doesn't call it twice."""
        server = self._mcp(name)

        async def live():
            try:
                text, failed = await asyncio.to_thread(server.call_tool, tool, args)
            except _NoAnswer:
                text, failed = f"The {server.describe()} didn't answer within {MCP_TIMEOUT:g} seconds.", True
            return [text, failed]
        out = await self._journaled("mcp", self._key(mcp_env_name(name), tool, args), live)
        return out[0], bool(out[1])

    @staticmethod
    def check_mcp_input(inp, schema):
        """Light checks before calling an MCP tool (the server checks fully): an object, its required inputs there, and
        numbers or yes/no written as text turned into numbers and true/false where the schema wants them."""
        if not isinstance(inp, dict):
            return "the input should be an object", None
        schema = schema if isinstance(schema, dict) else {}
        props = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        for k in schema.get("required") or []:
            if inp.get(k) is None:
                return f"“{k}” is missing", None
        if schema.get("additionalProperties") is False:
            extra = [k for k in inp if k not in props]
            if extra:
                return f"there's no input called “{extra[0]}” (its inputs are: {', '.join(props) or 'none'})", None
        out = {}
        for k, v in inp.items():
            t = (props.get(k) or {}).get("type") if isinstance(props.get(k), dict) else None
            if t in ("number", "integer") and isinstance(v, str) and re.fullmatch(r"\s*-?\d+(\.\d+)?\s*", v):
                v = float(v) if "." in v else int(v)
            elif t == "boolean" and isinstance(v, str) and v.strip().lower() in ("true", "yes", "false", "no"):
                v = v.strip().lower() in ("true", "yes")
            out[k] = v
        return None, out
