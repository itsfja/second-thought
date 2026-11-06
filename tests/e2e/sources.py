"""Checks on the sources themselves: the embedded runtime, the packages exported programs need, the example ini."""
from e2e.common import *  # noqa: F401,F403


PY_MARK = "# ---- Second Thought program: lets the block editor import this file again ----"


def js_code_hash(text):
    """The page's codeHash: FNV-1a over the UTF-16 code units, after trimming line ends."""
    t = "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")).rstrip("\n")
    h = 0x811c9dc5
    units = t.encode("utf-16-le")
    for i in range(0, len(units), 2):
        h = ((h ^ int.from_bytes(units[i:i + 2], "little")) * 0x01000193) & 0xFFFFFFFF
    return f"{h:08x}"


def rehash_export(code):
    """An exported program whose code was changed here, with its CODE-HASH redone, so the page treats it as unedited."""
    above, below = code.split(PY_MARK, 1)
    return above + PY_MARK + re.sub(r"# CODE-HASH: [0-9a-f]+", "# CODE-HASH: " + js_code_hash(above), below, count=1)


PACKAGE_CHECK = r"""
import json, os, sys, tempfile
os.environ["RB_MEMORY_FILE"] = os.path.join(tempfile.mkdtemp(), "memory.json")
sys.path.insert(0, sys.argv[1])
from second_thought import Runtime
from second_thought import agent, connectors, core, providers, settings  # noqa: F401
ns = {"__name__": "rt"}
exec(compile(open(sys.argv[2], encoding="utf-8").read(), "rt", "exec"), ns)
names = lambda c: sorted(n for n in dir(c) if not n.startswith("__"))
R = Runtime(); R.reset(); R.log = lambda *a, **k: None
R.remember("hello", "greeting", "permanent")
print(json.dumps({"same": names(Runtime) == names(ns["Runtime"]), "count": len(names(Runtime)),
                  "recall": R.recall("greeting"), "sdk": "anthropic" in sys.modules}))
"""


def package_check():
    """python/second_thought imports on its own (no SDK needed) and its Runtime matches the bundled one."""
    r = subprocess.run([sys.executable, "-I", "-c", PACKAGE_CHECK, str(ROOT / "python"), str(ROOT / "python" / "runtime.py")],
                       capture_output=True, text=True, timeout=60, cwd=tempfile.gettempdir())
    got = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 and r.stdout.strip() else {}
    check(got.get("same") is True and got.get("recall") == "hello" and got.get("sdk") is False,
          f"python/second_thought imports on its own and its Runtime has the same {got.get('count', '?')} parts as python/runtime.py"
          + ("" if got else f" ({r.stderr.strip()[-300:]})"))


def example_ini_check():
    """second-thought.example.ini lists every setting the runtime reads, and reads like a settings file."""
    import configparser
    src = (ROOT / "python" / "runtime.py").read_text(encoding="utf-8")
    names = set(re.findall(r'os\.environ(?:\.get)?[\[(]"([A-Z][A-Z0-9_]*)"', src))
    sys.path.insert(0, str(ROOT / "tools"))
    import sync as sync_tool
    services = json.loads(sync_tool.services_json())
    for s in services:  # each service's address and key settings, and its vision-model setting
        names.update([s["base_env"]] if s.get("base_env") else [])
        names.update(s["keys"])
        names.update([s["vision"][0]] if s.get("vision") else [])
    check(len(services) >= 15 and all(s["keys"] for s in services), f"the settings check sees all {len(services)} model services")
    friendly = set(re.findall(r'"([a-z_]+)": "RB_[A-Z_]+"', src.split("SETTING_NAMES = ", 1)[1].split("}", 1)[0]))
    prefixes = {n for n in names if n.endswith("_")}  # like MODEL_ + a tier's name: the example shows the pattern
    # GitHub sets GITHUB_ACTIONS and GITHUB_STEP_SUMMARY on its runners: they aren't settings.
    names -= {"SECOND_THOUGHT_INI", "GITHUB_ACTIONS", "GITHUB_STEP_SUMMARY"} | prefixes | {n for n in names if n.startswith("RB_") and any(f'"{f}": "{n}"' in src for f in friendly)}
    text = (ROOT / "second-thought.example.ini").read_text(encoding="utf-8")
    listed = {m.upper() for m in re.findall(r"^[;#]?\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", text, re.M)}
    missing = sorted((names | {f.upper() for f in friendly if f != "model"}) - listed)
    check(not missing and "SECOND_THOUGHT_INI" in text and all(re.search("^; " + p_ + "[A-Z]", text, re.M) for p_ in prefixes), "second-thought.example.ini lists every setting the runtime reads" + (f" (missing: {', '.join(missing)})" if missing else ""))
    cp = configparser.ConfigParser(interpolation=None, inline_comment_prefixes=(";", "#"))
    try:
        cp.read_string(text)
        ok = True
    except configparser.Error as e:
        ok = str(e)
    check(ok is True and cp.get("home assistant", "HA_URL") == "http://homeassistant.local:8123" and cp.get("keys", "ANTHROPIC_API_KEY") == "",
          "second-thought.example.ini reads as a settings file, with blank keys and its notes switched off" + ("" if ok is True else f": {ok}"))


# Counts the docs spell out as words ("ten groups of Home Assistant examples"), so they can be checked like digits.
NUMBER_WORDS = {w: n for n, w in
                enumerate("one two three four five six seven eight nine ten eleven twelve".split(), 1)}
# The words the number may be written as: a digit, or one of the words above.
_MAYBE_A_NUMBER = r"(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|\d+)"


def _said(pattern, texts):
    """Every counting phrase in the docs that matches, as (the number said, the words that said it)."""
    found = []
    for text in texts:
        for m in re.finditer(pattern, text):
            word = next(g for g in m.groups() if g is not None)
            found.append((int(word) if word.isdigit() else NUMBER_WORDS.get(word), " ".join(m.group(0).split())))
    return found


def _counts(what, found, actual, over=False):
    """The docs count 'what' at least once, and every count matches what the sources have ('over N' stays below it)."""
    ok = bool(found) and all(n is not None and (n < actual if over else n == actual) for n, _ in found)
    check(ok, f"the docs' {what} counts match the sources ({actual} now)" +
          ("" if ok else f", but the docs say: {'; '.join(words for _, words in found)}"))


def docs_check():
    """The numbers in README.md, ROADMAP.md and docs/ladybird-book.md match the sources: the runtime's module table,
    and every count of examples, community programs, languages, model services or Home Assistant examples (#308).
    Counts drift as the project grows, so anything the docs count is checked against what it counts."""
    sys.path.insert(0, str(ROOT / "tools"))
    import sync as sync_tool
    texts = [(ROOT / name).read_text(encoding="utf-8") for name in ("README.md", "ROADMAP.md", "docs/ladybird-book.md")]

    # The module table lists exactly what python/second_thought/ holds, in tools/sync.py's join order.
    readme = texts[0]
    table = readme[readme.index("The runtime's modules, in the order"):readme.index("Each module starts with")]
    listed = re.findall(r"^\| `([a-z_]+)\.py` \|", table, re.M)
    check(listed == sync_tool.MODULES,
          "README.md's module table lists every module in python/second_thought/, in tools/sync.py's join order "
          f"(it lists: {', '.join(listed) or 'nothing'})")
    m = re.search(r"package of (\w+) modules", readme)
    check(m is not None and NUMBER_WORDS.get(m.group(1)) == len(sync_tool.MODULES),
          f"README.md says 'a package of {m.group(1) if m else '…'} modules'; "
          f"python/second_thought/ has {len(sync_tool.MODULES)}")

    # What the sources can count, and what the docs say about each.
    library = (ROOT / "web" / "editor" / "06-example-library.js").read_text(encoding="utf-8")
    examples = len(re.findall(r'\{ key:"', library))
    _counts("example", [(int(m.group(1)), m.group(0)) for t in texts for m in re.finditer(r"over (\d+)", t)
                        if "example" in t[max(0, m.start() - 120):m.end() + 120]], examples, over=True)
    _counts("community program", _said(rf"over {_MAYBE_A_NUMBER} community programs|(?<!over ){_MAYBE_A_NUMBER} community programs", texts),
            len(list((ROOT / "gallery").glob("*.json"))))
    _counts("language", _said(rf"over {_MAYBE_A_NUMBER} languages|(?<!over ){_MAYBE_A_NUMBER} languages", texts),
            len(list((ROOT / "i18n").glob("*.json"))))
    _counts("model service", _said(rf"over {_MAYBE_A_NUMBER} model services|(?<!over ){_MAYBE_A_NUMBER} model services", texts),
            len(json.loads(sync_tool.services_json())))
    _counts("agent example", _said(rf"(?<!over ){_MAYBE_A_NUMBER} agent examples", texts),
            len(re.findall(r'cat:"Agents"', library)))
    _counts("Home Assistant example", _said(r"more than (\d+) Home Assistant examples", texts),
            len(re.findall(r"cat:HC\.", library)), over=True)
    _counts("group of Home Assistant examples", _said(rf"{_MAYBE_A_NUMBER} groups of Home Assistant examples", texts),
            len(set(re.findall(r'"(Home Assistant:[^"]+)"', library))))


def sri_check():
    """tools/sri.json pins every CDN file the page loads with its SHA-384 (#310): each one is fingerprinted, the page's
    script tags carry theirs, the page's "sri" part holds the ones the page's code adds itself, and the vendor copies
    the tests unpack hash to the same fingerprints the page pins."""
    sys.path.insert(0, str(ROOT / "tools"))
    import sync as sync_tool
    urls, table = sync_tool.sri_urls(), sync_tool.sri()
    bad = sorted(set(urls) ^ set(table) | {u for u in urls if not re.fullmatch(r"sha384-[A-Za-z0-9+/]{64}", table.get(u, ""))})
    check(urls and not bad, f"tools/sri.json fingerprints every CDN file the page loads ({len(urls)} of them), each a SHA-384"
          + (f"; wrong or missing: {', '.join(bad)}" if bad else ""))
    page = (ROOT / "second-thought.html").read_text(encoding="utf-8")
    tagged = [(url, attrs) for url, attrs in
              re.findall(r'<script src="(https://cdn\.(?:jsdelivr\.net|cdnjs\.cloudflare\.com)/[^"]+)"([^>]*)>', page)
              if "'" not in url]  # the palette's language file is written by the page's own code, with its fingerprint
    wrong = [url for url, attrs in tagged
             if f'integrity="{table.get(url)}"' not in attrs or 'crossorigin="anonymous"' not in attrs]
    check(tagged and not wrong, f"every CDN script tag in the page carries its fingerprint and crossorigin ({len(tagged)} tags)"
          + (f"; bare or stale: {', '.join(wrong)}" if wrong else ""))
    part = f'<script type="application/json" id="sri">\n{sync_tool.sri_json()}</script>'
    check(part in page, 'the page\'s "sri" part matches what tools/sri.json says the page checks files against')
    if VENDOR.is_dir():  # tests/setup.sh unpacked the same files the CDNs serve: they must hash to the page's pins
        import hashlib
        wrong = []
        for url in urls:
            path = sync_tool._vendor_copy(url)
            if path and path.is_file() and "sha384-" + base64.b64encode(hashlib.sha384(path.read_bytes()).digest()).decode() != table.get(url):
                wrong.append(url)
        check(not wrong, "the vendor copies the tests unpack hash to the fingerprints the page pins"
              + (f"; don't: {', '.join(wrong)}" if wrong else ""))
