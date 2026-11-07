"""Costs and money budgets in pounds, euros, yen or yuan (#263): the formatting, where the rate comes from (the ECB's
daily file, kept for a day; the last one kept; the built-in RATES; or exchange_rate), and budgets in other currencies."""
import asyncio
import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest

import support
from second_thought import providers
from second_thought.core import RunError
from second_thought.providers import RATES, amount_text, money
from second_thought.runtime import Runtime

ECB_XML = """<?xml version="1.0" encoding="UTF-8"?>
<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01" xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">
 <Cube><Cube time='2026-11-02'>
  <Cube currency='USD' rate='1.1000'/><Cube currency='JPY' rate='170.00'/><Cube currency='GBP' rate='0.8800'/>
  <Cube currency='CNY' rate='7.7000'/></Cube></Cube></gesmes:Envelope>"""


class InCurrency:
    """Sets the program's currency (and clears the rates it's using) for one test."""

    def __init__(self, cur, **env):
        self.cur, self.env = cur, env

    def __enter__(self):
        self.saved = providers.CURRENCY, {k: os.environ.get(k) for k in self.env}
        providers.CURRENCY = self.cur
        os.environ.update(self.env)
        providers._RATES.clear()

    def __exit__(self, *a):
        providers.CURRENCY = self.saved[0]
        for k, v in self.saved[1].items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        providers._RATES.clear()


class Formatting(unittest.TestCase):
    def test_each_currency(self):
        self.assertEqual(amount_text(0.5, "usd"), "$0.50")
        self.assertEqual(amount_text(12, "gbp"), "£12.00")
        self.assertEqual(amount_text(1234.5, "eur"), "€1,234.50")
        self.assertEqual(amount_text(75, "jpy"), "¥75", "yen has no decimals")
        self.assertEqual(amount_text(0.4, "cny"), "0.40 CNY", "yuan shows its code, so it isn't taken for yen")

    def test_under_the_smallest_coin_shows_its_digits(self):
        self.assertEqual(amount_text(0.0004, "usd"), "$0.0004")
        self.assertEqual(amount_text(0.3, "jpy"), "¥0.3")

    def test_approximate_costs_round(self):
        with InCurrency("jpy", RB_RATES_URL="http://127.0.0.1:9/none"):
            self.assertEqual(money(0.0002), "under ¥1")
            self.assertTrue(money(0.03).startswith("about ¥") and "." not in money(0.03), money(0.03))
        with InCurrency("gbp", RB_EXCHANGE_RATE="0.8"):
            self.assertEqual(money(0.0054), "under £0.01", "0.0054 dollars is 0.0043 pounds")
            self.assertEqual(money(1.25), "about £1.00")


class Rates(unittest.TestCase):
    def setUp(self):
        self.hits = 0
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                outer.hits += 1
                self.send_response(200)
                self.end_headers()
                self.wfile.write(ECB_XML.encode())

            def log_message(self, *a):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}/eurofxref-daily.xml"
        self.tmp = tempfile.TemporaryDirectory()
        self.saved_file = providers._rates_file
        providers._rates_file = lambda: os.path.join(self.tmp.name, ".second-thought-rates.json")

    def tearDown(self):
        providers._rates_file = self.saved_file
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def test_fetched_from_the_ecb_and_kept_for_the_day(self):
        with InCurrency("gbp", RB_RATES_URL=self.url):
            self.assertAlmostEqual(providers.per_dollar("gbp"), 0.88 / 1.1)
            self.assertAlmostEqual(providers.per_dollar("eur"), 1 / 1.1)
            self.assertEqual(providers.rate_note(), "at the ECB rate of 2026-11-02")
        with InCurrency("gbp", RB_RATES_URL=self.url):
            providers.per_dollar("gbp")
        self.assertEqual(self.hits, 1, "a second program run the same day uses the kept rates")

    def test_offline_uses_the_last_kept_then_the_built_in(self):
        with InCurrency("eur", RB_RATES_URL="http://127.0.0.1:9/none"):
            self.assertEqual(providers.rates()["how"], "built-in")
            self.assertEqual(providers.rates()["date"], RATES["date"])
            self.assertTrue(providers.rates()["problem"])
        with open(providers._rates_file(), "w", encoding="utf-8") as f:
            json.dump({"per_euro": {"usd": 1.2, "gbp": 0.9, "jpy": 160, "cny": 8}, "date": "2026-10-01", "fetched": time.time() - 86400 * 3}, f)
        with InCurrency("eur", RB_RATES_URL="http://127.0.0.1:9/none"):
            self.assertEqual(providers.rates()["date"], "2026-10-01", "an older kept rate beats the built-in one")

    def test_a_fixed_rate_wins_for_the_programs_currency_only(self):
        with InCurrency("gbp", RB_EXCHANGE_RATE="0.5", RB_RATES_URL=self.url):
            self.assertEqual(providers.per_dollar("gbp"), 0.5)
            self.assertAlmostEqual(providers.per_dollar("jpy"), 170 / 1.1, msg="another currency still uses the ECB's")
            self.assertIn("rate set", providers.rate_note())

    def test_built_in_rates_are_dated_and_complete(self):
        self.assertTrue(set(providers.CURRENCIES) - {"eur"} <= set(RATES["per_euro"]))
        self.assertRegex(RATES["date"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertTrue(RATES["source"].startswith("https://www.ecb.europa.eu/"))


class Budgets(unittest.TestCase):
    def runtime(self):
        rt = Runtime()
        rt.reset()
        rt.log = lambda *a, **k: None
        rt.tier = rt.primary = "default"
        rt.backups = []

        async def call_tier(t, *a, **k):
            rt._count("Claude", 100_000, 10_000)  # $0.30 at Sonnet's list price
            return "ok"
        rt._call_tier = call_tier
        return rt

    def test_a_budget_in_pounds(self):
        with InCurrency("gbp", RB_EXCHANGE_RATE="0.8"):
            rt = self.runtime()
            rt.set_budget(0.40, "gbp")  # $0.50
            self.assertAlmostEqual(rt.budget_dollars, 0.5)
            asyncio.run(rt._call_live("a"))
            asyncio.run(rt._call_live("b"))
            with self.assertRaises(RunError) as e:
                asyncio.run(rt._call_live("c"))
            self.assertIn("budget of £0.40", str(e.exception))
            self.assertIn("about £0.48", str(e.exception), "what was spent, in the budget's currency")

    def test_yen_budget_shows_whole_yen(self):
        with InCurrency("usd", RB_RATES_URL="http://127.0.0.1:9/none"):
            rt = self.runtime()
            rt.set_budget(75, "jpy")
            self.assertEqual(rt.budget_text(), "¥75")
            self.assertGreater(rt.budget_dollars, 0, "always has a rate, so never no limit")


class AsAnExportedProgram(unittest.TestCase):
    """python/runtime.py, joined from the package in a different order from the package's imports, run as a program
    with each currency (#274): a module using a name from one joined after it fails only here."""

    def run_with(self, **env):
        runtime = (support.ROOT / "python" / "runtime.py").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            prog = os.path.join(tmp, "prog.py")
            with open(prog, "w", encoding="utf-8") as f:
                f.write(runtime + "\nR = Runtime()\nprint(money(1.0))\nR.main([], {}, [])\n")
            full = {k: v for k, v in os.environ.items() if not k.startswith("RB_")}
            full.update(SECOND_THOUGHT_INI=os.path.join(tmp, "none.ini"), RB_RATES_URL="http://127.0.0.1:9/none", **env)
            return subprocess.run([sys.executable, "-I", prog], capture_output=True, text=True, timeout=60, cwd=tmp, env=full)

    def test_each_currency_starts(self):
        for cur, sign in (("usd", "$"), ("gbp", "£"), ("eur", "€"), ("jpy", "¥"), ("cny", "CNY")):
            with self.subTest(currency=cur):
                r = self.run_with(RB_CURRENCY=cur)
                self.assertIn("Nothing to run", r.stdout + r.stderr, r.stderr[-400:])
                self.assertIn(sign, r.stdout)

    def test_with_a_fixed_rate(self):
        r = self.run_with(RB_CURRENCY="gbp", RB_EXCHANGE_RATE="0.8")
        self.assertIn("about £0.80", r.stdout, r.stderr[-400:])

    def test_a_mistyped_rate_stops_it_saying_which_setting(self):
        r = self.run_with(RB_CURRENCY="gbp", RB_EXCHANGE_RATE="lots")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("exchange_rate", r.stderr)
        self.assertNotIn("NameError", r.stderr)


class Settings(unittest.TestCase):
    def test_an_older_exports_note_left_on_the_line_is_ignored(self):
        # #338: before 3.10.1 the export wrote "; currency = gbp      show costs…", and people took the ; off
        runtime = (support.ROOT / "python" / "runtime.py").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            prog, ini = os.path.join(tmp, "prog.py"), os.path.join(tmp, "second-thought.ini")
            with open(prog, "w", encoding="utf-8") as f:
                f.write(runtime + "\nimport os\nprint(repr(os.environ.get('RB_CURRENCY')), repr(os.environ.get('RB_SAVE_LOG')), "
                                  "repr(os.environ.get('RB_BUDGET')), repr(os.environ.get('RB_BACKUPS')), repr(os.environ.get('EMAIL_PASSWORD')))\n")
            with open(ini, "w", encoding="utf-8") as f:
                f.write("[run]\ncurrency = gbp      show costs and money budgets in usd, gbp, eur, jpy or cny (the ECB's rate)\n"
                        "save_log = yes      write each run's log to the logs folder\nbudget = 50000      stop a run before a model call\n"
                        "[models]\nbackups = claude-quick, gemini-flash\n[keys]\nEMAIL_PASSWORD = abcd efgh  ijkl mnop\n")
            env = {k: v for k, v in os.environ.items() if not k.startswith("RB_") and k != "EMAIL_PASSWORD"}
            env.update(SECOND_THOUGHT_INI=ini, RB_RATES_URL="http://127.0.0.1:9/none")
            r = subprocess.run([sys.executable, "-I", prog], capture_output=True, text=True, timeout=60, cwd=tmp, env=env)
        self.assertIn("'gbp' 'yes' '50000' 'claude-quick, gemini-flash' 'abcd efgh  ijkl mnop'", r.stdout, r.stderr[-400:])

    def test_a_mistyped_currency_stops_the_program_saying_so(self):
        runtime = (support.ROOT / "python" / "runtime.py").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            prog = os.path.join(tmp, "prog.py")
            with open(prog, "w", encoding="utf-8") as f:
                f.write(runtime + "\nR = Runtime()\nR.main([], {}, [])\n")
            env = dict(os.environ, RB_CURRENCY="pounds", SECOND_THOUGHT_INI=os.path.join(tmp, "none.ini"))
            r = subprocess.run([sys.executable, "-I", prog, "--version"], capture_output=True, text=True, timeout=60, cwd=tmp, env=env)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("currency must be usd, gbp, eur, jpy or cny", r.stderr)


if __name__ == "__main__":
    unittest.main()
