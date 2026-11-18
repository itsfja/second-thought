"""The You blocks on the approve_by channel when nobody's at the keyboard (#434): ask, wait, who answered.
Telegram is the first channel; the tests stand in for it. Channel answers are never journaled."""
import asyncio
import os
import pathlib
import sys
import tempfile
import unittest

import support  # noqa: F401
from second_thought.runtime import Runtime, _TelegramChannel

ENV_KEYS = ("RB_APPROVE_BY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")


class YouChannel(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.prog = pathlib.Path(self.tmp.name) / "prog.py"
        self.prog.write_text("# prog\n", encoding="utf-8")
        self.saved_argv = sys.argv
        sys.argv = [str(self.prog)]
        self.saved_env = {k: os.environ.get(k) for k in ENV_KEYS}
        for k in ENV_KEYS:
            os.environ.pop(k, None)
        self.rt = Runtime()
        self.rt._nobody_to_type = lambda: True  # a scheduler's run: stdin isn't a terminal
        os.environ["RB_APPROVE_BY"] = "telegram"
        os.environ["TELEGRAM_BOT_TOKEN"] = "t"
        os.environ["TELEGRAM_CHAT_ID"] = "42"
        self.sent = []   # the stand-in Telegram's sendMessage calls
        self.replies = []  # what the stand-in's getUpdates gives back

        async def fake_tg(method, params=None, wait=0):
            self.sent.append((method, params))
            return {"message_id": len(self.sent)}

        async def fake_fetch(wait=0):
            await asyncio.sleep(0)
            return self.replies.pop(0) if self.replies else []

        self.rt._tg = fake_tg
        self.rt.tg_fetch = fake_fetch

    def tearDown(self):
        sys.argv = self.saved_argv
        for k, v in self.saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def go(self, coro):
        return asyncio.run(coro)

    def reply(self, text, chat="42", sender="Alex"):
        self.replies.append([{"text": text, "chat": chat, "sender": sender}])

    def test_ask_me_answered_on_telegram(self):
        self.reply("rye flour")
        out = self.go(self.rt.ask_me("What to bake?", mins=5, default="bread"))
        self.assertEqual(out, "rye flour")
        self.assertEqual(self.rt.answer, "rye flour")
        self.assertEqual(len(self.sent), 1)
        method, params = self.sent[0]
        self.assertEqual(method, "sendMessage")
        self.assertEqual(params["chat_id"], "42")
        self.assertIn("What to bake?", params["text"])

    def test_ask_me_timeout_uses_the_blocks_default(self):
        out = self.go(self.rt.ask_me("What to bake?", mins=0, default="bread"))  # 0.6 s at most
        self.assertEqual(out, "bread")
        self.assertEqual(len(self.sent), 1)

    def test_replies_from_other_chats_are_ignored(self):
        self.replies.append([{"text": "stranger", "chat": "999", "sender": "Eve"}])
        self.reply("mine")
        out = self.go(self.rt.ask_me("q?", mins=5, default="d"))
        self.assertEqual(out, "mine")

    def test_approve_yes_and_no_and_default(self):
        self.reply("y")
        self.assertTrue(self.go(self.rt.approve("send the report?", mins=5, default="n")))
        self.reply("n")
        self.assertFalse(self.go(self.rt.approve("send it?", mins=5, default="y")))
        self.assertFalse(self.go(self.rt.approve("send it?", mins=0, default="n")))  # timeout -> default n
        self.assertTrue(self.go(self.rt.approve("send it?", mins=0, default="y")))   # timeout -> default y

    def test_choose_by_number_words_and_default(self):
        self.reply("2")
        self.assertEqual(self.go(self.rt.choose(["a", "b", "c"], mins=5, default="a")), "b")
        self.reply("C")
        self.assertEqual(self.go(self.rt.choose(["a", "b", "c"], mins=5, default="a")), "c")
        self.assertEqual(self.go(self.rt.choose(["a", "b"], mins=0, default="b")), "b")  # timeout -> default item
        self.assertEqual(self.go(self.rt.choose(["a", "b"], mins=0, default="zzz")), "a")  # not an item -> first

    def test_pause_continues_on_reply_or_timeout(self):
        self.reply("go on")
        self.go(self.rt.pause("check the oven", mins=5))
        self.go(self.rt.pause("check the oven", mins=0))  # timeout just continues
        self.assertEqual(len(self.sent), 2)

    def test_no_channel_means_keyboard_path(self):
        os.environ.pop("RB_APPROVE_BY")
        rt = Runtime()
        rt._nobody_to_type = lambda: True
        self.assertIsNone(self.go(rt._ask_channel("q?")))
        self.assertIsNone(rt._you_channel())

    def test_somebody_at_the_keyboard_means_keyboard_path(self):
        self.rt._nobody_to_type = lambda: False
        self.assertIsNone(self.go(self.rt._ask_channel("q?")))
        self.assertEqual(self.sent, [])

    def test_rehearsal_never_asks_on_the_channel(self):
        self.rt.rehearsing = True
        self.assertIsNone(self.go(self.rt._ask_channel("q?")))
        self.assertEqual(self.sent, [])

    def test_channel_answers_are_never_journaled(self):
        recorded = []
        self.rt._record = lambda *a: recorded.append(a)
        self.reply("rye flour")
        self.go(self.rt.ask_me("What to bake?", mins=5, default="bread"))
        self.assertEqual(recorded, [], "a channel answer must not be replayed from a stopped run's journal")

    def test_channel_interface_has_the_three_jobs(self):
        ch = _TelegramChannel(self.rt)
        self.assertEqual(ch.name, "telegram")
        self.assertTrue(callable(getattr(ch, "ask")))

    def test_missing_chat_raises_the_known_message(self):
        os.environ.pop("TELEGRAM_CHAT_ID")
        with self.assertRaises(Exception) as cm:
            self.go(self.rt.ask_me("q?", mins=5, default="d"))
        self.assertIn("TELEGRAM_CHAT_ID", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
