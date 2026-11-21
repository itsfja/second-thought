#!/usr/bin/env python3
"""What a pull request's checks need to run, from the files it changes (#457).

The full suite takes ten minutes side by side, and most pull requests touch one corner of it. CI asks this tool which
of its parts to run:

    git diff --name-only origin/main...HEAD | python tools/ci_scope.py scope --base origin/main   # docs, words, gallery or all
    python tools/ci_scope.py part "page" gallery                                    # the areas that part runs ("" = none)
    git diff --name-only origin/main...HEAD | python tools/ci_scope.py gallery     # the gallery files it changes

The scopes, narrowest first:

- docs:    only Markdown. The end-to-end parts don't run; the unit tests (which read the docs) always do.
- words:   only translations: i18n/*.json, the lang/ and docs/words/ files sync writes from them, tools/latin_kept.json,
           and the page, if only the parts tools/sync.py embeds in it changed (its own HTML, edited by hand, counts
           as code; the sync check makes sure the embedded parts match their sources). The sources and translation
           checks run.
- gallery: only community gallery programs (and words). The sources, translation and gallery checks run, and each
           changed program is loaded, run on the page, exported with tools/export.cjs and checked with --doctor.
- all:     anything else. Everything runs.

A push to main, the nightly run and a run by hand always run everything; so does a release, whose pull request
changes the runtime's version.
"""
import fnmatch
import re
import subprocess
import sys

# The part names in .github/workflows/ci.yml's matrices, and the areas each one runs in full.
PARTS = ("page", "python --share 1/3", "python --share 2/3", "python --share 3/3", "sources i18n gallery")

WORDS = ("i18n/*.json", "lang/*.js", "docs/words/*", "tools/latin_kept.json", "second-thought.html")
GALLERY = ("gallery/*.json",)


def _matches(path, patterns):
    return any(fnmatch.fnmatch(path, p) for p in patterns)


def markup(page):
    """The page's own HTML: everything but the <script> and <style> blocks tools/sync.py and the editor fill in."""
    return re.sub(r"<(script|style)\b[^>]*>.*?</\1>", "", page, flags=re.S)


def scope(changed, page_markup_changed=True):
    """docs, words, gallery or all, for these changed paths (relative to the repository, with / between folders).
    page_markup_changed says whether second-thought.html's own HTML changed, not just what sync embeds in it."""
    paths = [p.strip().replace("\\", "/") for p in changed if p.strip()]
    code = [p for p in paths if not p.endswith(".md")]
    if page_markup_changed and "second-thought.html" in code:
        return "all"
    if not code:
        return "docs"
    if all(_matches(p, WORDS) for p in code):
        return "words"
    if all(_matches(p, WORDS + GALLERY) for p in code):
        return "gallery"
    return "all"


def part(name, scope_name):
    """The areas CI's part `name` runs for this scope, as run_tests.py arguments; "" when it has nothing to do."""
    if name not in PARTS:
        raise ValueError(f"unknown part {name!r}: the parts are {', '.join(PARTS)}")
    if scope_name == "all":
        return name
    if scope_name == "docs" or name != "sources i18n gallery":
        return ""
    return {"words": "sources i18n", "gallery": "sources i18n gallery"}[scope_name]


def gallery_files(changed):
    """The gallery programs among the changed paths, as file names (rye-rain.json)."""
    return sorted({p.strip().replace("\\", "/").split("/")[-1] for p in changed if _matches(p.strip().replace("\\", "/"), GALLERY)})


def main(argv):
    if len(argv) >= 1 and argv[0] == "scope":
        changed = sys.stdin.read().splitlines()
        base = argv[argv.index("--base") + 1] if "--base" in argv else None
        markup_changed = True
        if base and "second-thought.html" in [p.strip() for p in changed]:
            def show(ref):
                return subprocess.run(["git", "show", f"{ref}:second-thought.html"], capture_output=True, text=True,
                                      encoding="utf-8", check=True).stdout
            markup_changed = markup(show(base)) != markup(show("HEAD"))
        print(scope(changed, markup_changed))
    elif len(argv) == 3 and argv[0] == "part":
        print(part(argv[1], argv[2]))
    elif len(argv) >= 1 and argv[0] == "gallery":
        print(" ".join(gallery_files(sys.stdin.read().splitlines())))
    else:
        print(__doc__.split("\n\n")[1])
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
