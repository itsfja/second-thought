#!/usr/bin/env python3
"""End-to-end tests for Second Thought.

Runs the page in a headless browser with stand-ins for Claude, account storage
and downloads, then exports every example to Python and runs that too, against
a stand-in Anthropic SDK (tests/fakeapi). Nothing calls the real API.

    bash tests/setup.sh          # once
    python tests/run_tests.py    # every time

The tests live in tests/e2e/, one file per area. To run only some areas, name them:

    python tests/run_tests.py i18n gallery

The areas are sources, page, i18n, gallery and python. Python runs the programs the page exports, so naming
python runs page too. CI runs python in three shares side by side (#342), each about as long as the others: the
checks that aren't per-program are spread over them, and the exported programs fill them up (#372).

    python tests/run_tests.py python --share 2/3    # one share

--parallel runs CI's five parts here as separate processes, a few at a time (as many as the CPUs, plus one, up to
four; --parallel 2 for two): page first, with sources, i18n and gallery beside it, then the Python shares with what
page exported, so they don't repeat its run. About 10 minutes on two CPUs, against 25 in one process. Every run ends
with how long its pieces took (#372).
"""
import pathlib
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # tests/, so tests/e2e is importable
from e2e.common import *  # noqa: E402,F401,F403  (tools/record_demo.py uses route, MOCK, VENDOR and step_texts from here)
from e2e.page import page_tests  # noqa: E402
from e2e.python_export import PROGRAM_TIMES, group_share, python_tests  # noqa: E402
from e2e.sources import docs_check, example_ini_check, links_check, package_check, sri_check  # noqa: E402
from e2e.i18n import i18n_tests  # noqa: E402
from e2e.gallery import gallery_smoke_tests, gallery_tests  # noqa: E402
from e2e.actions import actions_tests  # noqa: E402
from e2e.pages import pages_tests  # noqa: E402
from e2e.offline import offline_tests  # noqa: E402
from e2e.describe import describe_tests  # noqa: E402
from e2e.formats import format_tests  # noqa: E402
from e2e.program_tests import program_test_tests  # noqa: E402
from e2e.safety import safety_tests  # noqa: E402
from e2e.access import access_tests  # noqa: E402


def editor_unit_tests():
    """The editor's own functions, run in Node without a browser (tests/editor/)."""
    node = shutil.which("node")
    if not node:
        print("  (Node isn't installed, so the editor's unit tests in tests/editor were skipped)")
        return
    files = sorted(str(p) for p in (HERE / "editor").glob("*.test.cjs"))
    out = subprocess.run([node, "--test", *files], capture_output=True, text=True, timeout=300)
    passed = re.search(r"^# pass (\d+)", out.stdout, re.M)
    check(out.returncode == 0, f"the editor's unit tests in tests/editor pass ({passed.group(1) if passed else '?'} tests)"
          + ("" if out.returncode == 0 else ":\n" + (out.stdout + out.stderr).strip()[-2500:]))


AREAS = ("sources", "page", "i18n", "gallery", "python")
# What CI runs side by side (#342), and what --parallel runs here: page first, since the Python shares take what it
# exported (#372).
PARTS = (["page"], ["python", "--share", "1/3"], ["python", "--share", "2/3"], ["python", "--share", "3/3"], ["sources", "i18n", "gallery"])
# The page run's exports, so the Python shares of a --parallel run skip doing it again: the examples' Python and the
# extra programs and replies the page checks make (#372).
SHARED = ("EXAMPLES", "EXPORTS", "EXTRA", "AGENT_SCRIPTS", "EXAMPLE_A_TOOL")


def save_exports(codes, path):
    import e2e.common as common
    data = {"codes": codes, **{name: getattr(common, name) for name in SHARED}}
    pathlib.Path(path).write_text(json.dumps(data), encoding="utf-8")


def load_exports(path):
    import e2e.common as common
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    for name in SHARED:
        held = getattr(common, name)
        held.clear()
        (held.extend if isinstance(held, list) else held.update)(data[name])
    return {ex: tuple(v) for ex, v in data["codes"].items()}


def parallel(areas, workers):
    """Runs CI's parts as separate processes, a few at a time: the page part first (with sources, i18n and gallery
    beside it), then the Python shares with what it exported. Each part's output is printed when it ends."""
    import concurrent.futures
    parts = [p for p in PARTS if set(p) & areas]
    if "python" in areas and ["page"] not in parts:
        parts.insert(0, ["page"])  # the Python shares need what it exports
    began = time.monotonic()
    with tempfile.TemporaryDirectory() as tmp:
        exports = str(pathlib.Path(tmp) / "exports.json")
        env = dict(os.environ, RB_TEST_EXPORTS=exports)
        results = []

        def run(part):
            t = time.monotonic()
            out = subprocess.run([sys.executable, "-u", __file__, *part], env=env, capture_output=True, text=True,
                                 encoding="utf-8", errors="replace")
            return part, out.returncode, out.stdout + out.stderr, time.monotonic() - t

        def report(result):
            part, code, output, secs = result
            print(f"\n===== {' '.join(part)} ({secs:.0f}s, {'passed' if code == 0 else 'FAILED'}) =====")
            print(output.rstrip())
            results.append(result)

        first = [p for p in parts if p[0] != "python"]
        later = [p for p in parts if p[0] == "python"]
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            running = {pool.submit(run, p): p for p in first}
            page_done = "python" not in areas
            while running:
                done, _ = concurrent.futures.wait(running, return_when=concurrent.futures.FIRST_COMPLETED)
                for fut in done:
                    part = running.pop(fut)
                    report(fut.result())
                    if part == ["page"]:
                        page_done = True
                if page_done and later:
                    if not pathlib.Path(exports).exists():  # the page part failed before exporting
                        print("\nThe page part didn't save its exports, so the Python shares run the page themselves.")
                        env.pop("RB_TEST_EXPORTS")
                    for p in later:
                        running[pool.submit(run, p)] = p
                    later = []
    failed = [" ".join(p) for p, code, _, _ in results if code != 0]
    print(f"\n{len(results)} parts in {time.monotonic() - began:.0f}s: " + ", ".join(f"{' '.join(p)} {secs:.0f}s" for p, _, _, secs in results))
    if failed:
        print(f"Failed: {'; '.join(failed)}.")
        sys.exit(1)
    print("All checks passed.")


def main():
    args, share, workers = sys.argv[1:], None, None
    if "--share" in args:
        i = args.index("--share")
        m = re.fullmatch(r"(\d+)/(\d+)", args[i + 1] if i + 1 < len(args) else "")
        if not m or not 1 <= int(m[1]) <= int(m[2]):
            sys.exit("--share needs a share like 1/2.")
        share, args = (int(m[1]), int(m[2])), args[:i] + args[i + 2:]
    if "--parallel" in args:
        i = args.index("--parallel")
        n = args[i + 1] if i + 1 < len(args) and args[i + 1].isdigit() else None
        workers = int(n) if n else max(2, min(4, (os.cpu_count() or 2) + 1))
        args = args[:i] + args[i + (2 if n else 1):]
        if share:
            sys.exit("--parallel runs the shares itself; leave out --share.")
    areas = set(args) or set(AREAS)
    if areas - set(AREAS):
        sys.exit(f"Unknown area: {', '.join(sorted(areas - set(AREAS)))}. The areas are {', '.join(AREAS)}.")
    if workers:
        return parallel(areas, workers)
    if "sources" in areas:
        with timed("sources"):
            sync = subprocess.run([sys.executable, str(ROOT / "tools" / "sync.py"), "--check"], capture_output=True, text=True)
            print("Sources")
            check(sync.returncode == 0, sync.stdout.strip())
            package_check()
            unit = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(HERE / "unit")], capture_output=True, text=True, timeout=300)
            ran = re.search(r"Ran (\d+) tests?", unit.stderr)
            check(unit.returncode == 0, f"the unit tests in tests/unit pass ({ran.group(1) if ran else '?'} tests)"
                  + ("" if unit.returncode == 0 else ":\n" + unit.stderr.strip()[-1500:]))
            example_ini_check()
            docs_check()
            links_check()
            sri_check()
            editor_unit_tests()
    if areas - {"sources"} and not (VENDOR / "blockly").exists():
        sys.exit("Run tests/setup.sh first.")
    exports = os.environ.get("RB_TEST_EXPORTS")
    codes = None
    if "page" not in areas and "python" in areas and exports and pathlib.Path(exports).exists():
        codes = load_exports(exports)
        print(f"Using the page part's exports ({len(codes)} examples)")
    elif areas & {"page", "python"}:
        with timed("page: the page run"):
            codes = asyncio.run(page_tests())
        if exports and not failures:
            save_exports(codes, exports)
    if "page" in areas:
        for fn in (describe_tests, format_tests, program_test_tests, safety_tests, access_tests, pages_tests, offline_tests):
            with timed(f"page: {fn.__name__}"):
                asyncio.run(fn())
    if "i18n" in areas:
        with timed("i18n"):
            asyncio.run(i18n_tests())
    if "gallery" in areas:
        with timed("gallery"):
            asyncio.run(gallery_tests())
            gallery_smoke_tests()
    if "python" in areas:
        with timed("python" + (f" share {share[0]}/{share[1]}" if share else "")):
            python_tests(codes, share)
        if not share or group_share("listeners", share[1]) == share[0]:
            with timed("python: actions_tests"):
                asyncio.run(actions_tests())
    print_times(sorted(PROGRAM_TIMES.items(), key=lambda kv: -kv[1])[:5])
    print()
    if failures:
        print(f"{len(failures)} check(s) failed.")
        sys.exit(1)
    print("All checks passed.")

if __name__ == "__main__":
    main()
