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
    # GitHub sets GITHUB_ACTIONS on its runners: it isn't a setting.
    names -= {"SECOND_THOUGHT_INI", "GITHUB_ACTIONS"} | prefixes | {n for n in names if n.startswith("RB_") and any(f'"{f}": "{n}"' in src for f in friendly)}
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
