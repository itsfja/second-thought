"""'say where each fact came from' on the agent block (#312)."""
import asyncio
import unittest

import support  # noqa: F401
from second_thought.agent import AgentTools
from second_thought.runtime import Runtime


class Sources(unittest.TestCase):
    def test_the_rule_only_with_the_box_and_a_web_tool(self):
        web = {"read_page": ("Read a page.", ["url"], None, None, {})}
        other = {"calculate": ("Sums.", ["expression"], None, None, {})}
        self.assertIn(AgentTools.SOURCES_RULE, AgentTools.agent_prompt("g", web, [], 3, None, True))
        self.assertNotIn(AgentTools.SOURCES_RULE, AgentTools.agent_prompt("g", web, [], 3, None, False))
        self.assertNotIn(AgentTools.SOURCES_RULE, AgentTools.agent_prompt("g", other, [], 3, None, True))

    def run_agent(self, answer, sources=True):
        r = Runtime()
        r.reset()
        logged = []
        r.log = lambda name, text="", pill="", **k: logged.append((name, text))
        self.prompts = []

        async def fake_call(prompt, want_json=False, *a, **k):
            self.prompts.append(prompt)
            return {"done": True, "answer": answer}
        r._call = fake_call
        asyncio.run(r.agent("Use https://example.com/rye", 3, [{"kind": "web"}], sources=sources))
        return [t for n, t in logged if n == "Sources not read"]

    def test_an_address_it_never_read_is_flagged(self):
        note = self.run_agent("Long proof (https://example.com/rye). Sources: https://example.com/rye, https://made-up.example.org/bread")
        self.assertEqual(len(note), 1)
        self.assertIn("https://made-up.example.org/bread", note[0])
        self.assertNotIn("example.com/rye", note[0])

    def test_nothing_flagged_when_every_source_was_seen_or_the_box_is_off(self):
        self.assertEqual(self.run_agent("Long proof (https://example.com/rye/)."), [])
        self.assertEqual(self.run_agent("From https://made-up.example.org/x", sources=False), [])


if __name__ == "__main__":
    unittest.main()
