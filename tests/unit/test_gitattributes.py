"""`.gitattributes`: the files tools/sync.py rebuilds are marked `linguist-generated`, so GitHub folds them away
in a pull request instead of showing ~20 MB of generated file (#456), and keep the `generated` merge rule, so a
clone with `tools/merge_i18n.py --install` keeps our side and rebuilds them. i18n/*.json stays hand-edited: it
keeps the `i18n` merge rule and is NOT linguist-generated."""
import glob as g
import unittest

import support

ROOT = support.ROOT

# path glob -> attributes it must carry
REBUILT = {
    "lang/*.js": {"merge": "generated", "linguist-generated": True},
    "python/runtime.py": {"merge": "generated", "linguist-generated": True},
    "docs/words/*.md": {"merge": "generated", "linguist-generated": True},
}


def _attributes():
    """Parse .gitattributes into {glob: {attribute: value}}; comments and blank lines skipped."""
    out = {}
    for line in (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        glob, attrs = parts[0], {}
        for a in parts[1:]:
            if "=" in a:
                k, v = a.split("=", 1)
                attrs[k] = v
            else:
                attrs[a] = True
        out[glob] = attrs
    return out


class GitattributesTest(unittest.TestCase):
    def test_rebuilt_files_are_linguist_generated(self):
        attrs = _attributes()
        for glob, want in REBUILT.items():
            self.assertIn(glob, attrs, f"{glob} has no line in .gitattributes")
            for name, value in want.items():
                got = attrs[glob].get(name)
                if value is True:
                    self.assertTrue(got, f"{glob} is missing linguist-generated" if name == "linguist-generated" else f"{glob} is missing {name}")
                else:
                    self.assertEqual(got, value, f"{glob}: {name} should be {value!r}")

    def test_i18n_json_stays_hand_edited(self):
        attrs = _attributes()
        self.assertEqual(attrs.get("i18n/*.json", {}).get("merge"), "i18n")
        self.assertNotIn("linguist-generated", attrs.get("i18n/*.json", {}))

    def test_globs_match_real_files(self):
        # the globs must not have drifted away from the files they name
        for pattern in ("lang/*.js", "docs/words/*.md"):
            self.assertTrue(g.glob(str(ROOT / pattern)), f"{pattern} matches nothing")
        self.assertTrue((ROOT / "python" / "runtime.py").is_file())

    def test_every_lang_file_is_covered(self):
        # no rebuilt file left out: every lang/*.js and docs/words/*.md matches a linguist-generated line
        attrs = _attributes()
        gen_globs = [glob for glob, a in attrs.items() if a.get("linguist-generated")]
        self.assertTrue(gen_globs)
        covered = set()
        for pattern in gen_globs:
            covered.update(g.glob(str(ROOT / pattern)))
        for f in g.glob(str(ROOT / "lang" / "*.js")) + g.glob(str(ROOT / "docs" / "words" / "*.md")) + [str(ROOT / "python" / "runtime.py")]:
            self.assertIn(f, covered, f"{f} is not matched by any linguist-generated line")


if __name__ == "__main__":
    unittest.main()
