#!/usr/bin/env python3
"""Keep python/runtime.py and second-thought.html in step with their source files.

The Python runtime is written as a package, python/second_thought/, so each part can be read, reviewed and
tested on its own. Exported programs still come as one file with nothing to install, so this joins the
package's modules, in order, into python/runtime.py (each module's imports, above its "package only" line,
are left out: in one file every name is already there).

The page is published as one self-contained HTML file, so that runtime, its list of model services (SERVICES
in python/second_thought/providers.py, as JSON), what programs can do (CAPABILITIES in core.py), the code-conversion prompt
(prompts/convert-guide.txt), the Home Assistant sample house (ha/sample-house.json) and the sample feeds,
GitHub, Telegram, email and calendar (samples/connections.json) are embedded inside it.
Edit those files (not python/runtime.py, which is rebuilt), then run:

    python tools/sync.py           # rebuild python/runtime.py and write everything into second-thought.html
    python tools/sync.py --check   # exit 1 if either is out of date (used by the tests)
"""
import ast
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGE = ROOT / "second-thought.html"
RUNTIME = ROOT / "python" / "runtime.py"
PACKAGE = ROOT / "python" / "second_thought"
# The order matters: each module may use names from the ones before it.
MODULES = ["settings", "providers", "core", "connectors", "mcp", "agent", "runtime"]
MARK = "# ---- package only: tools/sync.py leaves everything above this line out of python/runtime.py ----"
SERVICES = PACKAGE / "providers.py"   # its SERVICES list is the page's list of model services too
CAPABILITIES = PACKAGE / "core.py"    # its CAPABILITIES list is the page's list of what programs can do
PARTS = [
    ('<script type="text/plain" id="py-runtime">\n', RUNTIME),
    ('<script type="application/json" id="services">\n', SERVICES),
    ('<script type="application/json" id="capabilities">\n', CAPABILITIES),
    ('<script type="text/plain" id="convert-guide">\n', ROOT / "prompts" / "convert-guide.txt"),
    ('<script type="application/json" id="ha-sample">\n', ROOT / "ha" / "sample-house.json"),
    ('<script type="application/json" id="connections-sample">\n', ROOT / "samples" / "connections.json"),
]


def bundle() -> str:
    """python/runtime.py, made from the package's modules."""
    bodies = []
    for name in MODULES:
        path = PACKAGE / (name + ".py")
        if not path.is_file():
            sys.exit(f"{path.relative_to(ROOT)} is missing. tools/sync.py lists the modules it joins, in MODULES.")
        text = path.read_text(encoding="utf-8")
        lines = text.split("\n")
        if MARK not in lines:
            sys.exit(f"{path.relative_to(ROOT)} has no line saying where its package-only imports end:\n{MARK}")
        bodies.append("\n".join(lines[lines.index(MARK) + 1:]).strip("\n"))
    return "\n\n\n".join(bodies) + "\n"


def literal_json(path: pathlib.Path, name: str) -> str:
    """A list set at the top level of one of the package's files, as JSON for the page, one entry a line. It's read,
    not run, so it must be plain values."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = [n.value for n in tree.body if isinstance(n, ast.Assign) and [ast.unparse(t) for t in n.targets] == [name]]
    if len(found) != 1:
        sys.exit(f"{path.relative_to(ROOT)} should set {name} = [...] once, at the top level.")
    try:
        items = ast.literal_eval(found[0])
    except ValueError:
        sys.exit(f"{name} in {path.relative_to(ROOT)} must be plain values (text, numbers, lists, dicts), "
                 "since the page reads it as data.")
    return "[\n" + ",\n".join(json.dumps(x, ensure_ascii=False) for x in items) + "\n]\n"


def services_json() -> str:
    """SERVICES in providers.py, for the page."""
    return literal_json(SERVICES, "SERVICES")


def capabilities_json() -> str:
    """CAPABILITIES in core.py, for the page."""
    return literal_json(CAPABILITIES, "CAPABILITIES")


def build(page: str, runtime: str = None) -> str:
    for opener, path in PARTS:
        if path == SERVICES:
            body = services_json()
        elif path == CAPABILITIES and "capabilities" in opener:
            body = capabilities_json()
        else:
            body = runtime if (path == RUNTIME and runtime is not None) else path.read_text(encoding="utf-8")
        if "</script" in body:
            sys.exit(f"{path.relative_to(ROOT)} must not contain '</script' (it is embedded in a script tag).")
        if opener not in page:
            sys.exit(f"second-thought.html has no {opener.strip()!r} tag to put {path.relative_to(ROOT)} in. "
                     "Put the tag back (an empty one is fine), then run this again.")
        start = page.index(opener) + len(opener)
        if "</script>" not in page[start:]:
            sys.exit(f"The {opener.strip()!r} tag in second-thought.html isn't closed with </script>.")
        end = page.index("</script>", start)
        page = page[:start] + body + page[end:]
    return page


def main() -> int:
    runtime = bundle()
    current_rt = RUNTIME.read_text(encoding="utf-8") if RUNTIME.is_file() else ""
    current = PAGE.read_text(encoding="utf-8")
    updated = build(current, runtime)
    if "--check" in sys.argv:
        bad = []
        if runtime != current_rt:
            bad.append("python/runtime.py doesn't match python/second_thought/ (edit the package, not runtime.py)")
        if updated != current:
            bad.append("second-thought.html is out of date")
        if bad:
            print("; ".join(bad) + ". Run: python tools/sync.py")
            return 1
        print("python/runtime.py and second-thought.html are in sync.")
        return 0
    changed = []
    if runtime != current_rt:
        RUNTIME.write_text(runtime, encoding="utf-8")
        changed.append("python/runtime.py")
    if updated != current:
        PAGE.write_text(updated, encoding="utf-8")
        changed.append("second-thought.html")
    print("Updated " + " and ".join(changed) + "." if changed else "Already in sync.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
