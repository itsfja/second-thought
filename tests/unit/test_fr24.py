"""Flightradar24 through its own MCP server (#364), against tests/fake_fr24.py: every tool only reads, so none of the
known ones asks, even with (no asking); a tool the safe list has never seen asks first, the safe way round like
Kraken's (#309). --doctor checks npx, FR24_API_KEY (without spending a credit on it) and counts what can change."""
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

FAKE = f'"{sys.executable}" "{support.ROOT / "tests" / "fake_fr24.py"}"'


class AtKeyboard:
    def isatty(self):
        return True


class Lists(unittest.TestCase):
    def test_every_tool_the_server_offers_is_on_the_safe_list(self):
        for name in ("get_live_flights_positions_light", "get_live_flights_positions_full", "get_live_flights_count",
                     "get_historic_flights_positions_full", "get_historic_flights_positions_light",
                     "get_historic_flights_count", "get_flight_summary_full", "get_flight_summary_light",
                     "get_flight_summary_count", "get_flight_tracks", "get_airline_info",
                     "get_airport_info_light", "get_airport_info_full"):
            self.assertIn(name, SAFETY["mcp_fr24_safe"], name)

    def test_the_block_starts_the_official_server(self):
        self.assertEqual(mcp.FR24_COMMANDS["read"], "npx -y @flightradar24/fr24api-mcp")
        for c in mcp.FR24_COMMANDS.values():
            self.assertNotIn("--allow-dangerous", c)

    def test_the_server_is_recognised_by_name_or_command(self):
        self.assertTrue(mcp.mcp_is_fr24("flightradar24"))
        self.assertTrue(mcp.mcp_is_fr24("FR24"))
        self.assertTrue(mcp.mcp_is_fr24("anything", "npx -y @flightradar24/fr24api-mcp"))
        self.assertFalse(mcp.mcp_is_fr24("github"))
        self.assertFalse(mcp.mcp_is_fr24("files", "npx -y @modelcontextprotocol/server-filesystem"))

    def test_a_tool_we_dont_know_asks_even_with_no_asking(self):
        rt = Runtime()
        tools = [{"name": "get_live_flights_positions_light", "annotations": {"readOnlyHint": True}},
                 {"name": "get_future_thing", "annotations": {"readOnlyHint": True}}]
        cat = rt._agent_tools([{"kind": "mcp", "server": "flightradar24", "ask": "never"}], {"flightradar24": tools})
        asks = {spec[2][1]["tool"]: spec[3] for spec in cat.values()}
        self.assertEqual(asks, {"get_live_flights_positions_light": False, "get_future_thing": True})


class Agent(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(dir=support.TMP)
        self.log = os.path.join(self.tmp, "fr24.log")

    def calls(self):
        import json
        if not os.path.exists(self.log):
            return []
        with open(self.log, encoding="utf-8") as f:
            return [m["params"] for m in map(json.loads, f) if m.get("method") == "tools/call"]

    def run_agent(self, script, answers=(), here=True, env=None, command=None):
        r = Runtime()
        r.reset()
        r.log = lambda *a, **k: None
        replies, self.asked = iter(script), []

        async def fake_call(prompt, want_json=False, *a, **k):
            self.prompt = prompt
            return next(replies)

        async def fake_confirm(what):
            self.asked.append(what)
            return answers[len(self.asked) - 1] if len(self.asked) <= len(answers) else True
        r._call, r.confirm = fake_call, fake_confirm
        tool = {"kind": "mcp", "server": "flightradar24", "ask": "never", "command": command or FAKE}
        base = {"FAKE_MCP_LOG": self.log}
        with mock.patch.dict(os.environ, dict(base, **(env or {}))), mock.patch.object(sys, "stdin", AtKeyboard() if here else sys.stdin):
            for k in ("MCP_FLIGHTRADAR24", "GITHUB_ACTIONS"):
                if k not in (env or {}):
                    os.environ.pop(k, None)
            asyncio.run(r.agent("Is Mum's flight on time?", 5, [tool]))
        for s in r.__dict__.get("_mcp_servers", {}).values():
            s.close()
        return r

    def test_reading_flights_doesnt_ask(self):
        r = self.run_agent([{"tool": "flightradar24_get_live_flights_positions_light", "input": {"flights": "BA123"}},
                            {"tool": "flightradar24_get_airport_info_light", "input": {"code": "LHR"}},
                            {"done": True, "answer": "BA123 lands at 14:30 UTC."}])
        self.assertEqual(self.asked, [])
        self.assertEqual([s["status"] for s in r.agent_trace], ["done", "done", "answer"])
        self.assertIn("14:30", r.agent_trace[2]["result"])

    def test_a_tool_the_list_has_never_seen_asks_even_with_no_asking(self):
        r = self.run_agent([{"tool": "flightradar24_get_future_thing", "input": {}},
                            {"done": True, "answer": "ok"}])
        self.assertEqual(len(self.asked), 1)
        self.assertIn("get_future_thing", self.asked[0])
        self.assertEqual(self.calls()[-1]["name"], "get_future_thing")

    def test_no_means_no(self):
        r = self.run_agent([{"tool": "flightradar24_get_future_thing", "input": {}},
                            {"done": True, "answer": "ok"}], answers=[False])
        self.assertEqual(r.agent_trace[0]["status"], "refused")
        self.assertEqual(self.calls(), [])

    def test_mcp_flightradar24_wins_over_the_blocks_command(self):
        self.run_agent([{"tool": "flightradar24_get_live_flights_positions_light", "input": {"flights": "BA123"}},
                        {"done": True, "answer": "ok"}],
                       env={"MCP_FLIGHTRADAR24": FAKE}, command="npx @flightradar24/that-does-not-exist")
        self.assertEqual(self.calls()[-1]["name"], "get_live_flights_positions_light")


class Doctor(unittest.TestCase):
    def check(self, env):
        r = Runtime()
        r.reset()
        r.log = lambda *a, **k: None
        r.__dict__["_mcp_defaults"] = {"MCP_FLIGHTRADAR24": FAKE}
        with mock.patch.dict(os.environ, dict({"FAKE_MCP_LOG": os.devnull}, **env)):
            for k in ("MCP_FLIGHTRADAR24", "FR24_API_KEY"):
                if k not in env:
                    os.environ.pop(k, None)
            try:
                [(area, run)] = asyncio.run(r._doctor_connections([], ["flightradar24"]))
                return asyncio.run(run())
            finally:
                for s in r.__dict__.get("_mcp_servers", {}).values():
                    s.close()

    def test_node_missing(self):
        with mock.patch("shutil.which", return_value=None), self.assertRaises(RunError) as e:
            self.check({})
        self.assertIn("Node.js isn't installed", str(e.exception))

    def test_no_key_is_a_fail(self):
        with mock.patch("shutil.which", return_value="/usr/bin/npx"), self.assertRaises(RunError) as e:
            self.check({})
        self.assertIn("FR24_API_KEY", str(e.exception))

    def test_the_key_is_reported_without_spending_a_credit(self):
        with mock.patch("shutil.which", return_value="/usr/bin/npx"):
            text = self.check({"FR24_API_KEY": "good"})
        self.assertIn("FR24_API_KEY is set", text)
        self.assertIn("credits", text)
        self.assertNotIn("can change things", text)  # every tool the stand-in offers is on the safe list


if __name__ == "__main__":
    unittest.main()
