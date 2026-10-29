#!/usr/bin/env python3
"""Keep python/runtime.py and second-thought.html in step with their source files.

The Python runtime is written as a package, python/second_thought/, so each part can be read, reviewed and
tested on its own. Exported programs still come as one file with nothing to install, so this joins the
package's modules, in order, into python/runtime.py (each module's imports, above its "package only" line,
are left out: in one file every name is already there).

The page is published as one HTML file, so that runtime, its list of model services (SERVICES
in python/second_thought/providers.py, as JSON), what programs can do (CAPABILITIES in core.py), a list of the languages in i18n/*.json, the code-conversion prompt
(prompts/convert-guide.txt), the community gallery's programs (gallery/*.json), the Home Assistant sample house (ha/sample-house.json) and the sample feeds,
GitHub, Telegram, email and calendar (samples/connections.json) are embedded inside it.

Each translation is too big to embed them all, so each i18n/<language>.json is also written as lang/<language>.js,
which the page loads for the chosen language only. Publish the lang/ folder with the page, as its supporting files.
Edit those files (not python/runtime.py, which is rebuilt), then run:

    python tools/sync.py           # rebuild python/runtime.py, lang/*.js and write everything into second-thought.html
    python tools/sync.py --check   # exit 1 if any of them is out of date (used by the tests)
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
MODULES = ["settings", "providers", "core", "connectors", "mcp", "agent", "doctor", "runtime"]
MARK = "# ---- package only: tools/sync.py leaves everything above this line out of python/runtime.py ----"
SERVICES = PACKAGE / "providers.py"   # its SERVICES list is the page's list of model services too
CAPABILITIES = PACKAGE / "core.py"    # its CAPABILITIES list is the page's list of what programs can do
I18N = ROOT / "i18n"                  # one <language>.json per language the block palette can be shown in
LANG = ROOT / "lang"                  # the same, as scripts the page loads one at a time: made by this tool
GALLERY = ROOT / "gallery"            # the community gallery: one block file per program, with a "gallery" part
GALLERY_FIELDS = ("title", "description", "tip", "author", "runtime")
PARTS = [
    ('<script type="text/plain" id="py-runtime">\n', RUNTIME),
    ('<script type="application/json" id="services">\n', SERVICES),
    ('<script type="application/json" id="capabilities">\n', CAPABILITIES),
    ('<script type="application/json" id="i18n">\n', I18N),
    ('<script type="application/json" id="community-gallery">\n', GALLERY),
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


def _lines(value, depth: int) -> str:
    """JSON with each key of the top `depth` levels of objects on its own line, and everything below that compact."""
    if depth == 0 or not isinstance(value, dict) or not value:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return "{\n" + ",\n".join(json.dumps(k, ensure_ascii=False) + ":" + _lines(v, depth - 1)
                              for k, v in value.items()) + "\n}"


def _languages() -> dict:
    langs = {}
    for path in sorted(I18N.glob("*.json")):
        try:
            langs[path.stem] = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as e:
            sys.exit(f"{path.relative_to(ROOT)} isn't valid JSON: {e}")
    return langs


def i18n_json() -> str:
    """The languages the page offers, for its Blocks menu, as {"es": {"name": "Español"}, ...}. The words themselves are in
    lang/<language>.js, which the page loads for the chosen language only."""
    return _lines({code: {"name": t.get("name", code)} for code, t in _languages().items()}, 1) + "\n"


def lang_files() -> dict:
    """lang/<language>.js for each i18n/<language>.json: a script that hands the page that language's words.

    Each section and each entry in a section goes on its own line, so changing one translated phrase changes one line.
    """
    return {LANG / f"{code}.js": f"/* Made by tools/sync.py from i18n/{code}.json: edit that, not this. */\n"
                                 f"(window.ST_I18N_FILES = window.ST_I18N_FILES || {{}})[{json.dumps(code)}] = {_lines(t, 2)};\n"
            for code, t in _languages().items()}


def gallery_json() -> str:
    """Every gallery/<name>.json, as a list for the page, by title. The page works out what each program can do from
    its blocks; an entry never says so itself (tests/unit/test_gallery.py has the rest of the checks)."""
    entries = []
    for path in sorted(GALLERY.glob("*.json")):
        where = path.relative_to(ROOT)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as e:
            sys.exit(f"{where} isn't valid JSON: {e}")
        info = data.get("gallery") if isinstance(data, dict) else None
        if not isinstance(info, dict) or not isinstance(data.get("program"), dict):
            sys.exit(f"{where} should be a block file saved from the page, with a \"gallery\" part added (see gallery/README.md).")
        missing = [f for f in GALLERY_FIELDS if not str(info.get(f, "")).strip()]
        if missing:
            sys.exit(f"{where}: the \"gallery\" part needs " + ", ".join(missing) + ".")
        entry = {"key": "g_" + path.stem.replace("-", "_"), "file": path.name}
        entry.update({f: str(info[f]).strip() for f in GALLERY_FIELDS})
        entry["program"] = data["program"]
        entries.append(entry)
    entries.sort(key=lambda e: e["title"].lower())
    return "[\n" + ",\n".join(json.dumps(e, ensure_ascii=False, separators=(",", ":")) for e in entries) + "\n]\n"


def build(page: str, runtime: str = None) -> str:
    for opener, path in PARTS:
        if path == SERVICES:
            body = services_json()
        elif path == CAPABILITIES and "capabilities" in opener:
            body = capabilities_json()
        elif path == I18N:
            body = i18n_json()
        elif path == GALLERY:
            body = gallery_json()
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
    langs = lang_files()
    stale = sorted(set(LANG.glob("*.js")) - set(langs))
    old_langs = sorted(path for path, text in langs.items() if not path.is_file() or path.read_text(encoding="utf-8") != text)
    if "--check" in sys.argv:
        bad = []
        if runtime != current_rt:
            bad.append("python/runtime.py doesn't match python/second_thought/ (edit the package, not runtime.py)")
        if updated != current:
            bad.append("second-thought.html is out of date")
        if old_langs or stale:
            bad.append("lang/ is out of date (" + ", ".join(p.name for p in old_langs + stale) + ")")
        if bad:
            print("; ".join(bad) + ". Run: python tools/sync.py")
            return 1
        print("python/runtime.py, lang/ and second-thought.html are in sync.")
        return 0
    changed = []
    if runtime != current_rt:
        RUNTIME.write_text(runtime, encoding="utf-8")
        changed.append("python/runtime.py")
    if updated != current:
        PAGE.write_text(updated, encoding="utf-8")
        changed.append("second-thought.html")
    if old_langs or stale:
        LANG.mkdir(exist_ok=True)
        for path in old_langs:
            path.write_text(langs[path], encoding="utf-8")
        for path in stale:  # a language whose i18n file was removed
            path.unlink()
        changed.append("lang/ (" + ", ".join(p.stem for p in old_langs + stale) + ")")
    print("Updated " + " and ".join(changed) + "." if changed else "Already in sync.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
