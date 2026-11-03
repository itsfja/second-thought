"""Kraken through its MCP server (#262), against tests/fake_kraken.py: prices, the account and paper trading don't ask;
tools that can move real money always ask, even with (no asking), the person (never the agent) sets "acknowledged",
and with nobody there to say yes they don't run at all. --doctor checks kraken-cli, the key and --allow-dangerous."""
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

FAKE = f'"{sys.executable}" "{support.ROOT / "tests" / "fake_kraken.py"}"'


class AtKeyboard:
    def isatty(self):
        return True


class Money(unittest.TestCase):
    def test_which_tools_move_money(self):
        self.assertTrue(mcp.mcp_money({"name": "kraken_order_buy"}))
        self.assertTrue(mcp.mcp_money({"name": "kraken_withdraw"}))
        self.assertTrue(mcp.mcp_money({"name": "anything", "inputSchema": {"properties": {"acknowledged": {"type": "boolean"}}}}))
        self.assertFalse(mcp.mcp_money({"name": "kraken_ticker"}))
        self.assertFalse(mcp.mcp_money({"name": "kraken_paper_buy"}))
        for prefix in ("kraken_order_", "kraken_futures_order_", "kraken_withdraw", "kraken_earn_allocate", "kraken_subaccount_transfer"):
            self.assertTrue(any(n.startswith(prefix) for n in SAFETY["mcp_money"]), prefix)

    def test_the_block_starts_read_only_services_unless_live_is_chosen(self):
        self.assertEqual(mcp.KRAKEN_COMMANDS["read"], "kraken mcp -s market,account,paper")
        self.assertNotIn("trade", mcp.KRAKEN_COMMANDS["read"])
        self.assertIn("trade", mcp.KRAKEN_COMMANDS["live"])
        for c in mcp.KRAKEN_COMMANDS.values():
            self.assertNotIn("funding", c)
            self.assertNotIn("--allow-dangerous", c)


class Agent(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(dir=support.TMP)
        self.log = os.path.join(self.tmp, "mcp.log")

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
        replies, self.asked, self.money_asked = iter(script), [], []

        async def fake_call(prompt, want_json=False, *a, **k):
            self.prompt = prompt
            return next(replies)

        async def fake_confirm(what):
            self.asked.append(what)
            return True

        async def fake_approve(what):
            self.money_asked.append(what)
            return answers[len(self.money_asked) - 1] if len(self.money_asked) <= len(answers) else True
        r._call, r.confirm, r._approve_live = fake_call, fake_confirm, fake_approve
        tool = {"kind": "mcp", "server": "kraken", "ask": "never", "command": command or FAKE}
        base = {"FAKE_MCP_LOG": self.log}
        with mock.patch.dict(os.environ, dict(base, **(env or {}))), mock.patch.object(sys, "stdin", AtKeyboard() if here else sys.stdin):
            os.environ.pop("MCP_KRAKEN", None) if "MCP_KRAKEN" not in (env or {}) else None
            os.environ.pop("GITHUB_ACTIONS", None) if "GITHUB_ACTIONS" not in (env or {}) else None
            asyncio.run(r.agent("Look after my crypto", 5, [tool]))
        for s in r.__dict__.get("_mcp_servers", {}).values():
            s.close()
        return r

    def test_prices_the_account_and_paper_trading_dont_ask(self):
        r = self.run_agent([{"tool": "kraken_kraken_ticker", "input": {"pair": "XBTGBP"}},
                            {"tool": "kraken_kraken_balance", "input": {}},
                            {"tool": "kraken_kraken_paper_buy", "input": {"pair": "XBTGBP", "volume": "0.01"}},
                            {"done": True, "answer": "ok"}])
        self.assertEqual(self.asked + self.money_asked, [])
        self.assertEqual([s["status"] for s in r.agent_trace], ["done", "done", "done", "answer"])
        self.assertIn("Paper: bought", r.agent_trace[2]["result"])

    def test_a_live_order_always_asks_and_only_a_yes_acknowledges_it(self):
        r = self.run_agent([{"tool": "kraken_kraken_order_buy", "input": {"pair": "XBTGBP", "volume": "0.01", "acknowledged": True}},
                            {"done": True, "answer": "ok"}])
        self.assertNotIn("acknowledged", self.prompt.split("kraken_kraken_order_buy(")[1].split(")")[0], "the agent isn't offered it")
        self.assertEqual(len(self.money_asked), 1)
        self.assertIn("real money", self.money_asked[0])
        self.assertIn("kraken_kraken_order_buy", self.money_asked[0])
        self.assertNotIn("acknowledged", self.money_asked[0], "what you're asked about is what the agent wanted, without its own say-so")
        self.assertEqual(self.calls()[-1]["arguments"], {"pair": "XBTGBP", "volume": "0.01", "acknowledged": True})
        self.assertIn("Done for real", r.agent_trace[0]["result"])

    def test_no_means_no_and_the_agents_own_acknowledged_doesnt_count(self):
        r = self.run_agent([{"tool": "kraken_kraken_withdraw", "input": {"asset": "XBT", "key": "mine", "amount": "1", "acknowledged": True}},
                            {"done": True, "answer": "ok"}], answers=[False])
        self.assertEqual(r.agent_trace[0]["status"], "refused")
        self.assertEqual(self.calls(), [])

    def test_a_tool_that_takes_acknowledged_counts_too(self):
        self.run_agent([{"tool": "kraken_kraken_future_thing", "input": {}}, {"done": True, "answer": "ok"}])
        self.assertEqual(len(self.money_asked), 1)

    def test_nobody_there_means_it_never_runs(self):
        for label, kw in (("no keyboard", {"here": False}), ("GitHub Actions", {"env": {"GITHUB_ACTIONS": "true"}})):
            with self.subTest(label):
                if os.path.exists(self.log):
                    os.remove(self.log)
                r = self.run_agent([{"tool": "kraken_kraken_order_buy", "input": {"pair": "XBTGBP", "volume": "1"}},
                                    {"done": True, "answer": "ok"}], **kw)
                self.assertEqual(self.money_asked, [], "not even asked: there's nobody to answer")
                self.assertEqual(r.agent_trace[0]["status"], "refused")
                self.assertIn("real money", r.agent_trace[0]["result"])
                self.assertEqual(self.calls(), [])

    def test_mcp_kraken_wins_over_the_blocks_command(self):
        self.run_agent([{"tool": "kraken_kraken_ticker", "input": {"pair": "ETHGBP"}}, {"done": True, "answer": "ok"}],
                       env={"MCP_KRAKEN": FAKE}, command="kraken-that-does-not-exist mcp")
        self.assertEqual(self.calls()[-1]["name"], "kraken_ticker")


class Doctor(unittest.TestCase):
    def check(self, env):
        r = Runtime()
        r.reset()
        r.log = lambda *a, **k: None
        r.__dict__["_mcp_defaults"] = {"MCP_KRAKEN": FAKE}
        with mock.patch.dict(os.environ, dict({"FAKE_MCP_LOG": os.devnull}, **env)):
            for k in ("MCP_KRAKEN", "KRAKEN_API_KEY"):
                if k not in env:
                    os.environ.pop(k, None)
            try:
                [(area, run)] = asyncio.run(r._doctor_connections([], ["kraken"]))
                return asyncio.run(run())
            finally:
                for s in r.__dict__.get("_mcp_servers", {}).values():
                    s.close()

    def test_allow_dangerous_fails(self):
        with self.assertRaises(RunError) as e:
            self.check({"MCP_KRAKEN": "kraken mcp -s market,trade --allow-dangerous"})
        self.assertIn("--allow-dangerous", str(e.exception))

    def test_kraken_cli_missing(self):
        with mock.patch("shutil.which", return_value=None), self.assertRaises(RunError) as e:
            self.check({"MCP_KRAKEN": "kraken mcp -s market"})
        self.assertIn("kraken-cli isn't installed", str(e.exception))

    def test_the_key_is_checked_without_showing_what_it_reads(self):
        text = self.check({"KRAKEN_API_KEY": "good"})
        self.assertIn("your Kraken key works", text)
        self.assertNotIn("1200", text)
        with self.assertRaises(RunError) as e:
            self.check({"KRAKEN_API_KEY": "bad"})
        self.assertIn("Invalid key", str(e.exception))
        self.assertNotIn("key works", self.check({}))


if __name__ == "__main__":
    unittest.main()
