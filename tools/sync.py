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

    python tools/sync.py           # rebuild python/runtime.py, lang/*.js, tools/blocks.json and write everything into second-thought.html
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
# Every block the editor defines, as JSON: type, words, slots, tooltip, palette category, capability (or none).
# Written by this tool from web/editor/*.js (#421); the tests check the gallery, the examples, the conversion guide,
# every language and the capability table against it.
BLOCKS_FILE = ROOT / "tools" / "blocks.json"


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


# ----- The block list: tools/blocks.json, written from the editor's definitions (#421) -----

class _JsReader:
    """Reads the JS literals the block definitions are written in: strings, numbers, booleans, null, arrays,
    objects, and the S(...)/V(...)/val(...) calls they use. Anything else raises, so a new construct in a
    definition is noticed here rather than silently dropped from the list."""

    def __init__(self, text, i=0):
        self.text, self.i = text, i

    def _skip(self):
        t, n = self.text, len(self.text)
        while self.i < n:
            if t[self.i] in " \t\r\n":
                self.i += 1
            elif t.startswith("//", self.i):
                j = t.find("\n", self.i)
                self.i = n if j < 0 else j + 1
            elif t.startswith("/*", self.i):
                self.i = t.index("*/", self.i) + 2
            else:
                break

    def _string(self):
        q = self.text[self.i]
        self.i += 1
        out = []
        while self.text[self.i] != q:
            c = self.text[self.i]
            if c == "\\":
                out.append({"n": "\n", "t": "\t", "r": "\r"}.get(self.text[self.i + 1], self.text[self.i + 1]))
                self.i += 2
            else:
                out.append(c)
                self.i += 1
        self.i += 1
        return "".join(out)

    def value(self):
        v = self._primary()
        while True:  # "..." + "..." concatenation, as in some tooltips
            self._skip()
            if self.text.startswith("+", self.i):
                self.i += 1
                w = self._primary()
                v = v + w if isinstance(v, str) and isinstance(w, str) else {"__ref__": "expression"}
            else:
                return v

    def _primary(self):
        self._skip()
        c = self.text[self.i]
        if c in "\"'":
            return self._string()
        if c == "[":
            self.i += 1
            out = []
            self._skip()
            if self.text[self.i] == "]":
                self.i += 1
                return out
            while True:
                out.append(self.value())
                self._skip()
                if self.text[self.i] == ",":
                    self.i += 1
                    continue
                if self.text[self.i] == "]":
                    self.i += 1
                    return out
                raise ValueError(f"expected ',' or ']' at offset {self.i}")
        if c == "{":
            self.i += 1
            out = {}
            self._skip()
            if self.text[self.i] == "}":
                self.i += 1
                return out
            while True:
                self._skip()
                if self.text[self.i] in "\"'":
                    key = self._string()
                else:
                    m = re.match(r"[A-Za-z_$][\w$]*", self.text[self.i:])
                    if not m:
                        raise ValueError(f"expected a key at offset {self.i}")
                    key = m.group(0)
                    self.i += m.end()
                self._skip()
                if self.text[self.i] != ":":
                    raise ValueError(f"expected ':' at offset {self.i}")
                self.i += 1
                out[key] = self.value()
                self._skip()
                if self.text[self.i] == ",":
                    self.i += 1
                    continue
                if self.text[self.i] == "}":
                    self.i += 1
                    return out
                raise ValueError(f"expected ',' or '}}' at offset {self.i}")
        m = re.match(r"-?\d+(?:\.\d+)?", self.text[self.i:])
        if m:
            self.i += m.end()
            return float(m.group(0)) if "." in m.group(0) else int(m.group(0))
        m = re.match(r"[A-Za-z_$][\w$]*", self.text[self.i:])
        if m:
            name = m.group(0)
            self.i += m.end()
            if name == "true":
                return True
            if name == "false":
                return False
            if name == "null":
                return None
            self._skip()
            if self.text.startswith("(", self.i):  # a call: S(...), V(...) or val(...)
                self.i += 1
                args = []
                self._skip()
                if self.text[self.i] != ")":
                    while True:
                        args.append(self.value())
                        self._skip()
                        if self.text[self.i] == ",":
                            self.i += 1
                            continue
                        break
                if self.text[self.i] != ")":
                    raise ValueError(f"expected ')' at offset {self.i}")
                self.i += 1
                if name == "val" and len(args) == 1 and isinstance(args[0], str):
                    return {"type": "input_value", "name": args[0]}
                return {"__call__": name, "args": args}
            return {"__ref__": name}  # a constant from outside the definition, like TIERS for the model dropdown
        raise ValueError(f"unexpected {c!r} at offset {self.i}")


def _block_entry(value, where):
    """One defineBlocks array element — an S(...)/V(...) call or a raw object literal — as a list entry."""
    if isinstance(value, dict) and "__call__" in value:
        kind, args = value["__call__"], value["args"]
        if kind not in ("S", "V") or len(args) < 3 or not all(isinstance(a, str) for a in args[:2]):
            raise ValueError(f"{where}: unsupported {kind}(...) call in defineBlocks")
        btype, words, inputs = args[0], args[1], args[2]
        extra = args[3] if kind == "S" and len(args) > 3 else (args[4] if kind == "V" and len(args) > 4 else None)
    elif isinstance(value, dict) and "type" in value:
        btype, words, inputs, extra = value["type"], value.get("message0", ""), value.get("args0", []), value
    else:
        raise ValueError(f"{where}: not a block definition: {value!r}")
    slots = [a["name"] for a in inputs if isinstance(a, dict) and isinstance(a.get("name"), str)]
    tooltip = extra.get("tooltip", "") if isinstance(extra, dict) else ""
    return {"type": btype, "words": words, "slots": slots, "tooltip": tooltip if isinstance(tooltip, str) else ""}


def block_definitions() -> list:
    """Every block defined through defineBlocks([...]) in web/editor/*.js, as (type, words, slots, tooltip), sorted by type."""
    entries, seen = [], set()
    for path in sorted(EDITOR.glob("*.js")):
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r"\bdefineBlocks\(\[", text):
            js = _JsReader(text, m.end() - 1)
            arr = js.value()
            if not isinstance(arr, list):
                sys.exit(f"{path.name}: defineBlocks( didn't get an array")
            for v in arr:
                e = _block_entry(v, f"{path.name} at offset {m.start()}")
                if e["type"] in seen:
                    sys.exit(f"{path.name}: block {e['type']} is defined twice")
                seen.add(e["type"])
                entries.append(e)
    entries.sort(key=lambda e: e["type"])
    return entries


def toolbox_categories() -> dict:
    """Block type -> the palette category that lists it, from the B(...) entries in web/editor/03-toolbox.js."""
    text = (EDITOR / "03-toolbox.js").read_text(encoding="utf-8")
    cats, current = {}, None
    for m in re.finditer(r'kind:"category",\s*name:"([^"]+)"|\bB\("([^"]+)"', text):
        if m.group(1):
            current = m.group(1)
        elif current:
            cats.setdefault(m.group(2), current)
    return cats


def _balanced_braces(text, i):
    """The text of the {...} starting at text[i] == '{', string-aware."""
    depth, j = 0, i
    while j < len(text):
        c = text[j]
        if c in "\"'":
            q = c
            j += 1
            while text[j] != q:
                j += 2 if text[j] == "\\" else 1
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[i:j + 1]
        j += 1
    raise ValueError("unbalanced braces")


def block_capabilities():
    """(block type -> its capability id or None, the set of blocks declared as doing nothing) from CAP_BLOCKS and
    NO_CAPABILITY in web/editor/02-blocks.js. A block in CAP_BLOCKS with a function for a value (it depends on a
    field) gets None here; the tests check it's listed, which is what matters."""
    text = (EDITOR / "02-blocks.js").read_text(encoding="utf-8")
    m = re.search(r"const CAP_BLOCKS = \{", text)
    obj = _balanced_braces(text, m.end() - 1)
    caps = {}
    for km in re.finditer(r'(rb_\w+):\s*(?:"([^"]*)"|[^,}\n]+)', obj):
        caps[km.group(1)] = km.group(2)
    m = re.search(r"const NO_CAPABILITY = \((.*?)\)\.split", text, re.S)
    none = set(" ".join(re.findall(r'"([^"]*)"', m.group(1))).split())
    # rb_agent_builtin is classified by its KIND field through CAP_KINDS, so it's in neither list above.
    re.search(r"const CAP_KINDS = \{", text)
    none.add("rb_agent_builtin")
    return caps, none


def blocks_json() -> str:
    """tools/blocks.json: every block the editor defines — type, words, slots, tooltip, the palette category that
    lists it, and its capability (or none) — sorted by type (#421)."""
    caps, none = block_capabilities()
    cats = toolbox_categories()
    entries = []
    for e in block_definitions():
        t = e["type"]
        if t not in caps and t not in none:
            sys.exit(f"web/editor/02-blocks.js: block {t} is in neither CAP_BLOCKS nor NO_CAPABILITY — "
                     "every block declares what it lets a program do, or as doing nothing")
        entries.append({"type": t, "words": e["words"], "slots": e["slots"], "tooltip": e["tooltip"],
                        "category": cats.get(t), "capability": caps.get(t)})
    return json.dumps(entries, ensure_ascii=False, indent=1) + "\n"


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
    blocks = blocks_json()
    blocks_current = BLOCKS_FILE.read_text(encoding="utf-8") if BLOCKS_FILE.is_file() else None
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
        if blocks_current != blocks:
            bad.append("tools/blocks.json is out of date (a block definition changed)")
        if bad:
            print("; ".join(bad) + ". Run: python tools/sync.py")
            return 1
        print("python/runtime.py, lang/, second-thought.html and tools/blocks.json are in sync.")
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
    if blocks_current != blocks:
        BLOCKS_FILE.write_text(blocks, encoding="utf-8")
        changed.append("tools/blocks.json")
    print("Updated " + " and ".join(changed) + "." if changed else "Already in sync.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
