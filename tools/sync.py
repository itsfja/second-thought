#!/usr/bin/env python3
"""Keep python/runtime.py and second-thought.html in step with their source files.

The Python runtime is written as a package, python/second_thought/, so each part can be read, reviewed and
tested on its own. Exported programs still come as one file with nothing to install, so this joins the
package's modules, in order, into python/runtime.py (each module's imports, above its "package only" line,
are left out: in one file every name is already there).

The page is published as one HTML file, so the editor's own styles and code (web/editor.css, and web/editor/*.js joined
in the order of their names), that
runtime, its list of model services (SERVICES
in python/second_thought/providers.py, as JSON), what programs can do (CAPABILITIES in core.py), a list of the languages in i18n/*.json, the code-conversion prompt
(prompts/convert-guide.txt), the community gallery's programs (gallery/*.json), the Home Assistant sample house (ha/sample-house.json) and the sample feeds,
GitHub, Telegram, email and calendar (samples/connections.json) are embedded inside it.

Each translation is too big to embed them all, so each i18n/<language>.json is also written as lang/<language>.js,
which the page loads for the chosen language only. Publish the lang/ folder with the page, as its supporting files.
Edit those files (not python/runtime.py, which is rebuilt), then run:

    python tools/sync.py           # rebuild python/runtime.py, lang/*.js and write everything into second-thought.html
    python tools/sync.py --check   # exit 1 if any of them is out of date (used by the tests)
    python tools/sync.py --sri     # refetch the page's CDN libraries and rewrite tools/sri.json, their fingerprints

The page's libraries (Blockly and its plugins, the PDF reader) load from jsDelivr and cdnjs, pinned to exact versions,
and each carries the SHA-384 in tools/sri.json as an integrity attribute (#310), so a file the CDN didn't publish
doesn't run. Bump a version in the page and run --sri, then sync, to move the fingerprint with it; --sri uses the
vendor copies tests/setup.sh makes when they're there, and the internet otherwise (the two agree byte for byte).
"""
import ast
import base64
import hashlib
import json
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGE = ROOT / "second-thought.html"
RUNTIME = ROOT / "python" / "runtime.py"
PACKAGE = ROOT / "python" / "second_thought"
# The order matters: each module may use names from the ones before it.
MODULES = ["settings", "providers", "core", "connectors", "mcp", "agent", "spending", "doctor", "update", "runtime"]
RUNTIME_START = "# ---- Second Thought runtime starts here: --update-runtime replaces everything down to the line that says it ends ----"
RUNTIME_END = "# ---- Second Thought runtime ends here ----"
MARK = "# ---- package only: tools/sync.py leaves everything above this line out of python/runtime.py ----"
SERVICES = PACKAGE / "providers.py"   # its SERVICES list is the page's list of model services too
CAPABILITIES = PACKAGE / "core.py"    # its CAPABILITIES list is the page's list of what programs can do
SAFETY = object()                     # SAFETY in core.py: what always asks, the same rules on the page
MONEY = object()                      # CURRENCIES and RATES in providers.py: the page shows costs the same way
SRI = object()                       # tools/sri.json: the fingerprints of the page's CDN libraries (#310)
I18N = ROOT / "i18n"                  # one <language>.json per language the block palette can be shown in
LANG = ROOT / "lang"                  # the same, as scripts the page loads one at a time: made by this tool
GALLERY = ROOT / "gallery"            # the community gallery: one block file per program, with a "gallery" part
GALLERY_FIELDS = ("title", "description", "tip", "author", "runtime")
# A gallery program's optional "category": where the page groups it. Keep in step with GALLERY_GROUPS in the page.
GALLERY_CATEGORIES = ("github", "coding", "news", "money", "calendar", "home", "learning", "odds")
# The editor's code, one file per area. They're joined in the order of their names into one function in the page, so a
# name declared in one file is seen by all of them. web/editor/README.md says what each holds.
EDITOR = ROOT / "web" / "editor"
# The fingerprints of the page's CDN libraries (#310): their SHA-384, made by `sync.py --sri` and carried by the page
# as each script's integrity attribute, so a file the CDN didn't publish doesn't run.
SRI_FILE = ROOT / "tools" / "sri.json"
VENDOR = ROOT / "tests" / "vendor"   # tests/setup.sh unpacks the same packages here, for the tests to serve offline


def editor_js() -> str:
    """web/editor/*.js, joined in order."""
    files = sorted(EDITOR.glob("*.js"))
    if not files:
        sys.exit("web/editor/ has no .js files: the editor's code lives there.")
    texts = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        if not text.endswith("\n"):
            text += "\n"
        texts.append(text)
    return "".join(texts)


PARTS = [
    ('<script type="text/plain" id="py-runtime">\n', RUNTIME),
    ('<script type="application/json" id="services">\n', SERVICES),
    ('<script type="application/json" id="capabilities">\n', CAPABILITIES),
    ('<script type="application/json" id="safety">\n', SAFETY),
    ('<script type="application/json" id="money">\n', MONEY),
    ('<script type="application/json" id="i18n">\n', I18N),
    ('<script type="application/json" id="sri">\n', SRI),
    ('<script type="application/json" id="community-gallery">\n', GALLERY),
    ('<script type="text/plain" id="convert-guide">\n', ROOT / "prompts" / "convert-guide.txt"),
    ('<script type="application/json" id="ha-sample">\n', ROOT / "ha" / "sample-house.json"),
    ('<script type="application/json" id="connections-sample">\n', ROOT / "samples" / "connections.json"),
    # The editor itself: its styles and its code. Edit these files, not the copies in the page.
    ('<style id="editor-css">\n', ROOT / "web" / "editor.css"),
    ('<script id="editor">\n', EDITOR),
]


def sri() -> dict:
    """tools/sri.json: the SHA-384 of every library file the page loads from a CDN, as {url: "sha384-…"}."""
    if not SRI_FILE.is_file():
        sys.exit("tools/sri.json is missing: run python tools/sync.py --sri to fingerprint the page's libraries.")
    try:
        return json.loads(SRI_FILE.read_text(encoding="utf-8"))
    except ValueError as e:
        sys.exit(f"tools/sri.json isn't valid JSON: {e}")


def sri_urls() -> list:
    """Every library URL the page loads from a CDN: its own script tags, Blockly's words for each language (loaded by
    the page for the language someone picks), and the PDF reader and its worker (loaded when a program reads a PDF).
    Found in the page and the editor's code, so a URL added there is picked up."""
    page = PAGE.read_text(encoding="utf-8")
    urls = list(re.findall(r'src="(https://cdn\.jsdelivr\.net/[^"\']+\.js|https://cdnjs\.cloudflare\.com/[^"\']+\.js)"', page))
    m = re.search(r'<script src="(https://cdn\.jsdelivr\.net/npm/blockly@[\d.]+)/msg/', page)
    if m:  # one file per language the palette can be shown in
        urls += [f"{m.group(1)}/msg/{t['blockly']}.js" for t in _languages().values() if t.get("blockly")]
    m = re.search(r'const base = "(https://cdnjs\.cloudflare\.com/[^"]+?)/?";', editor_js())
    if m:
        base = m.group(1).rstrip("/")
        urls += [base + "/pdf.min.js", base + "/pdf.worker.min.js"]
    return sorted(set(urls))


def _vendor_copy(url: str):
    """The same file in tests/vendor, where tests/setup.sh unpacks the npm packages the CDNs serve (verified: the
    CDN's file and the package's are the same bytes), or None for the ones it doesn't unpack."""
    m = re.fullmatch(r"https://cdn\.jsdelivr\.net/npm/(@blockly/)?([^/@]+)@[\d.]+/(.+)", url)
    if m:  # tests/setup.sh unpacks @blockly's plugins under their bare name
        return VENDOR / m.group(2) / "package" / m.group(3)
    m = re.fullmatch(r"https://cdnjs\.cloudflare\.com/ajax/libs/pdf\.js/[\d.]+/(pdf(?:\.worker)?\.min\.js)", url)
    if m:  # cdnjs serves pdfjs-dist's build files
        return VENDOR / "pdfjs-dist" / "package" / "build" / m.group(1)


def sri_refresh() -> int:
    """`sync.py --sri`: fingerprint every CDN library the page loads, from the vendor copies if they're there and the
    internet otherwise, and rewrite tools/sri.json. Bump a version in the page, run this, then run sync."""
    table = {}
    for url in sri_urls():
        path = _vendor_copy(url)
        try:
            data = path.read_bytes() if path and path.is_file() else urllib.request.urlopen(url, timeout=30).read()
        except OSError as e:
            sys.exit(f"couldn't fingerprint {url}: {e}")
        table[url] = "sha384-" + base64.b64encode(hashlib.sha384(data).digest()).decode()
    SRI_FILE.write_text(json.dumps(table, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"tools/sri.json: fingerprinted {len(table)} library files. Run python tools/sync.py to put the hashes in the page.")
    return 0


def sri_json() -> str:
    """The fingerprints the page needs as it runs, as JSON for it: Blockly's words for each language, and the PDF
    reader and its worker (which isn't a script tag, so the page checks its bytes itself before making it a worker)."""
    table, urls = sri(), sri_urls()
    missing = [u for u in urls if u not in table]
    if missing:
        sys.exit("tools/sri.json has no fingerprint for " + ", ".join(missing) + ". Run python tools/sync.py --sri.")
    out = {"blocklyMsg": {}, "pdf": {}}
    for url in urls:
        m = re.search(r"/msg/([a-z-]+)\.js$", url)
        if m:
            out["blocklyMsg"][m.group(1)] = table[url]
        elif url.endswith("/pdf.min.js"):
            out["pdf"]["main"] = table[url]
        elif url.endswith("/pdf.worker.min.js"):
            out["pdf"]["worker"] = table[url]
    return json.dumps(out, ensure_ascii=False, indent=1) + "\n"


def add_sri(page: str) -> str:
    """Give every CDN script tag in the page its fingerprint and crossorigin, so the browser refuses a file that
    doesn't match (#310). The tags carry nothing else, so this writes them whole and runs again cleanly."""
    table, missing = sri(), []

    def fix(m):
        url = m.group(1)
        if url not in table:
            missing.append(url)
            return m.group(0)
        return f'<script src="{url}" integrity="{table[url]}" crossorigin="anonymous">'

    page = re.sub(r'<script src="(https://cdn\.jsdelivr\.net/[^"\']+\.js|https://cdnjs\.cloudflare\.com/[^"\']+\.js)"'
                  r'(?: integrity="[^"]*"| crossorigin="[^"]*")*>', fix, page)
    if missing:
        sys.exit("tools/sri.json has no fingerprint for " + ", ".join(missing) + ". Run python tools/sync.py --sri.")
    return page


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
    # First and last, the lines --update-runtime looks for (python/second_thought/update.py), so it can swap the
    # runtime inside an exported program for a newer release's python/runtime.py.
    return "\n\n\n".join([RUNTIME_START] + bodies + [RUNTIME_END]) + "\n"


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


def safety_json() -> str:
    """SAFETY in core.py, for the page: what always asks."""
    tree = ast.parse(CAPABILITIES.read_text(encoding="utf-8"))
    found = [n.value for n in tree.body if isinstance(n, ast.Assign) and [ast.unparse(t) for t in n.targets] == ["SAFETY"]]
    if len(found) != 1:
        sys.exit("python/second_thought/core.py should set SAFETY = {...} once, at the top level.")
    return json.dumps(ast.literal_eval(found[0]), ensure_ascii=False, indent=1) + "\n"


def money_json() -> str:
    """CURRENCIES, RATES and BANDS in providers.py, for the page."""
    tree = ast.parse(SERVICES.read_text(encoding="utf-8"))
    out = {}
    for name in ("CURRENCIES", "RATES", "BANDS"):
        found = [n.value for n in tree.body if isinstance(n, ast.Assign) and [ast.unparse(t) for t in n.targets] == [name]]
        if len(found) != 1:
            sys.exit(f"python/second_thought/providers.py should set {name} = {{...}} once, at the top level.")
        out[name.lower()] = ast.literal_eval(found[0])
    return json.dumps(out, ensure_ascii=False, indent=1) + "\n"


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
    files = {LANG / f"{code}.js": f"/* Made by tools/sync.py from i18n/{code}.json: edit that, not this. */\n"
                                  f"(window.ST_I18N_FILES = window.ST_I18N_FILES || {{}})[{json.dumps(code)}] = {_lines(t, 2)};\n"
             for code, t in _languages().items()}
    files.update(word_lists())
    return files


WORDS = ROOT / "docs" / "words"


def word_lists() -> dict:
    """docs/words/<language>.md: a short list of each language's everyday words (the block categories and labels), for
    the Ladybird lesson gallery program to read instead of the whole language file."""
    out = {}
    for code, t in _languages().items():
        pairs = [(k, v) for section in ("categories", "labels") for k, v in (t.get(section) or {}).items() if isinstance(v, str)]
        if pairs:
            out[WORDS / f"{code}.md"] = (f"# {t.get('name', code)}: everyday words\n\n"
                                         f"Made by tools/sync.py from i18n/{code}.json: edit that, not this.\n\n"
                                         + "".join(f"- {k}: {v}\n" for k, v in pairs))
    return out


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
        category = str(info.get("category", "odds")).strip().lower() or "odds"
        if category not in GALLERY_CATEGORIES:
            sys.exit(f"{where}: \"category\" should be one of " + ", ".join(GALLERY_CATEGORIES) + f", not \"{info['category']}\".")
        entry = {"key": "g_" + path.stem.replace("-", "_"), "file": path.name, "category": category}
        entry.update({f: str(info[f]).strip() for f in GALLERY_FIELDS})
        version = data.get("version", 1)
        if not isinstance(version, int) or version < 1:
            sys.exit(f"{where}: \"version\" should be a whole number, the block format the program was saved with.")
        entry["version"] = version
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
        elif path is SAFETY:
            body = safety_json()
        elif path is MONEY:
            body = money_json()
        elif path is SRI:
            body = sri_json()
        elif path == I18N:
            body = i18n_json()
        elif path == GALLERY:
            body = gallery_json()
        elif path == EDITOR:
            body = editor_js()
        else:
            body = runtime if (path == RUNTIME and runtime is not None) else path.read_text(encoding="utf-8")
        closer = "</style>" if opener.startswith("<style") else "</script>"
        if closer[:-1] in body:
            sys.exit(f"{path.relative_to(ROOT)} must not contain '{closer[:-1]}' (it is embedded in a {closer[2:-1]} tag).")
        if opener not in page:
            sys.exit(f"second-thought.html has no {opener.strip()!r} tag to put {path.relative_to(ROOT)} in. "
                     "Put the tag back (an empty one is fine), then run this again.")
        start = page.index(opener) + len(opener)
        if closer not in page[start:]:
            sys.exit(f"The {opener.strip()!r} tag in second-thought.html isn't closed with {closer}.")
        end = page.index(closer, start)
        page = page[:start] + body + page[end:]
    return add_sri(page)


def main() -> int:
    if "--sri" in sys.argv:
        return sri_refresh()
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
        WORDS.mkdir(parents=True, exist_ok=True)
        for path in old_langs:
            path.write_text(langs[path], encoding="utf-8")
        for path in stale:  # a language whose i18n file was removed
            path.unlink()
        changed.append("lang/ (" + ", ".join(p.stem for p in old_langs + stale) + ")")
    print("Updated " + " and ".join(changed) + "." if changed else "Already in sync.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
