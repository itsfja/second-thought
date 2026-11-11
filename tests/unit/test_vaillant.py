"""Vaillant through the unofficial read-only MCP server (#363), against tests/fake_vaillant.py: the server's four
read-only tools don't ask, but a tool the safe list has never seen asks first, even with (no asking) — the API behind
it is unofficial and reverse-engineered, so it can change whenever Vaillant changes the app. --doctor counts what can
change things, which for this server should be nothing."""
import asyncio
import os
import sys
import tempfile
import unittest
from unittest import mock

import support
from second_thought import mcp
from second_thought.core import SAFETY, RunError
from second_thought.runtime import Runtime

FAKE = f'"{sys.executable}" "{support.ROOT / "tests" / "fake_vaillant.py"}"'


class AtKeyboard:
    def isatty(self):
        return True


class Lists(unittest.TestCase):
    def test_every_tool_the_server_offers_is_on_the_safe_list(self):
        for name in ("vaillant_get_status", "vaillant_get_devices", "vaillant_get_energy_report", "vaillant_get_diagnostics"):
            self.assertIn(name, SAFETY["mcp_vaillant_safe"], name)

    def test_the_server_is_recognised_by_name_or_command(self):
        self.assertTrue(mcp.mcp_is_vaillant("vaillant"))
        self.assertTrue(mcp.mcp_is_vaillant("unofficial-mcp4vaillant"))
        self.assertTrue(mcp.mcp_is_vaillant("anything", "python -m vaillant_mcp_server"))
        self.assertFalse(mcp.mcp_is_vaillant("github"))
        self.assertFalse(mcp.mcp_is_vaillant("files", "npx -y @modelcontextprotocol/server-filesystem"))

    def test_a_tool_we_dont_know_asks_even_with_no_asking(self):
        rt = Runtime()
        tools = [{"name": "vaillant_get_status", "annotations": {"readOnlyHint": True}},
                 {"name": "vaillant_set_quick_mode", "annotations": {"readOnlyHint": True}}]
        cat = rt._agent_tools([{"kind": "mcp", "server": "vaillant", "ask": "never"}], {"vaillant": tools})
        asks = {spec[2][1]["tool"]: spec[3] for spec in cat.values()}
        self.assertEqual(asks, {"vaillant_get_status": False, "vaillant_set_quick_mode": True})


class Agent(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(dir=support.TMP)
        self.log = os.path.join(self.tmp, "vaillant.log")

    def calls(self):
        import json
        if not os.path.exists(self.log):
            return []
        with open(self.log, encoding="utf-8") as f:
            return [m["params"] for m in map(json.loads, f) if m.get("method") == "tools/call"]

    def run_agent(self, script, answers=(), env=None):
        r = Runtime()
        r.reset()
        r.log = lambda *a, **k: None
        replies, self.asked = iter(script), []

        async def fake_call(prompt, want_json=False, *a, **k):
            return next(replies)

        async def fake_confirm(what):
            self.asked.append(what)
            return answers[len(self.asked) - 1] if len(self.asked) <= len(answers) else True
        r._call, r.confirm = fake_call, fake_confirm
        tool = {"kind": "mcp", "server": "vaillant", "ask": "never", "command": FAKE}
        with mock.patch.dict(os.environ, dict({"FAKE_MCP_LOG": self.log}, **(env or {}))), \
                mock.patch.object(sys, "stdin", AtKeyboard()):
            for k in ("MCP_VAILLANT", "GITHUB_ACTIONS"):
                if k not in (env or {}):
                    os.environ.pop(k, None)
            asyncio.run(r.agent("How's the heating doing?", 5, [tool]))
        for s in r.__dict__.get("_mcp_servers", {}).values():
            s.close()
        return r

    def test_reading_the_heating_doesnt_ask(self):
        r = self.run_agent([{"tool": "vaillant_vaillant_get_status", "input": {}},
                            {"tool": "vaillant_vaillant_get_energy_report", "input": {"time_range": "week"}},
                            {"done": True, "answer": "COP 3.76 this week."}])
        self.assertEqual(self.asked, [])
        self.assertEqual([s["status"] for s in r.agent_trace], ["done", "done", "answer"])
        self.assertIn("3.76", r.agent_trace[2]["result"])

    def test_a_tool_the_list_has_never_seen_asks_even_with_no_asking(self):
        r = self.run_agent([{"tool": "vaillant_vaillant_set_quick_mode", "input": {}},
                            {"done": True, "answer": "ok"}])
        self.assertEqual(len(self.asked), 1)
        self.assertIn("vaillant_set_quick_mode", self.asked[0])
        self.assertEqual(self.calls()[-1]["name"], "vaillant_set_quick_mode")

    def test_no_means_no(self):
        r = self.run_agent([{"tool": "vaillant_vaillant_set_quick_mode", "input": {}},
                            {"done": True, "answer": "ok"}], answers=[False])
        self.assertEqual(r.agent_trace[0]["status"], "refused")
        self.assertEqual(self.calls(), [])


class Doctor(unittest.TestCase):
    def check(self, env):
        r = Runtime()
        r.reset()
        r.log = lambda *a, **k: None
        r.__dict__["_mcp_defaults"] = {"MCP_VAILLANT": FAKE}
        with mock.patch.dict(os.environ, dict({"FAKE_MCP_LOG": os.devnull}, **(env or {}))):
            for k in ("MCP_VAILLANT",):
                if k not in env:
                    os.environ.pop(k, None)
            try:
                [(area, run)] = asyncio.run(r._doctor_connections([], ["vaillant"]))
                return asyncio.run(run())
            finally:
                for s in r.__dict__.get("_mcp_servers", {}).values():
                    s.close()

    def test_doctor_counts_nothing_that_can_change_things(self):
        text = self.check({})
        self.assertIn("5 tools", text)
        self.assertNotIn("can change things", text)  # every tool the stand-in offers is on the safe list


if __name__ == "__main__":
    unittest.main()
