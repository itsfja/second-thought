"""Settings in three layers (#340): ST_ variables, then second-thought.ini in your home folder, then the program's own,
each over the one before; ordinary environment variables over all three; --doctor says where each key came from."""
import os
import subprocess
import sys
import tempfile
import unittest

import support

SHOW = ("\nimport os\nfrom_ = {k: KEY_SOURCES.get(k) for k in ('ANTHROPIC_API_KEY', 'EMAIL_ADDRESS', 'RB_CURRENCY', 'RB_SAVE_LOG', 'RB_BUDGET')}\n"
        "print('VALUES', [os.environ.get(k) for k in ('ANTHROPIC_API_KEY', 'EMAIL_ADDRESS', 'RB_CURRENCY', 'RB_SAVE_LOG', 'RB_BUDGET')])\n"
        "print('FROM', [from_[k] for k in sorted(from_)])\nprint('PATHS', len(SETTINGS_PATHS), SETTINGS_PATH == SETTINGS_PATHS[-1] if SETTINGS_PATHS else None)\n")


class Layers(unittest.TestCase):
    def run_prog(self, home=None, own=None, env=None):
        runtime = (support.ROOT / "python" / "runtime.py").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            prog = os.path.join(tmp, "prog.py")
            with open(prog, "w", encoding="utf-8") as f:
                f.write(runtime + SHOW)
            if own is not None:
                with open(os.path.join(tmp, "second-thought.ini"), "w", encoding="utf-8") as f:
                    f.write(own)
            home_ini = os.path.join(tmp, "home.ini")
            if home is not None:
                with open(home_ini, "w", encoding="utf-8") as f:
                    f.write(home)
            full = {k: v for k, v in os.environ.items()
                    if not k.startswith(("RB_", "ST_")) and k not in ("ANTHROPIC_API_KEY", "EMAIL_ADDRESS", "SECOND_THOUGHT_INI")}
            full.update(SECOND_THOUGHT_HOME_INI=home_ini, RB_RATES_URL="http://127.0.0.1:9/none", **(env or {}))
            r = subprocess.run([sys.executable, "-I", prog], capture_output=True, text=True, timeout=60, cwd=tmp, env=full)
        out = {line.split(" ", 1)[0]: line.split(" ", 1)[1] for line in r.stdout.splitlines() if line[:5] in ("VALUE", "FROM ", "PATHS")}
        self.assertIn("VALUES", out, r.stderr[-600:])
        return out

    def test_each_layer_over_the_one_before(self):
        out = self.run_prog(
            env={"ST_CURRENCY": "eur", "ST_EMAIL_ADDRESS": "st@example.com", "ST_SAVE_LOG": "no", "ST_ANTHROPIC_API_KEY": "sk-st"},
            home="[keys]\nEMAIL_ADDRESS = home@example.com\n[run]\ncurrency = gbp\nbudget = 1000\n",
            own="[run]\ncurrency = jpy\n")
        self.assertEqual(out["VALUES"], "['sk-st', 'home@example.com', 'jpy', 'no', '1000']")
        # sorted by name: ANTHROPIC_API_KEY, EMAIL_ADDRESS, RB_BUDGET, RB_CURRENCY, RB_SAVE_LOG
        self.assertEqual(out["FROM"], "['st:ST_ANTHROPIC_API_KEY', 'home', 'home', 'file', 'st:ST_SAVE_LOG']")
        self.assertEqual(out["PATHS"], "2 True")

    def test_an_ordinary_environment_variable_wins_over_all_three(self):
        out = self.run_prog(env={"ST_CURRENCY": "eur", "RB_CURRENCY": "cny", "EMAIL_ADDRESS": "env@example.com"},
                            home="[run]\ncurrency = gbp\nEMAIL_ADDRESS = home@example.com\n", own="[run]\ncurrency = jpy\n")
        self.assertIn("'env@example.com', 'cny'", out["VALUES"])

    def test_the_home_file_alone_still_works(self):
        out = self.run_prog(home="[run]\ncurrency = gbp      show costs in…\n")
        self.assertIn("'gbp'", out["VALUES"], "and a note left on its line is dropped (#338)")
        self.assertEqual(out["PATHS"], "1 True")

    def test_an_empty_value_doesnt_hide_a_layer_below(self):
        out = self.run_prog(home="[keys]\nEMAIL_ADDRESS = home@example.com\n", own="[keys]\nEMAIL_ADDRESS = \n")
        self.assertIn("'home@example.com'", out["VALUES"])


if __name__ == "__main__":
    unittest.main()
