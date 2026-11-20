"""The page's three typefaces as files of the site (#453): web/fonts/*.woff2 plus web/fonts/fonts.css, pinned by
SHA-384 in tools/fonts.sha384.json like the CDN libraries are in tools/sri.json, so a changed copy is refused.

The page itself keeps loading them from Google Fonts (the artifact on claude.ai has no use for local files);
tools/pages.py serves the files beside the page on GitHub Pages and points the page at fonts/fonts.css, and
tools/offline.py puts the faces inside the offline page as data: URIs.

    python tools/fonts.py --refresh    # after replacing a font file: re-pin web/fonts/*.woff2
"""
import base64
import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FONTS_DIR = ROOT / "web" / "fonts"
PINS_FILE = ROOT / "tools" / "fonts.sha384.json"

# The three <link> tags in the page's head that load the typefaces from Google Fonts; pages.py and offline.py
# replace them. The runtime <link> for a script language's font is written by the page's own code and stays.
GOOGLE_FONTS = re.compile(
    r'<link rel="preconnect" href="https://fonts\.googleapis\.com">\s*\n'
    r'<link rel="preconnect" href="https://fonts\.gstatic\.com" crossorigin>\s*\n'
    r'<link rel="stylesheet" href="https://fonts\.googleapis\.com/css2\?[^"]+">')

# The fontsource npm package each file comes from, for the vendor cross-check in the tests: file -> package@version
PACKAGES = {
    "atkinson-hyperlegible": "@fontsource/atkinson-hyperlegible@5.3.0",
    "bricolage-grotesque": "@fontsource/bricolage-grotesque@5.3.0",
    "jetbrains-mono": "@fontsource/jetbrains-mono@5.3.0",
}


def pins() -> dict:
    """tools/fonts.sha384.json: {"web/fonts/<file>": "sha384-…"} for every typeface file."""
    if not PINS_FILE.is_file():
        sys.exit("tools/fonts.sha384.json is missing: run python tools/fonts.py --refresh to pin the fonts.")
    try:
        return json.loads(PINS_FILE.read_text(encoding="utf-8"))
    except ValueError as e:
        sys.exit(f"tools/fonts.sha384.json isn't valid JSON: {e}")


def check() -> list:
    """Every font file on disk is pinned with its SHA-384, and every pin has its file; the caller refuses to build on
    a non-empty list, as tools/offline.py does for the libraries' fingerprints."""
    table = pins()
    disk = {f"web/fonts/{p.name}": "sha384-" + base64.b64encode(hashlib.sha384(p.read_bytes()).digest()).decode()
            for p in sorted(FONTS_DIR.glob("*.woff2"))}
    bad = [k for k in sorted(set(disk) | set(table)) if disk.get(k) != table.get(k)]
    return bad


def refresh() -> int:
    """`fonts.py --refresh`: fingerprint every web/fonts/*.woff2 and rewrite tools/fonts.sha384.json."""
    table = {f"web/fonts/{p.name}": "sha384-" + base64.b64encode(hashlib.sha384(p.read_bytes()).digest()).decode()
             for p in sorted(FONTS_DIR.glob("*.woff2"))}
    PINS_FILE.write_text(json.dumps(table, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"tools/fonts.sha384.json: pinned {len(table)} typeface files.")
    return 0


def css(inline=False) -> str:
    """web/fonts/fonts.css, with the pins checked first; inline=True puts each woff2 in as a data: URI, for the
    offline page (#453)."""
    bad = check()
    if bad:
        sys.exit("web/fonts has a file that isn't pinned or doesn't match its pin in tools/fonts.sha384.json: "
                 + ", ".join(bad) + " (run python tools/fonts.py --refresh after replacing a font)")
    text = (FONTS_DIR / "fonts.css").read_text(encoding="utf-8")
    if not inline:
        return text
    def to_data(m):
        path = FONTS_DIR / m.group(1)
        return 'url("data:font/woff2;base64,' + base64.b64encode(path.read_bytes()).decode() + '") format("woff2")'
    return re.sub(r'url\("([^"]+\.woff2)"\) format\("woff2"\)', to_data, text)


def swap_google_fonts(page: str, replacement: str) -> str:
    """Replace the page's Google Fonts <link> tags with `replacement` (a local fonts.css link on Pages, an inline
    <style> in the offline page); refuses if the tags aren't there exactly once."""
    n = len(GOOGLE_FONTS.findall(page))
    if n != 1:
        sys.exit(f"second-thought.html no longer has the Google Fonts links exactly once ({n} found); "
                 "tools' font swap needs updating.")
    return GOOGLE_FONTS.sub(lambda m: replacement, page, count=1)


if __name__ == "__main__":
    if sys.argv[1:] == ["--refresh"]:
        raise SystemExit(refresh())
    sys.exit("Usage: python tools/fonts.py --refresh")
