"""GitHub through its own MCP server (#333), against tests/fake_github_mcp.py: reading a repository never asks; a
change asks unless the block says (no asking); merging, pushing and deleting always ask, and with nobody there to say
yes they don't run at all. Started as the recipe says, with --read-only, the server offers only reading tools."""
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

FAKE = f'"{sys.executable}" "{support.ROOT / "tests" / "fake_github_mcp.py"}"'


class AtKeyboard:
    def isatty(self):
        return True


class NoKeyboard:
    def isatty(self):
        return False


class Rules(unittest.TestCase):
    def test_merge_push_and_delete_always_ask(self):
        for name in ("merge_pull_request", "push_files", "create_or_update_file", "delete_repository"):
            self.assertIn(name, SAFETY["mcp_always_ask"])
            self.assertTrue(mcp.mcp_destructive({"name": name, "annotations": {"readOnlyHint": False}}), name)
        self.assertFalse(mcp.mcp_destructive({"name": "create_issue", "annotations": {"readOnlyHint": False}}))
        self.assertFalse(mcp.mcp_destructive({"name": "merge_pull_request", "annotations": {"readOnlyHint": True}}), "read-only wins")
        self.assertFalse(mcp.mcp_money({"name": "merge_pull_request"}), "asking, not money")


class Agent(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(dir=support.TMP)
        self.log = os.path.join(self.tmp, "mcp.log")

    def calls(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log, encoding="utf-8") as f:
            return [m["params"]["name"] for m in map(json.loads, f) if m.get("method") == "tools/call"]

    def run_agent(self, script, ask="never", here=True, env=None):
        r = Runtime()
        r.reset()
        r.log = lambda *a, **k: None
        replies, self.asked = iter(script), []

        async def fake_call(prompt, want_json=False, *a, **k):
            self.prompt = prompt
            return next(replies)

        async def fake_confirm(what):
            self.asked.append(what)
            return True
        r._call = fake_call
        if here:
            r.confirm = fake_confirm
        else:  # a scheduled run with no keyboard: the real question runs, and finds nobody to ask
            r.schedule_mode = True
        tool = {"kind": "mcp", "server": "github", "ask": ask, "command": FAKE}
        with mock.patch.dict(os.environ, dict({"FAKE_MCP_LOG": self.log}, **(env or {}))), \
                mock.patch.object(sys, "stdin", AtKeyboard() if here else NoKeyboard()):
            os.environ.pop("MCP_GITHUB", None)
            os.environ.pop("GITHUB_ACTIONS", None)
            asyncio.run(r.agent("Look at itsfja/rye-planner", 6, [tool]))
        for s in r.__dict__.get("_mcp_servers", {}).values():
            s.close()
        return r

    def test_reading_a_repository_never_asks(self):
        r = self.run_agent([{"tool": "github_get_repository_tree", "input": {"owner": "itsfja", "repo": "rye-planner"}},
                            {"tool": "github_get_file_contents", "input": {"owner": "itsfja", "repo": "rye-planner", "path": "README.md"}},
                            {"done": True, "answer": "It plans rye bakes (README.md)."}], ask="changes")
        self.assertEqual(self.asked, [])
        self.assertEqual(self.calls(), ["get_repository_tree", "get_file_contents"])
        self.assertIn("Rye Planner", r.agent_trace[1]["result"])

    def test_merge_and_delete_ask_even_with_no_asking(self):
        self.run_agent([{"tool": "github_create_issue", "input": {"owner": "itsfja", "repo": "rye-planner", "title": "Two ovens"}},
                        {"tool": "github_merge_pull_request", "input": {"owner": "itsfja", "repo": "rye-planner", "pullNumber": 4}},
                        {"tool": "github_delete_file", "input": {"owner": "itsfja", "repo": "rye-planner", "path": "plan.py"}},
                        {"done": True, "answer": "ok"}])
        self.assertEqual(len(self.asked), 2, self.asked)
        self.assertIn("merge_pull_request", self.asked[0])
        self.assertIn("delete_file", self.asked[1])

    def test_nobody_there_means_merge_never_runs(self):
        r = self.run_agent([{"tool": "github_merge_pull_request", "input": {"owner": "itsfja", "repo": "rye-planner", "pullNumber": 4}},
                            {"done": True, "answer": "ok"}], here=False)
        self.assertEqual(r.agent_trace[0]["status"], "refused")
        self.assertEqual(self.calls(), [])

    def test_read_only_server_offers_only_reading(self):
        self.run_agent([{"done": True, "answer": "ok"}], env={"FAKE_GITHUB_READ_ONLY": "1"})
        offered = self.prompt
        self.assertIn("github_get_file_contents", offered)
        for name in ("create_issue", "merge_pull_request", "delete_file"):
            self.assertNotIn("github_" + name, offered)


if __name__ == "__main__":
    unittest.main()
