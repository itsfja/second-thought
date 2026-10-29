#!/usr/bin/env python3
"""End-to-end tests for Second Thought.

Runs the page in a headless browser with stand-ins for Claude, account storage
and downloads, then exports every example to Python and runs that too, against
a stand-in Anthropic SDK (tests/fakeapi). Nothing calls the real API.

    bash tests/setup.sh          # once
    python tests/run_tests.py    # every time
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # tests/, so tests/e2e is importable
from e2e.common import *  # noqa: E402,F401,F403  (tools/record_demo.py uses route, MOCK, VENDOR and step_texts from here)
from e2e.page import page_tests  # noqa: E402
from e2e.python_export import python_tests  # noqa: E402
from e2e.sources import example_ini_check, package_check  # noqa: E402
from e2e.i18n import i18n_tests  # noqa: E402
from e2e.gallery import gallery_tests  # noqa: E402


def main():
    sync = subprocess.run([sys.executable, str(ROOT / "tools" / "sync.py"), "--check"], capture_output=True, text=True)
    print("Sources")
    check(sync.returncode == 0, sync.stdout.strip())
    package_check()
    unit = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(HERE / "unit")], capture_output=True, text=True, timeout=300)
    ran = re.search(r"Ran (\d+) tests?", unit.stderr)
    check(unit.returncode == 0, f"the unit tests in tests/unit pass ({ran.group(1) if ran else '?'} tests)"
          + ("" if unit.returncode == 0 else ":\n" + unit.stderr.strip()[-1500:]))
    example_ini_check()
    if not (VENDOR / "blockly").exists():
        sys.exit("Run tests/setup.sh first.")
    codes = asyncio.run(page_tests())
    asyncio.run(i18n_tests())
    asyncio.run(gallery_tests())
    python_tests(codes)
    print()
    if failures:
        print(f"{len(failures)} check(s) failed.")
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()
