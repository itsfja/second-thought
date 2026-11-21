"""Coinbase through its Advanced Trade API (#371), against tests/fake_coinbase.py, which checks every request's signed
token the way Coinbase does. Reading and previewing don't ask; placing and cancelling orders always ask, even with
(no asking), only after a preview, and with nobody there to say yes they don't run at all. --doctor says what the key
may do."""
import asyncio
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import support
from second_thought.core import SAFETY, RunError, coinbase_money
from second_thought.runtime import Runtime

sys.path.insert(0, str(support.ROOT / "tests"))
HAVE_CRYPTO = importlib.util.find_spec("cryptography") is not None
if HAVE_CRYPTO:
    import fake_coinbase  # noqa: E402


class AtKeyboard:
    def isatty(self):
        return True


class Money(unittest.TestCase):
    def test_only_reading_and_previewing_go_without_asking(self):
        for method, path in [("GET", "/api/v3/brokerage/accounts"), ("GET", "/api/v3/brokerage/products/BTC-GBP/candles"),
                             ("get", "/api/v3/brokerage/key_permissions"), ("POST", "/api/v3/brokerage/orders/preview")]:
            self.assertFalse(coinbase_money(method, path), f"{method} {path}")
        for method, path in [("POST", "/api/v3/brokerage/orders"), ("POST", "/api/v3/brokerage/orders/batch_cancel"),
                             ("POST", "/api/v3/brokerage/orders/edit"), ("POST", "/api/v3/brokerage/orders/close_position"),
                             ("POST", "/api/v3/brokerage/convert/quote"), ("POST", "/api/v3/brokerage/convert/trade/abc"),
                             ("POST", "/api/v3/brokerage/portfolios/move_funds"), ("DELETE", "/api/v3/brokerage/portfolios/abc"),
                             ("PUT", "/api/v3/brokerage/portfolios/abc"), ("POST", "/api/v3/brokerage/orders/preview/x"),
                             ("GET", "/api/v3/brokerage/products?x=1"), ("GET", "/v2/accounts")]:
            self.assertTrue(coinbase_money(method, path), f"{method} {path}")
        self.assertEqual({m for m, _ in SAFETY["coinbase_free"]}, {"GET", "POST"})

    def test_a_money_call_without_a_yes_never_leaves(self):
        r = Runtime()
        with mock.patch.object(r, "_coinbase_token", side_effect=AssertionError("signed")):
            for path in ("/api/v3/brokerage/orders", "/api/v3/brokerage/orders/batch_cancel", "/api/v3/brokerage/convert/quote"):
                with self.assertRaises(RunError):
                    asyncio.run(r._coinbase("POST", path, body={}))

    def test_trading_pairs_are_checked_before_they_go_in_an_address(self):
        self.assertEqual(Runtime._coinbase_product_id(" btc/gbp "), "BTC-GBP")
        for bad in ("../accounts", "BTC", "BTC-GBP/candles", "BTC-GBP?x=1", ""):
            with self.assertRaises(RunError, msg=bad):
                Runtime._coinbase_product_id(bad)


class Key(unittest.TestCase):
    def run_key(self, env):
        r = Runtime()
        with mock.patch.dict(os.environ, env, clear=False):
            for k in ("COINBASE_KEY", "COINBASE_KEY_FILE"):
                if k not in env:
                    os.environ.pop(k, None)
            return r._coinbase_key()

    def test_no_key_says_how_to_make_one(self):
        with self.assertRaises(RunError) as e:
            self.run_key({})
        self.assertIn("COINBASE_KEY_FILE", str(e.exception))
        self.assertIn("View only", str(e.exception))

    def test_the_key_file_or_its_contents(self):
        with tempfile.TemporaryDirectory(dir=support.TMP) as tmp:
            path = os.path.join(tmp, "cdp_api_key.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"name": "organizations/o/apiKeys/k", "privateKey": "-----BEGIN EC PRIVATE KEY-----\nabc\n-----END EC PRIVATE KEY-----\n"}, f)
            self.assertEqual(self.run_key({"COINBASE_KEY_FILE": path})[0], "organizations/o/apiKeys/k")
            with open(path, encoding="utf-8") as f:
                self.assertEqual(self.run_key({"COINBASE_KEY": f.read()})[1].splitlines()[1], "abc")
            with self.assertRaises(RunError):
                self.run_key({"COINBASE_KEY_FILE": os.path.join(tmp, "missing.json")})
        with self.assertRaises(RunError):
            self.run_key({"COINBASE_KEY": "not json"})

    @unittest.skipUnless(HAVE_CRYPTO, "needs the cryptography package")
    def test_an_ed25519_key_is_explained(self):
        with mock.patch.dict(os.environ, {"COINBASE_KEY": json.dumps({"id": "abc", "privateKey": "bm90IGEga2V5"})}):
            with self.assertRaises(RunError) as e:
                Runtime()._coinbase_token("GET", "api.coinbase.com/api/v3/brokerage/accounts")
        self.assertIn("ECDSA", str(e.exception))


@unittest.skipUnless(HAVE_CRYPTO, "needs the cryptography package")
class Account(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(dir=support.TMP)
        self.key = fake_coinbase.make_key(os.path.join(self.tmp, "cdp_api_key.json"))

    def runtime(self, can_trade=True, can_transfer=False, here=True, env=None, answers=()):
        self.fake = fake_coinbase.FakeCoinbase(self.key, can_trade=can_trade, can_transfer=can_transfer)
        url = self.fake.start()
        self.addCleanup(self.fake.stop)
        r = Runtime()
        r.reset()
        self.logged, self.money_asked, self.asked = [], [], []
        r.log = lambda *a, **k: self.logged.append(a)

        async def approve(what):
            self.money_asked.append(what)
            return answers[len(self.money_asked) - 1] if len(self.money_asked) <= len(answers) else True

        async def confirm(what):
            self.asked.append(what)
            return True
        r._approve_live, r.confirm = approve, confirm
        r.ask_first = {"ha", "messages", "files"}  # asking everything else first changes nothing for money: it always asks
        patches = [mock.patch.dict(os.environ, dict({"COINBASE_KEY_FILE": self.key, "COINBASE_API_URL": url, "RB_CURRENCY": "gbp"}, **(env or {}))),
                   mock.patch.object(sys, "stdin", AtKeyboard() if here else sys.stdin)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        os.environ.pop("COINBASE_KEY", None)
        if "GITHUB_ACTIONS" not in (env or {}):
            os.environ.pop("GITHUB_ACTIONS", None)
        return r

    def test_reading_signs_every_request_and_never_asks(self):
        r = self.runtime()
        bal = asyncio.run(r.coinbase_balances())
        self.assertEqual([b["asset"] for b in bal], ["BTC", "ETH", "SOL", "GBP"])
        self.assertEqual(bal[0], {"asset": "BTC", "amount": 0.0425, "value": 2612.4, "currency": "GBP"})
        self.assertEqual(asyncio.run(r.coinbase_value()), 5802.61)
        self.assertEqual(asyncio.run(r.coinbase_price("price", "btc-gbp")), 61468.24)
        self.assertEqual(asyncio.run(r.coinbase_price("change", "ETH-GBP")), 1.84)
        days = asyncio.run(r.coinbase_candles("day", "BTC-GBP", 7))
        self.assertEqual(len(days), 7)
        self.assertEqual(days[-1]["close"], 61468.24, "oldest first, ending today")
        self.assertLess(days[0]["time"], days[-1]["time"])
        self.assertEqual(len(asyncio.run(r.coinbase_candles("hour", "ETH-GBP", 400))), 48, "as many as there are, up to 350")
        orders = asyncio.run(r.coinbase_orders("open"))
        self.assertEqual(orders[0], {"id": "8f2c1a7e-0b4d-4c55-9a51-3e6d2b9f7a10", "product": "BTC-GBP", "side": "buy", "size": 0.01,
                                     "price": 55000, "filled": 0, "created": "2026-11-02 09:14:00"})
        self.assertEqual(asyncio.run(r.coinbase_orders("fills"))[0]["fee"], 1.71)
        pre = asyncio.run(r.coinbase_preview("buy", 50, "BTC-GBP"))
        self.assertEqual((pre["spend"], pre["fee"], pre["total"]), (50, 0.3, 50))
        self.assertEqual(self.money_asked + self.asked, [])
        self.assertEqual(self.fake.refused, [])
        self.assertEqual(len(self.fake.nonces), len(self.fake.calls), "a new token for every request")
        self.assertNotIn("POST /api/v3/brokerage/orders", self.fake.calls)

    def test_a_token_that_doesnt_match_is_refused(self):
        r = self.runtime()
        other = fake_coinbase.make_key(os.path.join(self.tmp, "other.json"))
        with mock.patch.dict(os.environ, {"COINBASE_KEY_FILE": other}):
            with self.assertRaises(RunError) as e:
                asyncio.run(r.coinbase_value())
        self.assertIn("refused the key", str(e.exception))
        self.assertEqual(self.fake.refused, ["signature doesn't verify"])

    def test_derivatives_and_unknown_pairs_are_refused(self):
        r = self.runtime()
        with self.assertRaises(RunError) as e:
            asyncio.run(r.coinbase_price("price", "BIT-28NOV26-CDE"))
        with self.assertRaises(RunError) as e:
            asyncio.run(r.coinbase_preview("buy", 50, "BIT-28NOV26"))
        self.assertIn("not found", str(e.exception))

    def test_an_order_is_previewed_then_asked_about_then_placed(self):
        r = self.runtime()
        oid = asyncio.run(r.coinbase_order("buy", 50, "BTC-GBP"))
        self.assertEqual(oid, "order-1")
        self.assertEqual(len(self.money_asked), 1)
        self.assertIn("real money", self.money_asked[0])
        self.assertIn("fee 0.3 GBP, total 50 GBP", self.money_asked[0])
        posts = [c for c in self.fake.calls if c.startswith("POST")]
        self.assertEqual(posts, ["POST /api/v3/brokerage/orders/preview", "POST /api/v3/brokerage/orders"])
        placed = self.fake.placed[0]
        self.assertEqual((placed["side"], placed["order_configuration"]), ("BUY", {"market_market_ioc": {"quote_size": "50"}}))
        self.assertEqual(placed["preview_id"], "preview-1")
        self.assertEqual(self.asked, [], "it's the money question, not the everyday one")

    def test_sell_sizes_in_the_first_currency(self):
        r = self.runtime()
        asyncio.run(r.coinbase_order("sell", 0.01, "BTC-GBP"))
        self.assertEqual(self.fake.placed[0]["order_configuration"], {"market_market_ioc": {"base_size": "0.01"}})
        self.assertIn("sell 0.01 BTC for 614.68 GBP", self.money_asked[0])

    def test_no_means_nothing_is_placed(self):
        r = self.runtime(answers=[False, False])
        self.assertEqual(asyncio.run(r.coinbase_order("buy", 50, "BTC-GBP")), "")
        self.assertFalse(asyncio.run(r.coinbase_cancel("8f2c1a7e-0b4d-4c55-9a51-3e6d2b9f7a10")))
        self.assertEqual((self.fake.placed, self.fake.cancelled), ([], []))

    def test_a_preview_problem_stops_it_before_asking(self):
        r = self.runtime()
        with self.assertRaises(RunError) as e:
            asyncio.run(r.coinbase_order("buy", 5000, "BTC-GBP"))
        self.assertIn("insufficient fund", str(e.exception))
        self.assertEqual((self.money_asked, self.fake.placed), ([], []))
        for bad in (("hold", 5), ("buy", 0), ("buy", "lots")):
            with self.assertRaises(RunError, msg=str(bad)):
                asyncio.run(r.coinbase_preview(bad[0], bad[1], "BTC-GBP"))

    def test_cancelling_asks_too(self):
        r = self.runtime()
        self.assertTrue(asyncio.run(r.coinbase_cancel("8f2c1a7e-0b4d-4c55-9a51-3e6d2b9f7a10")))
        self.assertEqual(self.fake.cancelled, ["8f2c1a7e-0b4d-4c55-9a51-3e6d2b9f7a10"])
        self.assertIn("cancel the Coinbase order", self.money_asked[0])
        with self.assertRaises(RunError) as e:
            asyncio.run(r.coinbase_cancel("no-such-order"))
        self.assertIn("unknown cancel order", str(e.exception))
        with self.assertRaises(RunError):
            asyncio.run(r.coinbase_cancel("x/../y"))

    def test_nobody_there_means_it_never_runs(self):
        for label, kw in (("no keyboard", {"here": False}), ("GitHub Actions", {"env": {"GITHUB_ACTIONS": "true"}})):
            with self.subTest(label):
                r = self.runtime(**kw)
                self.assertEqual(asyncio.run(r.coinbase_order("buy", 50, "BTC-GBP")), "")
                self.assertFalse(asyncio.run(r.coinbase_cancel("8f2c1a7e-0b4d-4c55-9a51-3e6d2b9f7a10")))
                self.assertEqual((self.money_asked, self.fake.placed, self.fake.cancelled), ([], [], []))
                self.assertTrue(any("real money" in str(a) for a in self.logged))

    def test_a_test_run_places_nothing(self):
        r = self.runtime()
        r.testing = True
        self.assertEqual(asyncio.run(r.coinbase_order("buy", 50, "BTC-GBP")), "")
        self.assertEqual((self.money_asked, self.fake.placed), ([], []))

    def test_a_view_only_key_is_refused_by_coinbase_after_a_yes(self):
        r = self.runtime(can_trade=False)
        with self.assertRaises(RunError) as e:
            asyncio.run(r.coinbase_order("buy", 50, "BTC-GBP"))
        self.assertIn("isn't allowed", str(e.exception))

    def doctor(self, can, **kw):
        r = self.runtime(**kw)
        [(area, run)] = [c for c in asyncio.run(r._doctor_connections(can, [])) if c[0] == "Coinbase"]
        try:
            got = asyncio.run(run())
        except RunError as e:
            return "FAIL", str(e)
        return got if isinstance(got, tuple) else ("ok", got)

    def test_doctor_says_what_the_key_may_do(self):
        self.assertEqual(self.doctor(["coinbase_read"], can_trade=False), ("ok", "the key works, View only"))
        self.assertEqual(self.doctor(["coinbase_read"], can_trade=True)[0], "NOTE")
        self.assertIn("View-only key is safer", self.doctor(["coinbase_read"], can_trade=True)[1])
        self.assertEqual(self.doctor(["coinbase_read", "coinbase_trade"], can_trade=True)[0], "ok")
        status, text = self.doctor(["coinbase_trade"], can_trade=False)
        self.assertEqual(status, "FAIL")
        self.assertIn("View only", text)
        self.assertIn("Transfer", self.doctor(["coinbase_read"], can_trade=False, can_transfer=True)[1])
        self.assertEqual([c for c in self.fake.calls if not c.startswith("GET")], [], "the doctor only reads")


if __name__ == "__main__":
    unittest.main()
