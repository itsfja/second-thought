"""Newer runtimes: --doctor says when one is out, and --update-runtime puts it into the program file.

Part of the second_thought package. tools/sync.py joins these files, in order, into
python/runtime.py, which is what ships inside every exported program and the page.
"""
import base64
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from .settings import RUNTIME_VERSION
from .core import _short, to_str
from .settings import tr  # noqa: F401
# ---- package only: tools/sync.py leaves everything above this line out of python/runtime.py ----

# Where the runtime starts and ends in an exported program. tools/sync.py puts these lines first and last in
# python/runtime.py, so --update-runtime swaps the text between them and leaves the program's own part alone.
RUNTIME_START = "# ---- Second Thought runtime starts here: --update-runtime replaces everything down to the line that says it ends ----"
RUNTIME_END = "# ---- Second Thought runtime ends here ----"
# The line the page puts after the program, above its blocks (web/editor/10-python-export.js), and the older one.
# Written in two parts: this runtime goes inside every program, and the page finds the line anywhere in the file.
PROGRAM_MARKS = tuple("# ---- " + who + " program: lets the block editor import this file again ----"
                      for who in ("Second Thought", "Reflection Blocks"))
RELEASES = "https://api.github.com/repos/itsfja/second-thought/releases"
UPDATE_TIMEOUT = 20
RUNTIME_ASSET_LIMIT = 8_000_000

# The public half of the key releases are signed with (#311): 32 bytes of Ed25519 public key, as 64 hex characters.
# The private half never touches GitHub: each release's runtime.py is signed on the maintainer's computer
# (tools/sign_runtime.py) and the .sig is attached to the release. --update-runtime then refuses a runtime whose
# signature doesn't match, so whoever can publish a release can't publish a runtime this program will run. Empty means
# no release has been signed yet, and --update-runtime keeps checking the SHA-256 as before.
UPDATE_SIGNING_KEY = ""

# Pure-Python Ed25519 signature checking (RFC 8032): the standard library has none, and an exported program installs
# nothing. Only verification: signing happens off GitHub, with tools/sign_runtime.py.
_P = 2 ** 255 - 19
_L = 0x1000000000000000000000000000000014def9dea2f79cd65812631a5cf5d3ed
_D = -121665 * pow(121666, _P - 2, _P) % _P
_BY = 4 * pow(5, _P - 2, _P) % _P
_BX = pow((_BY * _BY - 1) * pow(_D * _BY * _BY + 1, _P - 2, _P), (_P + 3) // 8, _P)
if (_BX * _BX - (_BY * _BY - 1) * pow(_D * _BY * _BY + 1, _P - 2, _P)) % _P != 0:
    _BX = _BX * pow(2, (_P - 1) // 4, _P) % _P
if _BX % 2 != 0:
    _BX = _P - _BX
_B = (_BX, _BY)


def _ed25519_point_add(p1, p2):
    x1, y1 = p1
    x2, y2 = p2
    x3 = (x1 * y2 + x2 * y1) * pow(1 + _D * x1 * x2 * y1 * y2, _P - 2, _P)
    y3 = (y1 * y2 + x1 * x2) * pow(1 - _D * x1 * x2 * y1 * y2, _P - 2, _P)
    return x3 % _P, y3 % _P


def _ed25519_point_mul(k, p1):
    out = (0, 1)
    while k > 0:
        if k & 1:
            out = _ed25519_point_add(out, p1)
        p1 = _ed25519_point_add(p1, p1)
        k >>= 1
    return out


def _ed25519_decompress(s):
    y = int.from_bytes(s, "little") & (2 ** 255 - 1)
    x = pow((y * y - 1) * pow(_D * y * y + 1, _P - 2, _P), (_P + 3) // 8, _P)
    if (x * x - (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P)) % _P != 0:
        x = x * pow(2, (_P - 1) // 4, _P) % _P
    if x % 2 != (s[31] >> 7) & 1:
        x = _P - x
    return x, y


def _ed25519_ok(sig, msg, pub):
    """True if sig (64 bytes) is pub's signature of msg: R + h·A == s·B, as RFC 8032 has it."""
    if len(sig) != 64 or len(pub) != 32:
        return False
    try:
        r = _ed25519_decompress(sig[:32])
        a = _ed25519_decompress(pub)
        s = int.from_bytes(sig[32:], "little")
        if s >= _L:
            return False
        h = int.from_bytes(hashlib.sha512(sig[:32] + pub + msg).digest(), "little") % _L
        return _ed25519_point_add(r, _ed25519_point_mul(h, a)) == _ed25519_point_mul(s, _B)
    except (ValueError, ZeroDivisionError):
        return False

# JavaScript's \s, which the page's code hash trims from the end of each line.
_JS_SPACE = "\t\n\v\f\r                  　﻿"


def version_tuple(text):
    """(3, 0, 1) from "3.0.1" or "v3.0.1"; None if it isn't a version."""
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", to_str(text).strip())
    return tuple(int(x) for x in m.groups()) if m else None


def code_hash(text):
    """The page's codeHash(): FNV-1a over the code's UTF-16 units, line endings made \\n, each line's trailing spaces
    and the final newlines left out. An exported file keeps it as # CODE-HASH, so the page knows if the code was edited."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    t = "\n".join(line.rstrip(_JS_SPACE) for line in lines).rstrip("\n")
    units = t.encode("utf-16-le")
    h = 0x811c9dc5
    for i in range(0, len(units), 2):
        h ^= units[i] | (units[i + 1] << 8)
        h = (h * 0x01000193) & 0xffffffff
    return f"{h:08x}"


def security_fix(notes):
    """Whether a release's notes say it fixes something about safety: a Security heading, as CHANGELOG.md has one."""
    return bool(re.search(r"^#{1,6}\s*Security\b", to_str(notes), re.M | re.I))


def runtime_span(text):
    """(start, end) of the runtime in a program's text, as character offsets covering both marker lines; or None."""
    lines = text.split("\n")
    starts = [i for i, line in enumerate(lines) if line.rstrip() == RUNTIME_START]
    ends = [i for i, line in enumerate(lines) if line.rstrip() == RUNTIME_END]
    if len(starts) != 1 or len(ends) != 1 or ends[0] < starts[0]:
        return None
    offset = lambda n: sum(len(line) + 1 for line in lines[:n])  # noqa: E731
    return offset(starts[0]), offset(ends[0]) + len(lines[ends[0]])


def program_mark_at(text):
    """Where the line above the program's blocks starts, or -1."""
    found = [m.start() for mark in PROGRAM_MARKS for m in re.finditer("^" + re.escape(mark) + "[ \t]*$", text, re.M)]
    return min(found) if found else -1


def with_runtime(program, runtime):
    """The program's text with its runtime replaced; None if it isn't marked. Its # CODE-HASH is made right again, unless
    it was already wrong: then the code was edited by hand, and the page should still say so when it's imported."""
    span = runtime_span(program)
    if span is None:
        return None
    new = program[:span[0]] + runtime.strip("\n") + program[span[1]:]
    at, old_at = program_mark_at(new), program_mark_at(program)
    said = re.search(r"^#\s*CODE-HASH:\s*([0-9a-fA-F]+)", program[old_at:], re.M) if old_at >= 0 else None
    if at >= 0 and said and said.group(1).lower() == code_hash(program[:old_at]):
        new = new[:at] + re.sub(r"^(#\s*CODE-HASH:\s*)[0-9a-fA-F]+", lambda m: m.group(1) + code_hash(new[:at]),
                                new[at:], count=1, flags=re.M)
    return new


class Updates:
    """Part of Runtime: whether a newer runtime is out, and putting one into this program file."""

    @staticmethod
    def _releases_get(url, limit=3_000_000):
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "second-thought-runtime/" + RUNTIME_VERSION}
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=UPDATE_TIMEOUT) as r:
            return r.read(limit + 1)

    def newer_releases(self):
        """Published releases newer than this runtime, newest first: [(version, release)]. Raises if GitHub can't be read."""
        url = os.environ.get("RB_RELEASES_URL") or RELEASES
        data = json.loads(self._releases_get(url + ("&" if "?" in url else "?") + "per_page=30") or b"[]")
        out = []
        for rel in data if isinstance(data, list) else []:
            v = version_tuple(rel.get("tag_name")) if isinstance(rel, dict) else None
            if v and v > version_tuple(RUNTIME_VERSION) and not rel.get("draft") and not rel.get("prerelease"):
                out.append((v, rel))
        return sorted(out, key=lambda x: x[0], reverse=True)

    @staticmethod
    def _update_problem(e):
        if isinstance(e, urllib.error.HTTPError):
            return f"HTTP {e.code}"
        return _short(to_str(getattr(e, "reason", None) or e), 120)

    def update_status(self):
        """--doctor's Runtime line: (status, text), or None when update_check = no. Offline is a NOTE, never an error."""
        if os.environ.get("RB_UPDATE_CHECK", "").strip().lower() in ("no", "0", "false", "off"):
            return None
        try:
            newer = self.newer_releases()
        except (urllib.error.URLError, OSError, ValueError) as e:
            return "NOTE", tr("couldn't check for a newer one ({err})", err=self._update_problem(e))
        if not newer:
            return "ok", tr("{version} is the latest", version=RUNTIME_VERSION)
        latest = ".".join(map(str, newer[0][0]))
        same = [v for v, _ in newer if v[0] == version_tuple(RUNTIME_VERSION)[0]]
        how = tr("Run it with --update-runtime to get it.") if same else \
            tr("Import this file on the Second Thought page and export it again to get it.")
        if any(security_fix(rel.get("body")) for _, rel in newer):
            return "FAIL", tr("{latest} is out, with a security fix (this program has {version}). {how}", latest=latest, version=RUNTIME_VERSION, how=how)
        return "NOTE", tr("{latest} is out (this program has {version}). {how}", latest=latest, version=RUNTIME_VERSION, how=how)

    def update_runtime(self, can=None):
        """--update-runtime: replaces this file's runtime with the newest release of the same major version, checked
        against its SHA-256, keeping the blocks, code and settings and a .bak of the old file. Gives the exit code."""
        again = tr("Import this file on the Second Thought page and export it again.")
        prog = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else ""
        try:
            with open(prog, "rb") as f:
                raw = f.read()
            text = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            text = ""
        crlf = "\r\n" in text
        text = text.replace("\r\n", "\n")
        if runtime_span(text) is None:
            print(tr("This file doesn't mark where its runtime starts and ends, so it can't be updated in place.") + " " + again)
            return 1
        try:
            newer = self.newer_releases()
        except (urllib.error.URLError, OSError, ValueError) as e:
            print(tr("Couldn't check for a newer runtime ({err}).", err=self._update_problem(e)))
            return 1
        major = version_tuple(RUNTIME_VERSION)[0]
        same = [(v, rel) for v, rel in newer if v[0] == major]
        if not same:
            if newer:
                print(tr("Runtime {latest} is a new major version, which may change what this program does, so it isn't applied here.",
                         latest=".".join(map(str, newer[0][0]))) + " " + again)
                return 1
            print(tr("Runtime {version} is the latest, so there's nothing to update.", version=RUNTIME_VERSION))
            return 0
        v, rel = same[0]
        latest = ".".join(map(str, v))
        assets = {a.get("name"): a.get("browser_download_url") for a in rel.get("assets") or [] if isinstance(a, dict)}
        if not assets.get("runtime.py") or not assets.get("runtime.py.sha256"):
            print(tr("Release {latest} has no runtime to download.", latest=latest) + " " + again)
            return 1
        try:
            body = self._releases_get(assets["runtime.py"], RUNTIME_ASSET_LIMIT)
            expected = self._releases_get(assets["runtime.py.sha256"], 1000).decode("utf-8", "replace").split()
        except (urllib.error.URLError, OSError, ValueError) as e:
            print(tr("Couldn't check for a newer runtime ({err}).", err=self._update_problem(e)))
            return 1
        if len(body) > RUNTIME_ASSET_LIMIT or not expected or hashlib.sha256(body).hexdigest() != expected[0].lower():
            print(tr("The downloaded runtime doesn't match its SHA-256, so it wasn't used. Nothing was changed."))
            return 1
        if UPDATE_SIGNING_KEY:
            sig = b""
            if assets.get("runtime.py.sig"):
                try:
                    raw = self._releases_get(assets["runtime.py.sig"], 200)
                    sig = base64.b64decode(raw.decode("utf-8", "replace").strip(), validate=True)
                except (urllib.error.URLError, OSError, ValueError):
                    sig = b""
            if not _ed25519_ok(sig, body, bytes.fromhex(UPDATE_SIGNING_KEY)):
                print(tr("Release {latest} isn't signed by the key this runtime holds, so it wasn't used. Nothing was changed.", latest=latest))
                return 1
        try:
            runtime = body.decode("utf-8").replace("\r\n", "\n")
        except UnicodeDecodeError:
            runtime = ""
        said = re.search(r'^RUNTIME_VERSION = "([^"]+)"', runtime, re.M)
        if runtime_span(runtime) != (0, len(runtime.rstrip("\n"))) or not said or version_tuple(said.group(1)) != v:
            print(tr("The downloaded runtime isn't a {latest} runtime, so it wasn't used. Nothing was changed.", latest=latest))
            return 1
        new = with_runtime(text, runtime)
        if crlf:
            new = new.replace("\n", "\r\n")
        backup = prog + ".bak"
        try:
            with open(backup, "wb") as f:
                f.write(raw)
            with open(prog, "w", encoding="utf-8", newline="") as f:
                f.write(new)
        except OSError as e:
            print(tr("Couldn't write {path} ({err}). Nothing was changed.", path=prog, err=_short(to_str(e), 120)))
            return 1
        print(tr("Updated the runtime from {version} to {latest}. The old file is saved as {backup}.",
                 version=RUNTIME_VERSION, latest=latest, backup=os.path.basename(backup)))
        if rel.get("html_url"):
            print(tr("What changed: {url}", url=rel["html_url"]))
        if self.can_acts(can):
            print(tr("The file changed, so it asks to be allowed again before its next run."))
        return 0
