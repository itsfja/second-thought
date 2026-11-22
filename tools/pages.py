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

The three typefaces come from the site itself, not Google Fonts (#453): web/fonts/ goes beside the page as fonts/,
and the page's Google Fonts <link> tags become a link to fonts/fonts.css (the CSP's font-src 'self' allows it; the
Google hosts stay in the policy for the script languages' fonts, which the page still loads from there). The font
files are pinned by SHA-384 in tools/fonts.sha384.json and a changed copy is refused. claude.ai keeps Google Fonts.

The community gallery gets a page of its own for each program (#438), at gallery/<name>/, and a list of them at
gallery/: what it does, what it can do, its blocks as an outline, Open in the editor (a #p= link to the page above,
#436) and Download Python (from tools/export.cjs, #441), so a search for "Pi-hole daily report Telegram" can find one
and a forum answer can link to it. They're plain pages, with no scripts at all, and a sitemap lists them. Their Python,
what they can do and their outlines come from the editor's own code in Node (tools/gallery_data.cjs), which needs Node
and Blockly (npm install blockly@13.4.0 @blockly/field-multilineinput@13.4.0, or bash tests/setup.sh).
"""
import base64
import hashlib
import html
import json
import pathlib
import re
import shutil
import subprocess
import sys
import zlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import fonts as fonts_tool  # noqa: E402

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
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",  # Blockly writes its own styles; the script languages' fonts
        "font-src 'self' https://fonts.gstatic.com",  # 'self': the page's own typefaces in fonts/ (#453); gstatic: the script fonts'
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
    bad = fonts_tool.check()
    if bad:
        sys.exit("web/fonts has a file that isn't pinned or doesn't match tools/fonts.sha384.json: "
                 + ", ".join(bad) + " (run python tools/fonts.py --refresh)")
    page = fonts_tool.swap_google_fonts(page, '<link rel="stylesheet" href="fonts/fonts.css">')  # the typefaces from the site (#453)
    (out / "index.html").write_text(HEAD.replace("{csp}", csp(page)) + page + TAIL, encoding="utf-8")
    for f in sorted((ROOT / "lang").glob("*.js")):
        shutil.copy(f, out / "lang" / f.name)
    (out / "fonts").mkdir()
    for f in sorted((ROOT / "web" / "fonts").iterdir()):
        shutil.copy(f, out / "fonts" / f.name)
    (out / ".nojekyll").write_text("", encoding="utf-8")  # serve the files as they are
    gallery_pages(out)
    return out


# ----- The gallery's own pages (#438) -----
SITE = "https://itsfja.github.io/second-thought/"
PAGE_CSP = ("default-src 'none'; style-src 'self'; font-src 'self'; img-src 'self'; script-src 'none'; "
            "object-src 'none'; base-uri 'none'; form-action 'none'")
GALLERY_CSS = """/* The gallery's pages (tools/pages.py, #438): the page's tokens from web/editor.css, and its three typefaces. */
:root{--bg:#F3F4F8;--panel:#FFFFFF;--ink:#1B1E2B;--muted:#5D6278;--line:#DADDE8;--accent:#2F4BDB;--accent-ink:#FFFFFF;
  --warn:#8A5408;--warn-bg:#FCEFD9;--ok:#187652;--ok-bg:#DFF3EA;
  --font-display:"Bricolage Grotesque","Avenir Next",system-ui,sans-serif;
  --font-body:"Atkinson Hyperlegible",system-ui,-apple-system,"Segoe UI",sans-serif;
  --font-mono:"JetBrains Mono",ui-monospace,"SF Mono",Menlo,monospace}
@media (prefers-color-scheme:dark){:root{--bg:#12141C;--panel:#1B1E2A;--ink:#E9EBF3;--muted:#9AA0B8;--line:#2E3243;
  --accent:#7C93FF;--accent-ink:#0E1120;--warn:#F2B55B;--warn-bg:#3A2B12;--ok:#5FD3A4;--ok-bg:#163428;color-scheme:dark}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--font-body);font-size:16px;line-height:1.55}
main{max-width:760px;margin:0 auto;padding:24px 16px 48px}
a{color:var(--accent)}
h1,h2{font-family:var(--font-display);font-weight:700;letter-spacing:-.01em;line-height:1.2}
h1{font-size:30px;margin:8px 0 12px}
h2{font-size:20px;margin:32px 0 8px}
.crumbs,.by{color:var(--muted);font-size:14px}
.lede{font-size:18px}
.tip{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 14px}
.actions{display:flex;flex-wrap:wrap;gap:8px;margin:20px 0}
.button{display:inline-block;padding:9px 16px;border-radius:8px;border:1px solid var(--line);background:var(--panel);color:var(--ink);
  text-decoration:none;font-weight:700;min-height:44px}
.button.primary{background:var(--accent);border-color:var(--accent);color:var(--accent-ink)}
.button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.can{padding-inline-start:20px}
.asks{background:var(--warn-bg);color:var(--warn);border-radius:8px;padding:8px 12px;display:inline-block}
.reads{background:var(--ok-bg);color:var(--ok);border-radius:8px;padding:8px 12px;display:inline-block}
.outline{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 14px;font-family:var(--font-mono);
  font-size:13px;line-height:1.6;overflow-x:auto}
.outline div{white-space:pre-wrap;overflow-wrap:anywhere}
.outline .hat{font-weight:500;color:var(--accent)}
.outline .gap{height:10px}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;padding:0;list-style:none}
.cards li{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.cards a{font-weight:700;text-decoration:none}
.cards p{margin:6px 0 0;color:var(--muted);font-size:14px}
code{font-family:var(--font-mono);font-size:14px}
"""


def _slug(name):
    """A program's file name, as the page and tools/export.cjs make it."""
    s = re.sub(r"\s+", "-", re.sub(r"[^\w\- ]+", "", str(name or "").strip().removesuffix(".json")))[:80]
    return s or "my-program"


def _link(data):
    """The #p= part of a link that offers this program on the page (#436): { version, name, program }, deflated and
    base64url'd as the page packs it."""
    payload = {"version": int(data.get("version") or 1), "name": data.get("name") or "my-program", "program": data["program"]}
    if data.get("tests"):
        payload["tests"] = data["tests"]
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    raw = c.compress(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) + c.flush()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _groups():
    """The gallery's categories and their names, from GALLERY_GROUPS in the editor: { "money": "Community: money", ... }."""
    text = (ROOT / "web" / "editor" / "07-format.js").read_text(encoding="utf-8")
    body = re.search(r"const GALLERY_GROUPS = \{(.*?)\};", text, re.S).group(1)
    return dict(re.findall(r'(\w+):"([^"]+)"', body))


def _doc(title, description, body, depth, canonical):
    up = "../" * depth
    e = html.escape
    return (f'<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            f'<meta http-equiv="Content-Security-Policy" content="{PAGE_CSP}">\n'
            f'<title>{e(title)}</title>\n<meta name="description" content="{e(description)}">\n'
            f'<link rel="canonical" href="{e(canonical)}">\n'
            f'<meta property="og:title" content="{e(title)}">\n<meta property="og:description" content="{e(description)}">\n'
            f'<meta property="og:type" content="website">\n<meta property="og:url" content="{e(canonical)}">\n'
            f'<link rel="stylesheet" href="{up}fonts/fonts.css">\n<link rel="stylesheet" href="{up}gallery/gallery.css">\n'
            f'</head>\n<body>\n<main>\n{body}</main>\n</body>\n</html>\n')


def gallery_data(files):
    """Each gallery file's Python, capabilities and outline, from the editor's own code (tools/gallery_data.cjs)."""
    node = shutil.which("node")
    if not node:
        sys.exit("The gallery's pages need Node (and Blockly: npm install blockly@13.4.0 @blockly/field-multilineinput@13.4.0).")
    r = subprocess.run([node, str(ROOT / "tools" / "gallery_data.cjs"), *map(str, files)], capture_output=True, text=True,
                       encoding="utf-8", timeout=600)
    if r.returncode:
        sys.exit("tools/gallery_data.cjs failed: " + r.stderr.strip()[-800:])
    return {d["file"]: d for d in json.loads(r.stdout)}


def gallery_pages(out):
    """gallery/<name>/index.html for each gallery program, gallery/index.html listing them, and sitemap.xml."""
    e = html.escape
    files = sorted((ROOT / "gallery").glob("*.json"))
    if not files:
        return
    made = gallery_data(files)
    caps = {c[0]: (c[1], c[2]) for c in json.loads(_capabilities_json())}
    groups = _groups()
    gdir = out / "gallery"
    gdir.mkdir()
    (gdir / "gallery.css").write_text(GALLERY_CSS, encoding="utf-8")
    listed, urls = {}, [SITE, SITE + "gallery/"]
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        g, info = data.get("gallery") or {}, made[f.name]
        key, base = f.stem, _slug(data.get("name") or f.stem)
        title = g.get("title") or data.get("name") or key
        group = groups.get(g.get("category") or "odds", groups.get("odds", "")).removeprefix("Community: ")
        group = group[:1].upper() + group[1:]
        here = gdir / key
        here.mkdir()
        (here / (base + ".py")).write_text(info["python"], encoding="utf-8")
        shutil.copy(f, here / (base + ".json"))
        can = [caps[c] for c in info["can"] if c in caps]
        acts = any(a for _, a in can)
        if can:
            does = '<ul class="can">' + "".join(f"<li>{e(t[0].upper() + t[1:])}</li>" for t, _ in can) + "</ul>\n"
            does += ('<p class="asks">It can act on the world, so the exported program asks you before its first run.</p>\n' if acts
                     else '<p class="reads">None of this acts on the world, so the exported program doesn\'t need your yes before its first run.</p>\n')
        else:
            does = '<p class="reads">It only uses your models: it reads nothing of yours and sends nothing.</p>\n'
        rows, new_script = [], True
        for depth, words in info["outline"]:
            if not words:
                rows.append('<div class="gap"></div>')
                new_script = True
                continue
            hat = ' class="hat"' if depth == 0 and new_script else ""
            rows.append(f'<div{hat}>{"  " * depth}{e(words)}</div>')
            new_script = False
        canonical = f"{SITE}gallery/{key}/"
        body = (f'<p class="crumbs"><a href="../../">Second Thought</a> · <a href="../">Gallery</a> · {e(group)}</p>\n'
                f'<h1>{e(title)}</h1>\n<p class="lede">{e(g.get("description", ""))}</p>\n'
                + (f'<p class="tip"><b>Try:</b> {e(g["tip"])}</p>\n' if g.get("tip") else "")
                + f'<p class="by">Shared by {e(g.get("author") or "someone")}' + (f' · made for runtime {e(g["runtime"])}' if g.get("runtime") else "") + '</p>\n'
                f'<p class="actions"><a class="button primary" href="../../#p={_link(data)}">Open in the editor</a>\n'
                f'<a class="button" href="{e(base)}.py" download>Download Python</a>\n'
                f'<a class="button" href="{e(base)}.json" download>Download the block file</a></p>\n'
                f'<h2>What it can do</h2>\n{does}'
                f'<h2>Its blocks</h2>\n<div class="outline">\n' + "\n".join(rows) + '\n</div>\n'
                f'<h2>Running it</h2>\n<p><b>Open in the editor</b> to see the blocks and try it on sample data. To run it for real, '
                f'download the Python, put your keys in <code>second-thought.ini</code> next to it, and run <code>python {e(base)}.py</code>; '
                f'<code>--doctor</code> checks the setup first. <a href="https://github.com/itsfja/second-thought/blob/main/docs/running.md">More on running exported programs</a>.</p>\n')
        (here / "index.html").write_text(_doc(f"{title}: a Second Thought program", g.get("description", ""), body, 2, canonical),
                                         encoding="utf-8")
        listed.setdefault(group, []).append((key, title, g.get("description", "")))
        urls.append(canonical)
    order = [n.removeprefix("Community: ")[:1].upper() + n.removeprefix("Community: ")[1:] for n in groups.values()]
    sections = "".join(f'<h2>{e(name)}</h2>\n<ul class="cards">\n' + "".join(
        f'<li><a href="{e(k)}/">{e(t)}</a><p>{e(d)}</p></li>\n' for k, t, d in sorted(listed[name], key=lambda x: x[1].lower()))
        + "</ul>\n" for name in order if name in listed)
    index = (f'<p class="crumbs"><a href="../">Second Thought</a> · Gallery</p>\n<h1>Programs people shared</h1>\n'
             f'<p class="lede">{len(files)} programs from the Second Thought community, each checked before it was added. '
             'Open one in the editor, or download its Python and run it yourself.</p>\n' + sections)
    (gdir / "index.html").write_text(_doc("Second Thought: the community gallery", f"{len(files)} programs people shared for Second Thought.",
                                          index, 1, SITE + "gallery/"), encoding="utf-8")
    (out / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                     + "".join(f"  <url><loc>{e(u)}</loc></url>\n" for u in urls) + "</urlset>\n", encoding="utf-8")
    (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE}sitemap.xml\n", encoding="utf-8")


def _capabilities_json():
    import sync
    return sync.capabilities_json()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python tools/pages.py <folder>")
    done = build(sys.argv[1])
    print(f"Built {done}: index.html, {len(list((done / 'lang').glob('*.js')))} language files, "
          f"{len(list((done / 'fonts').iterdir()))} typeface files and {len(list((done / 'gallery').glob('*/index.html')))} gallery pages.")
