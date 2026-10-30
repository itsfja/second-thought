#!/usr/bin/env python3
"""A git merge driver for the translation files, i18n/<language>.json.

Two pull requests that each add words almost always add them at the end of the same sections, which git sees as a
conflict. This merges the files key by key instead: words added on either side are kept, a word changed on one side
takes that change, and only a word changed differently on both sides is a real conflict, left for a person to decide.

Turn it on once, in your clone (GitHub's web editor doesn't use merge drivers, so merge or rebase locally):

    python tools/merge_i18n.py --install

That tells git to use this for i18n/*.json, and to keep your side of the files tools/sync.py makes (python/runtime.py
and lang/*.js). After a merge or rebase, run python tools/sync.py to rebuild those, and commit them.

Git runs it as:  python tools/merge_i18n.py <ancestor> <ours> <theirs> <path>
It writes the result over <ours>, and exits 1 if anything still conflicts.
"""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def merge(base, ours, theirs, where="", conflicts=None):
    """ours, with theirs' changes laid over it, key by key. Adds each real conflict's key path to conflicts."""
    conflicts = [] if conflicts is None else conflicts
    if isinstance(ours, dict) and isinstance(theirs, dict):
        base = base if isinstance(base, dict) else {}
        out = dict(ours)
        for k, v in theirs.items():
            if k not in ours:
                if k not in base or base[k] != v:  # added by them, or changed by them after we removed it
                    out[k] = v
            elif ours[k] != v:
                out[k] = merge(base.get(k), ours[k], v, f"{where}/{k}", conflicts)
        for k in list(out):
            if k in base and k not in theirs and ours.get(k) == base[k]:
                del out[k]  # they removed it, and we didn't change it
        return out
    if ours == theirs or theirs == base:
        return ours
    if ours == base:
        return theirs
    conflicts.append(where or "/")
    return ours


def dump(data):
    return json.dumps(data, ensure_ascii=False, indent=1) + "\n"


def load(path):
    text = pathlib.Path(path).read_text(encoding="utf-8")
    return json.loads(text) if text.strip() else {}


def main(argv):
    if argv[:1] == ["--install"]:
        for key, value in [("merge.i18n.name", "Second Thought translations, key by key"),
                           ("merge.i18n.driver", f'"{sys.executable}" tools/merge_i18n.py %O %A %B %P'),
                           ("merge.generated.name", "keep ours; tools/sync.py rebuilds it"),
                           ("merge.generated.driver", "true")]:
            subprocess.run(["git", "config", key, value], cwd=ROOT, check=True)
        print("Done. Translation files now merge key by key. After a merge, run: python tools/sync.py")
        return 0
    if len(argv) < 3:
        print(__doc__)
        return 2
    base_path, ours_path, theirs_path = argv[:3]
    name = argv[3] if len(argv) > 3 else ours_path
    try:
        base, ours, theirs = load(base_path), load(ours_path), load(theirs_path)
    except ValueError as e:
        print(f"{name}: can't merge key by key, one side isn't valid JSON ({e}).", file=sys.stderr)
        return 1
    conflicts = []
    out = merge(base, ours, theirs, "", conflicts)
    pathlib.Path(ours_path).write_text(dump(out), encoding="utf-8")
    if conflicts:
        print(f"{name}: changed differently on both sides, kept ours: " + ", ".join(conflicts[:10]), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
