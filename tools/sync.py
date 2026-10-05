#!/usr/bin/env python3
"""Keep second-thought.html in step with its separate source files.

The page is published as one self-contained HTML file, so the Python runtime
(python/runtime.py) and the code-conversion prompt (prompts/convert-guide.txt)
are embedded inside it. Edit those files, then run:

    python tools/sync.py           # write them into second-thought.html
    python tools/sync.py --check   # exit 1 if the page is out of date (used by the tests)
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGE = ROOT / "second-thought.html"
PARTS = [
    ('<script type="text/plain" id="py-runtime">\n', ROOT / "python" / "runtime.py"),
    ('<script type="text/plain" id="convert-guide">\n', ROOT / "prompts" / "convert-guide.txt"),
]


def build(page: str) -> str:
    for opener, path in PARTS:
        body = path.read_text(encoding="utf-8")
        if "</script" in body:
            sys.exit(f"{path.relative_to(ROOT)} must not contain '</script' (it is embedded in a script tag).")
        start = page.index(opener) + len(opener)
        end = page.index("</script>", start)
        page = page[:start] + body + page[end:]
    return page


def main() -> int:
    current = PAGE.read_text(encoding="utf-8")
    updated = build(current)
    if "--check" in sys.argv:
        if updated != current:
            print("second-thought.html is out of date. Run: python tools/sync.py")
            return 1
        print("second-thought.html is in sync.")
        return 0
    if updated != current:
        PAGE.write_text(updated, encoding="utf-8")
        print("Updated second-thought.html.")
    else:
        print("Already in sync.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
