"""The MCP client, against tests/fake_mcp.py in each era and over each transport, and the agent using its tools."""
import asyncio
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import support
from second_thought import mcp
from second_thought.core import RunError
from second_thought.runtime import Runtime

sys.path.insert(0, str(support.ROOT / "tests"))
import fake_mcp  # noqa: E402

FAKE = str(support.ROOT / "tests" / "fake_mcp.py")


def command(era):
    return f'"{sys.executable}" "{FAKE}" {era}'


class Logged(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(dir=support.TMP)
        self.log = os.path.join(self.tmp, "mcp.log")
        self.env = mock.patch.dict(os.environ, {"FAKE_MCP_LOG": self.log})
        self.env.start()
        fake_mcp.LOG = self.log
        self.servers = []

    def tearDown(self):
        for s in self.servers:
            if hasattr(s, "close"):
                s.close()
        self.env.stop()

    def got(self):
        with open(self.log, encoding="utf-8") as f:
            return [json.loads(x) for x in f]

    def stdio(self, era):
        s = mcp._MCPStdio("bakery", command(era))
        self.servers.append(s)
        return s


class Stdio(Logged):
    def test_current_era(self):
        s = self.stdio("modern")
        names = [t["name"] for t in s.list_tools()]
        self.assertEqual((s.era, s.version), ("modern", "2026-07-28"))
        self.assertEqual(names, ["list_loaves", "add_loaf", "fail", "bake_in"])  # both pages
        self.assertEqual(s.call_tool("add_loaf", {"name": "Rye", "grams": 900}), ("Added Rye.", False))
        self.assertEqual(s.call_tool("list_loaves", {}), ("Rye (900 g)", False))
        sent = self.got()
        self.assertEqual(sent[0]["method"], "server/discover")
        self.assertNotIn("initialize", [m.get("method") for m in sent])
        for m in sent:
            meta = m["params"]["_meta"]
            self.assertEqual(meta["io.modelcontextprotocol/protocolVersion"], "2026-07-28")
            self.assertEqual(meta["io.modelcontextprotocol/clientInfo"]["name"], "Second Thought")
            self.assertEqual(meta["io.modelcontextprotocol/clientCapabilities"], {})

    def test_earlier_era_falls_back_to_initialize_and_answers_pings(self):
        s = self.stdio("legacy")
        self.assertEqual(len(s.list_tools()), 4)
        self.assertEqual((s.era, s.version), ("legacy", "2025-11-25"))
        self.assertEqual(s.call_tool("fail", {}), ("The oven is off.", True))
        methods = [m.get("method") for m in self.got()]
        self.assertEqual(methods[:3], ["server/discover", "initialize", "notifications/initialized"])
        later = [m for m in self.got() if m.get("method") in ("tools/list", "tools/call")]
        self.assertTrue(later and all("_meta" not in (m.get("params") or {}) for m in later))
        self.assertIn({"jsonrpc": "2.0", "id": "srv-ping", "result": {}}, self.got())

    def test_a_server_that_ignores_discover(self):
        with mock.patch.object(mcp, "MCP_PROBE_SECONDS", 0.5):
            s = self.stdio("silent")
            self.assertEqual(len(s.list_tools()), 4)
        self.assertEqual(s.era, "legacy")
        self.assertNotIn("notifications/cancelled", [m.get("method") for m in self.got()])

    def test_a_slow_current_era_server_isnt_mistaken_for_an_old_one(self):
        with mock.patch.dict(os.environ, {"FAKE_MCP_SLOW": "1.5"}), mock.patch.object(mcp, "MCP_PROBE_SECONDS", 0.3):
            s = self.stdio("slow")
            self.assertEqual(len(s.list_tools()), 4)
        self.assertEqual(s.era, "modern")

    def test_unknown_tool_and_a_server_that_stops(self):
        s = self.stdio("modern")
        text, failed = s.call_tool("nope", {})
        self.assertTrue(failed and "refused" in text and "Unknown tool" in text)
        dead = mcp._MCPStdio("broken", f'"{sys.executable}" -c "import sys; print(\'bad key\', file=sys.stderr); sys.exit(3)"')
        self.servers.append(dead)
        with self.assertRaises(RunError) as e:
            dead.list_tools()
        self.assertIn("stopped", str(e.exception))
        self.assertIn("MCP_BROKEN", str(e.exception))

    def test_a_command_that_doesnt_exist(self):
        with self.assertRaises(RunError) as e:
            mcp._MCPStdio("x", "no-such-program-here --flag")
        self.assertIn("couldn't be started", str(e.exception))


class Http(Logged):
    def http(self, era, sse=False, token=""):
        url, srv = fake_mcp.start_http(era, sse, token)
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        return url, srv

    def test_current_era_headers_and_bad_tools_left_out(self):
        url, _ = self.http("modern")
        s = mcp._MCPHttp("bakery", url)
        names = [t["name"] for t in s.list_tools()]
        self.assertEqual(names, ["list_loaves", "add_loaf", "fail", "bake_in"])  # bad_header left out
        self.assertEqual(s.call_tool("bake_in", {"region": "Rhône", "loaf": "pain"}), ("Baking pain in Rhône.", False))
        call = [m for m in self.got() if m["body"].get("method") == "tools/call"][-1]["http"]
        self.assertEqual(call["Mcp-Method"], "tools/call")
        self.assertEqual(call["Mcp-Name"], "bake_in")
        self.assertEqual(call["Mcp-Param-Region"], "=?base64?" + __import__("base64").b64encode("Rhône".encode()).decode() + "?=")
        self.assertNotIn("Mcp-Session-Id", call)

    def test_streamed_replies(self):
        url, _ = self.http("modern", sse=True)
        s = mcp._MCPHttp("bakery", url)
        self.assertEqual(len(s.list_tools()), 4)
        self.assertEqual(s.call_tool("add_loaf", {"name": "Spelt"}), ("Added Spelt.", False))

    def test_earlier_era_session_and_a_new_one_when_it_ends(self):
        url, srv = self.http("legacy")
        s = mcp._MCPHttp("bakery", url)
        self.assertEqual(len(s.list_tools()), 4)
        self.assertEqual((s.era, s.session), ("legacy", "s-1"))
        srv.sessions.clear()  # the server forgets the session: the client starts a new one, once
        self.assertEqual(s.call_tool("add_loaf", {"name": "Rye"}), ("Added Rye.", False))
        self.assertEqual(s.session, "s-2")
        later = [m["http"] for m in self.got() if m["body"].get("method") == "tools/call"]
        self.assertEqual(later[-1]["Mcp-Session-Id"], "s-2")
        self.assertEqual(later[-1]["Mcp-Protocol-Version"], "2025-11-25")

    def test_earlier_era_streamed(self):
        url, _ = self.http("legacy", sse=True)
        s = mcp._MCPHttp("bakery", url)
        self.assertEqual(s.call_tool("fail", {}), ("The oven is off.", True))

    def test_token(self):
        url, _ = self.http("modern", token="sekrit")
        with self.assertRaises(RunError) as e:
            mcp._MCPHttp("tracker", url).list_tools()
        self.assertIn("MCP_TRACKER_TOKEN", str(e.exception))
        self.assertEqual(len(mcp._MCPHttp("tracker", url, "sekrit").list_tools()), 4)

    def test_nothing_there(self):
        with self.assertRaises(RunError) as e:
            mcp._MCPHttp("gone", "http://127.0.0.1:9/mcp").list_tools()
        self.assertIn("couldn't be reached", str(e.exception))


class Pieces(unittest.TestCase):
    def test_setting_names_and_choosing_a_transport(self):
        self.assertEqual(mcp.mcp_env_name(" my files "), "MCP_MY_FILES")
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MCP_NOWHERE", None)
            with self.assertRaises(RunError) as e:
                mcp.mcp_server("nowhere")
            self.assertIn("MCP_NOWHERE =", str(e.exception))
        with mock.patch.dict(os.environ, {"MCP_T": "https://x.test/mcp", "MCP_T_TOKEN": "k"}):
            s = mcp.mcp_server("t")
            self.assertIsInstance(s, mcp._MCPHttp)
            self.assertEqual(s.token, "k")

    def test_header_values(self):
        for v, want in [("us-west1", "us-west1"), ("Hello, 世界", "=?base64?SGVsbG8sIOS4lueVjA==?="), (" padded ", "=?base64?IHBhZGRlZCA=?="),
                        ("line1\nline2", "=?base64?bGluZTEKbGluZTI=?="), ("=?base64?literal?=", "=?base64?PT9iYXNlNjQ/bGl0ZXJhbD89?="),
                        (42, "42"), (True, "true")]:
            with self.subTest(v=v):
                self.assertEqual(mcp._header_value(v), want)

    def test_header_params_validation(self):
        good = {"type": "object", "properties": {"a": {"type": "object", "properties": {"b": {"type": "string", "x-mcp-header": "B"}}}}}
        self.assertEqual(mcp._header_params(good), [("B", ["a", "b"])])
        for bad in ({"properties": {"n": {"type": "number", "x-mcp-header": "N"}}},
                    {"properties": {"l": {"type": "array", "items": {"type": "string", "x-mcp-header": "L"}}}},
                    {"properties": {"x": {"type": "string", "x-mcp-header": "a b"}}},
                    {"properties": {"x": {"type": "string", "x-mcp-header": "Dup"}, "y": {"type": "string", "x-mcp-header": "dup"}}},
                    {"anyOf": [{"properties": {"x": {"type": "string", "x-mcp-header": "X"}}}]}):
            with self.subTest(bad=bad):
                self.assertIsNone(mcp._header_params(bad))
        self.assertEqual(mcp._header_params({"type": "object"}), [])

    def test_result_text(self):
        r = {"content": [{"type": "text", "text": "hi"}, {"type": "image", "data": "x", "mimeType": "image/png"},
                         {"type": "resource_link", "uri": "file:///a.txt", "name": "a.txt"},
                         {"type": "resource", "resource": {"uri": "file:///b", "text": "inside b"}}]}
        text, failed = mcp.mcp_result_text(r)
        self.assertFalse(failed)
        self.assertEqual(text.split("\n"), ["hi", "[image from the tool (image/png): not shown to the agent]", "Link: a.txt (file:///a.txt)", "inside b"])
        self.assertEqual(mcp.mcp_result_text({"structuredContent": {"ok": 1}}), ('{"ok": 1}', False))
        self.assertEqual(mcp.mcp_result_text({}), ("(the tool gave no result)", False))
        long, _ = mcp.mcp_result_text({"content": [{"type": "text", "text": "x" * (mcp.MCP_MAX_RESULT + 10)}]})
        self.assertIn("cut", long)

    def test_input_checks(self):
        schema = {"type": "object", "properties": {"n": {"type": "integer"}, "ok": {"type": "boolean"}, "o": {"type": "object"}},
                  "required": ["n"], "additionalProperties": False}
        self.assertEqual(Runtime.check_mcp_input({"n": "4", "ok": "yes", "o": {"a": 1}}, schema), (None, {"n": 4, "ok": True, "o": {"a": 1}}))
        self.assertIn("“n” is missing", Runtime.check_mcp_input({}, schema)[0])
        self.assertIn("no input called “z”", Runtime.check_mcp_input({"n": 1, "z": 2}, schema)[0])
        self.assertEqual(Runtime.check_mcp_input({"anything": [1]}, {"type": "object"}), (None, {"anything": [1]}))


class Agent(Logged):
    """The agent with an MCP server's tools: named after the server, asking before tools that change things."""

    def run_agent(self, script, ask="changes", answers=()):
        r = Runtime()
        r.reset()
        r.log = lambda *a, **k: None
        replies, asked = iter(script), []

        async def fake_call(prompt, want_json=False, *a, **k):
            self.prompt = prompt
            return next(replies)

        async def fake_confirm(what):
            asked.append(what)
            return answers[len(asked) - 1] if len(asked) <= len(answers) else True
        r._call, r.confirm = fake_call, fake_confirm
        with mock.patch.dict(os.environ, {"MCP_BAKERY": command("modern")}):
            asyncio.run(r.agent("Bake", 4, [{"kind": "mcp", "server": "bakery", "ask": ask}]))
        for s in r.__dict__.get("_mcp_servers", {}).values():
            s.close()
        return r, asked

    def test_tools_are_offered_and_used(self):
        r, asked = self.run_agent([{"tool": "bakery_list_loaves", "input": {}},
                                   {"tool": "bakery_add_loaf", "input": {"name": "Rye", "grams": "900"}},
                                   {"done": True, "answer": "Baked."}])
        self.assertIn("- bakery_add_loaf(name, grams): Adds a loaf to the bake list. (from the MCP server “bakery”)", self.prompt)
        self.assertEqual([s["tool"] for s in r.agent_trace], ["bakery_list_loaves", "bakery_add_loaf", ""])
        self.assertEqual(len(asked), 1)  # only the tool that isn't read-only
        self.assertIn("bakery_add_loaf", asked[0])
        self.assertIn("Added Rye.", r.agent_trace[1]["result"])
        calls = [m for m in self.got() if m.get("method") == "tools/call"]
        self.assertEqual(calls[-1]["params"]["arguments"], {"name": "Rye", "grams": 900})  # "900" became a number

    def test_no_means_no(self):
        r, asked = self.run_agent([{"tool": "bakery_add_loaf", "input": {"name": "Rye"}}, {"done": True, "answer": "ok"}], answers=[False])
        self.assertEqual(r.agent_trace[0]["status"], "refused")
        self.assertNotIn("tools/call", [m.get("method") for m in self.got()])

    def test_asking_modes_and_errors(self):
        _, asked = self.run_agent([{"tool": "bakery_list_loaves", "input": {}}, {"done": True, "answer": "ok"}], ask="every")
        self.assertEqual(len(asked), 1)
        _, asked = self.run_agent([{"tool": "bakery_add_loaf", "input": {"name": "Rye"}}, {"done": True, "answer": "ok"}], ask="never")
        self.assertEqual(asked, [])
        r, _ = self.run_agent([{"tool": "bakery_fail", "input": {}}, {"tool": "bakery_add_loaf", "input": {}}, {"done": True, "answer": "ok"}])
        self.assertEqual([s["status"] for s in r.agent_trace], ["tool error", "bad input", "answer"])

    def test_a_server_that_isnt_set_up_stops_the_run_plainly(self):
        r = Runtime()
        r.reset()
        r.log = lambda *a, **k: None
        os.environ.pop("MCP_NOT_HERE", None)
        with self.assertRaises(RunError) as e:
            asyncio.run(r.agent("x", 2, [{"kind": "mcp", "server": "not here", "ask": "changes"}]))
        self.assertIn("MCP_NOT_HERE", str(e.exception))


if __name__ == "__main__":
    unittest.main()
