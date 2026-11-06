"""Trust Wallet through its Agent Kit's MCP server (#320), against tests/fake_twak.py: balances, prices and risk checks
don't ask; transfers, swaps and payments always ask, even with (no asking), and never run with nobody there; a tool we
don't know counts as money; the agent can't set autoApprove; and automations aren't offered at all."""
import asyncio
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import support
from second_thought import mcp
from second_thought.core import SAFETY
from second_thought.runtime import Runtime

FAKE = f'"{sys.executable}" "{support.ROOT / "tests" / "fake_twak.py"}"'


class Keyboard:
    def __init__(self, here):
        self.here = here

    def isatty(self):
        return self.here


class Rules(unittest.TestCase):
    def test_which_servers_are_trust_wallet(self):
        for server, command in (("trustwallet", ""), ("Trust Wallet", ""), ("twak", ""), ("wallet", "twak serve"),
                                ("wallet", "npx -y @trustwallet/cli serve"), ("wallet", '"C:\\\\npm\\\\twak.cmd" serve --rest')):
            self.assertTrue(mcp.mcp_is_twak(server, command), (server, command))
        for server, command in (("wallet", "python wallet.py"), ("github", "docker run ghcr.io/github/github-mcp-server stdio")):
            self.assertFalse(mcp.mcp_is_twak(server, command), (server, command))

    def test_the_lists(self):
        self.assertTrue(set(SAFETY["mcp_twak_safe"]).isdisjoint(["transfer", "swap", "approve_token", "x402_request", "confirm_offramp_transfer"]))
        self.assertNotIn("create_automation", SAFETY["mcp_twak_safe"])
        self.assertIn("autoApprove", SAFETY["mcp_money_inputs"])


class Agent(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(dir=support.TMP)
        self.log = os.path.join(self.tmp, "mcp.log")

    def calls(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log, encoding="utf-8") as f:
            return [m["params"] for m in map(json.loads, f) if m.get("method") == "tools/call"]

    def run_agent(self, script, ask="never", here=True, answers=()):
        r = Runtime()
        r.reset()
        r.log = lambda *a, **k: None
        replies, self.asked, self.money_asked = iter(script), [], []

        self.prompts = []

        async def fake_call(prompt, want_json=False, *a, **k):
            self.prompt = prompt
            self.prompts.append(prompt)
            return next(replies)

        async def fake_confirm(what):
            self.asked.append(what)
            return True

        async def fake_approve(what):
            self.money_asked.append(what)
            return answers[len(self.money_asked) - 1] if len(self.money_asked) <= len(answers) else True
        r._call, r.confirm, r._approve_live = fake_call, fake_confirm, fake_approve
        if not here:
            r.schedule_mode = True
        tool = {"kind": "mcp", "server": "trustwallet", "ask": ask, "command": FAKE}
        with mock.patch.dict(os.environ, {"FAKE_MCP_LOG": self.log}), mock.patch.object(sys, "stdin", Keyboard(here)):
            for k in ("MCP_TRUSTWALLET", "GITHUB_ACTIONS", "RB_APPROVE_BY"):
                os.environ.pop(k, None)
            asyncio.run(r.agent("Look after my wallet", 6, [tool]))
        for s in r.__dict__.get("_mcp_servers", {}).values():
            s.close()
        return r

    def test_looking_never_asks(self):
        r = self.run_agent([{"tool": "trustwallet_wallet_portfolio", "input": {}},
                            {"tool": "trustwallet_check_token_risk", "input": {"token": "PEPE", "chain": "ethereum"}},
                            {"done": True, "answer": "ok"}])
        self.assertEqual(self.asked + self.money_asked, [])
        self.assertIn("1234.5", r.agent_trace[0]["result"])

    def test_a_transfer_always_asks_and_no_means_no(self):
        r = self.run_agent([{"tool": "trustwallet_transfer", "input": {"chain": "ethereum", "to": "0xabc", "amount": "1"}},
                            {"done": True, "answer": "ok"}], answers=[False])
        self.assertEqual(len(self.money_asked), 1)
        self.assertIn("real money", self.money_asked[0])
        self.assertEqual(r.agent_trace[0]["status"], "refused")
        self.assertEqual(self.calls(), [])

    def test_a_tool_we_dont_know_counts_as_money(self):
        self.run_agent([{"tool": "trustwallet_stake_everything", "input": {}}, {"done": True, "answer": "ok"}])
        self.assertEqual(len(self.money_asked), 1)

    def test_only_a_yes_sets_auto_approve(self):
        self.run_agent([{"tool": "trustwallet_x402_request", "input": {"url": "https://api.example.com/data", "maxPaymentAtomic": "10000", "autoApprove": True}},
                        {"done": True, "answer": "ok"}])
        self.assertNotIn("autoApprove", self.prompt.split("trustwallet_x402_request(")[1].split(")")[0], "the agent isn't offered it")
        self.assertNotIn("autoApprove", self.money_asked[0], "what you're asked about is what the agent wanted, without its own say-so")
        self.assertIs(self.calls()[-1]["arguments"].get("autoApprove"), True, "set by the yes")

    def test_automations_are_not_offered(self):
        r = self.run_agent([{"tool": "trustwallet_create_automation", "input": {"type": "dca"}}, {"done": True, "answer": "ok"}])
        self.assertIn("trustwallet_create_alert", self.prompts[0])
        self.assertNotIn("trustwallet_create_automation", self.prompts[0])
        self.assertNotEqual(r.agent_trace[0]["status"], "done")
        self.assertEqual(self.calls(), [])

    def test_nobody_there_means_a_swap_never_runs(self):
        r = self.run_agent([{"tool": "trustwallet_swap", "input": {"fromToken": "ETH", "toToken": "USDC", "amount": "0.1", "fromChain": "ethereum", "toChain": "ethereum"}},
                            {"done": True, "answer": "ok"}], here=False)
        self.assertEqual(self.money_asked, [], "not even asked: there's nobody to answer")
        self.assertEqual(r.agent_trace[0]["status"], "refused")
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
