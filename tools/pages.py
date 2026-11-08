"""Builds the copy of the page for GitHub Pages (#245): second-thought.html as index.html, and lang/ beside it.

    python tools/pages.py _site      # what .github/workflows/pages.yml publishes

On claude.ai the page is wrapped in a document (doctype, character set, viewport) when it's published; on GitHub Pages
it's served as it is, so this wraps it the same way. Off claude.ai there's no Claude to call: the page says so itself,
saves files with ordinary browser downloads, and can run programs with the person's own API key (#293).

Because a key can be typed into this copy, it gets a Content-Security-Policy: scripts only from this site, the two
places the page loads libraries from, and the page's own inline scripts (by their hashes, worked out here); and
connections only to this site, api.anthropic.com, the model services that speak OpenAI's chat format and a model
server on this computer (each key goes only to its own service, #321), and cdnjs (the PDF worker's bytes are fetched to
be checked against their fingerprint before it runs, #310), so nothing else the page loads could send a key anywhere.
"""
import base64
import hashlib
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
HEAD = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
        '<meta http-equiv="Content-Security-Policy" content="{csp}">\n'
        '<style>:root{box-sizing:border-box}body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>\n'
        '</head>\n<body>\n')
TAIL = '\n</body>\n</html>\n'
LIBRARIES = "https://cdn.jsdelivr.net https://cdnjs.cloudflare.com"  # Blockly and its plugins; the PDF reader
API = "https://api.anthropic.com"
LOCAL = "http://localhost:* http://127.0.0.1:*"  # a model server on this computer, such as Ollama (#321)


def service_hosts(page):
    """The addresses of the model services the page can call with your own key (#321): those that speak OpenAI's chat
    format, from the SERVICES the page carries."""
    import json
    from urllib.parse import urlsplit
    m = re.search(r'<script[^>]*\bid="services"[^>]*>(.*?)</script>', page, re.S)
    services = json.loads(m.group(1)) if m else []
    return sorted({f"https://{urlsplit(s['base']).netloc}" for s in services if s.get("api") == "openai" and str(s.get("base", "")).startswith("https://")})
INLINE_SCRIPT = re.compile(r"<script(?![^>]*\b(?:src|type)=)[^>]*>(.*?)</script>", re.S)


def csp(page):
    """The policy for this page: its inline scripts allowed by hash, so an injected one wouldn't run."""
    hashes = " ".join("'sha256-" + base64.b64encode(hashlib.sha256(m.group(1).encode("utf-8")).digest()).decode() + "'"
                      for m in INLINE_SCRIPT.finditer(page))
    return "; ".join([
        "default-src 'self'",
        f"script-src 'self' {LIBRARIES} {hashes}",
        f"worker-src 'self' blob: {LIBRARIES}",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",  # Blockly writes its own styles
        "font-src 'self' https://fonts.gstatic.com",
        "img-src 'self' data: blob: https://static.blockly.com",  # Blockly's sprites (Blockly 13's media path)
        # cdnjs: the PDF worker's bytes, fetched to check them (#310); the services: your own keys for them (#321)
        f"connect-src 'self' {API} {' '.join(service_hosts(page))} {LOCAL} https://cdnjs.cloudflare.com",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'none'",
    ])


def build(out):
    out = pathlib.Path(out)
    if out.exists():
        shutil.rmtree(out)
    (out / "lang").mkdir(parents=True)
    page = (ROOT / "second-thought.html").read_text(encoding="utf-8")
    (out / "index.html").write_text(HEAD.replace("{csp}", csp(page)) + page + TAIL, encoding="utf-8")
    for f in sorted((ROOT / "lang").glob("*.js")):
        shutil.copy(f, out / "lang" / f.name)
    (out / ".nojekyll").write_text("", encoding="utf-8")  # serve the files as they are
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python tools/pages.py <folder>")
    done = build(sys.argv[1])
    print(f"Built {done}: index.html and {len(list((done / 'lang').glob('*.js')))} language files.")
