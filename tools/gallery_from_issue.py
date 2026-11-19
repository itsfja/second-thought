#!/usr/bin/env python3
"""Turn an accepted "Share a program" issue into a gallery file (#437).

The page's Share… form opens .github/ISSUE_TEMPLATE/share-a-program.yml with the fields and the #p= link (#436)
filled in. When a maintainer adds the gallery-accepted label, .github/workflows/gallery-share.yml runs this with the
event payload: the issue's fields are read from its body, the link is unpacked (base64url, deflate-raw, JSON) and
checked, and gallery/<name>.json is written in the shape the gallery's other files have. tests/unit/test_gallery.py
(the same checks as on every pull request) is the real gate; this tool fails early with a readable message.

  python tools/gallery_from_issue.py --event $GITHUB_EVENT_PATH --write   # in the workflow
  python tools/gallery_from_issue.py --body "..."                       # dry run: prints the entry as JSON
"""
import argparse
import base64
import json
import pathlib
import re
import sys
import zlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "python"))
from second_thought.settings import RUNTIME_VERSION  # noqa: E402

GALLERY = ROOT / "gallery"
FORMAT = "reflection-blocks"
# The dropdown's labels in .github/ISSUE_TEMPLATE/share-a-program.yml, as the page's GALLERY_GROUPS names them.
CATEGORY_LABELS = {"Community: GitHub": "github", "Community: code and data": "coding", "Community: news": "news",
                   "Community: money": "money", "Community: calendar and email": "calendar",
                   "Community: home and baking": "home", "Community: teaching": "learning",
                   "Community: odds and ends": "odds"}
# What an issue form puts in the body, by the field's label -> its id in the template.
FIELD_LABELS = {"Title": "title", "Category": "category", "Description": "description", "Tip": "tip",
                "Author": "author", "File name": "name", "Runtime": "runtime", "Program link": "link"}
LIMITS = {"title": 40, "author": 40, "description": 300, "tip": 200}
# The same lists tests/unit/test_gallery.py checks a gallery file against — kept in step with it.
SECRETS = [r"sk-[A-Za-z0-9_-]{16,}", r"gh[pousr]_[A-Za-z0-9]{20,}", r"github_pat_\w{20,}", r"xox[abprs]-[A-Za-z0-9-]{10,}",
           r"AKIA[0-9A-Z]{16}", r"AIza[A-Za-z0-9_-]{30,}", r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b", r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}",
           r"(?i)(password|passwd|api[_ ]?key|secret|token)\s*[=:]\s*\S{6,}"]
EMAIL = re.compile(r"[\w.+-]+@([\w-]+\.)+[a-z]{2,}", re.I)
SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
LINK_PART = re.compile(r"#p=([A-Za-z0-9_-]+)")


def fail(msg):
    sys.exit(f"gallery_from_issue: {msg}")


def parse_fields(body):
    """The fields an issue form writes into the body: '### Label' followed by the value, until the next '###'."""
    fields = {}
    label = None
    for line in body.splitlines():
        m = re.match(r"^###\s+(.*)$", line)
        if m:
            label = m.group(1).strip()
            if label in FIELD_LABELS:
                fields[FIELD_LABELS[label]] = []
            continue
        if label in FIELD_LABELS:
            fields[FIELD_LABELS[label]].append(line)
    return {k: "\n".join(v).strip() for k, v in fields.items() if v}


def unpack_link(link):
    """The #p= part of a link, as the page packs it (#436): base64url of deflate-raw of the compact JSON."""
    m = LINK_PART.search(link or "")
    if not m:
        fail("the Program link field has no #p= part: " + (link or "")[:120])
    try:
        raw = base64.urlsafe_b64decode(m.group(1) + "=" * (-len(m.group(1)) % 4))
        data = json.loads(zlib.decompress(raw, -15).decode("utf-8"))
    except Exception as e:
        fail(f"the #p= link doesn't unpack ({e}); it should be a link from the page's Share… form")
    if not isinstance(data, dict):
        fail("the #p= link doesn't hold a program")
    if data.get("format") == FORMAT:
        version, name, program = data.get("version", 1), data.get("name", ""), data.get("program")
    else:
        version, name, program = data.get("version", 1), data.get("name", ""), data.get("program", data)
    if not isinstance(program, dict) or not isinstance(program.get("blocks", {}).get("blocks"), list):
        fail("the #p= link's payload has no blocks")
    return int(version or 1), str(name or ""), program


def category_key(value):
    v = (value or "").strip()
    if v in CATEGORY_LABELS:
        return CATEGORY_LABELS[v]
    if v in CATEGORY_LABELS.values():
        return v
    fail("Category should be one of " + ", ".join(sorted(CATEGORY_LABELS)) + f", not {v!r}")


def build_entry(fields, version, link_name, program):
    for f in ("title", "description", "tip", "author", "name", "runtime", "link"):
        if not fields.get(f):
            fail(f"the issue's {f} field is empty")
    name = fields["name"].strip()
    if not SLUG.match(name):
        fail(f"File name should be lowercase words joined by -, like bake-day-timeline, not {name!r}")
    if (GALLERY / f"{name}.json").exists():
        fail(f"gallery/{name}.json already exists; pick another file name")
    for f, most in LIMITS.items():
        if len(fields[f]) > most:
            fail(f"{f} is over {most} characters ({len(fields[f])})")
    runtime = fields["runtime"].strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", runtime):
        fail(f"Runtime should look like 3.13.0, not {runtime!r}")
    if tuple(int(x) for x in runtime.split(".")) > tuple(int(x) for x in RUNTIME_VERSION.split(".")):
        fail(f"runtime {runtime} is newer than this page's {RUNTIME_VERSION}")
    text = json.dumps(program, ensure_ascii=False)
    for pattern in SECRETS:
        if re.search(pattern, text):
            fail(f"the program looks like it carries a key or password ({pattern}); take it out")
    for m in EMAIL.finditer(text):
        if not re.fullmatch(r"[^@]+@example\.(com|org|net)", m.group(0), re.I):
            fail(f"the program has a real-looking email address ({m.group(0)}); use you@example.com")
    if "rb_run_program" in text:
        fail("the program runs another saved program; it must stand alone")
    return {
        "format": FORMAT,
        "version": version,
        "name": name,
        "gallery": {
            "title": fields["title"].strip(),
            "category": category_key(fields["category"]),
            "description": fields["description"].strip(),
            "tip": fields["tip"].strip(),
            "author": fields["author"].strip(),
            "runtime": runtime,
        },
        "program": program,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--event", help="a GitHub event payload JSON (uses its issue body and number)")
    ap.add_argument("--body", help="the issue body text directly (or @file)")
    ap.add_argument("--write", action="store_true", help="write gallery/<name>.json instead of just printing it")
    args = ap.parse_args()

    if args.event:
        event = json.loads(pathlib.Path(args.event).read_text(encoding="utf-8"))
        body = (event.get("issue") or {}).get("body") or ""
        issue = (event.get("issue") or {}).get("number")
    else:
        body = args.body or ""
        if body.startswith("@"):
            body = pathlib.Path(body[1:]).read_text(encoding="utf-8")
        issue = None
    if not body.strip():
        fail("no issue body given")

    fields = parse_fields(body)
    version, link_name, program = unpack_link(fields.get("link", ""))
    entry = build_entry(fields, version, link_name, program)
    name = entry["name"]
    if args.write:
        path = GALLERY / f"{name}.json"
        path.write_text(json.dumps(entry, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"issue": issue, "name": name, "title": entry["gallery"]["title"],
                      "file": f"gallery/{name}.json", "written": bool(args.write)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
