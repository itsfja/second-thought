"""Builds the copy of the page for GitHub Pages (#245): second-thought.html as index.html, and lang/ beside it.

    python tools/pages.py _site      # what .github/workflows/pages.yml publishes

On claude.ai the page is wrapped in a document (doctype, character set, viewport) when it's published; on GitHub Pages
it's served as it is, so this wraps it the same way. Off claude.ai there's no Claude to call: the page says so itself,
and saves files with ordinary browser downloads.
"""
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
HEAD = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
        '<style>:root{box-sizing:border-box}body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>\n'
        '</head>\n<body>\n')
TAIL = '\n</body>\n</html>\n'


def build(out):
    out = pathlib.Path(out)
    if out.exists():
        shutil.rmtree(out)
    (out / "lang").mkdir(parents=True)
    page = (ROOT / "second-thought.html").read_text(encoding="utf-8")
    (out / "index.html").write_text(HEAD + page + TAIL, encoding="utf-8")
    for f in sorted((ROOT / "lang").glob("*.js")):
        shutil.copy(f, out / "lang" / f.name)
    (out / ".nojekyll").write_text("", encoding="utf-8")  # serve the files as they are
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python tools/pages.py <folder>")
    done = build(sys.argv[1])
    print(f"Built {done}: index.html and {len(list((done / 'lang').glob('*.js')))} language files.")
