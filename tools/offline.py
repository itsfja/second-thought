"""Builds second-thought-offline.html (#314): the page as one file that works with no network, attached to each
release by the Release workflow.

    python tools/offline.py second-thought-offline.html     # after bash tests/setup.sh (it needs tests/vendor)

Blockly, its multiline field, Blockly's words for each language and every language file of the page go inside the
file, each library checked against its fingerprint in tools/sri.json first, so a changed copy is refused. Off claude.ai
the page needs your own key to run programs (#293, #321), as on GitHub Pages, and it carries the same
Content-Security-Policy. The PDF reader still loads from its CDN when a program reads a PDF, so offline that's the one
thing it can't do; fonts for scripts many computers lack (Linear B, cuneiform) also come from the web.
"""
import base64
import hashlib
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import pages  # noqa: E402
import sync  # noqa: E402


def _checked(url, fingerprints):
    """A library's text from tests/vendor, refused unless it's the file the page would load from the CDN."""
    path = sync._vendor_copy(url)
    if path is None or not path.is_file():
        sys.exit(f"{url} isn't in tests/vendor: run bash tests/setup.sh first.")
    data = path.read_bytes()
    want = fingerprints.get(url)
    have = "sha384-" + base64.b64encode(hashlib.sha384(data).digest()).decode()
    if have != want:
        sys.exit(f"tests/vendor's copy of {url} isn't the file tools/sri.json fingerprints ({have} != {want}).")
    text = data.decode("utf-8")
    if "</script" in text.lower():
        sys.exit(f"{url} contains </script, so it can't go inside the page as it is.")
    return text


def build(out):
    page = sync.PAGE.read_text(encoding="utf-8")
    fingerprints = sync.sri()
    # The two libraries the page loads with script tags, put inside
    for m in list(re.finditer(r'<script src="(https://cdn\.jsdelivr\.net/[^"]+)" integrity="[^"]+" crossorigin="anonymous"></script>', page)):
        page = page.replace(m.group(0), "<script>\n" + _checked(m.group(1), fingerprints) + "\n</script>", 1)
    # Every language's words, and Blockly's words for it, before the script that picks one: the page uses these instead
    # of loading lang/<code>.js and Blockly's msg/<code>.js
    base = re.search(r"https://cdn\.jsdelivr\.net/npm/blockly@[\d.]+", page)
    msgs = sorted({t["blockly"] for t in sync._languages().values() if t.get("blockly")})
    parts = []
    for code in msgs:
        text = _checked(f"{base.group(0)}/msg/{code}.js", fingerprints)
        parts.append(f'<script>\n(window.ST_BLOCKLY_MSG = window.ST_BLOCKLY_MSG || {{}})["{code}"] = function(){{\n{text}\n}};\n</script>')
    for f in sorted((ROOT / "lang").glob("*.js")):
        parts.append("<script>\n" + f.read_text(encoding="utf-8") + "\n</script>")
    marker = "<script>\n  /* The block palette's language:"
    if page.count(marker) != 1:
        sys.exit("second-thought.html no longer has the script that picks the language, which tools/offline.py puts the languages before.")
    page = page.replace(marker, "\n".join(parts) + "\n" + marker)
    if re.search(r'^<script src="https://', page, re.M):
        sys.exit("A library is still loaded from the CDN; tools/offline.py needs to put it inside too.")
    out = pathlib.Path(out)
    out.write_text(pages.HEAD.replace("{csp}", pages.csp(page)) + page + pages.TAIL, encoding="utf-8")
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python tools/offline.py <file.html>")
    done = build(sys.argv[1])
    print(f"Built {done} ({done.stat().st_size / 1e6:.1f} MB).")
