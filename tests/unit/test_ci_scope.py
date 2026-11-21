"""tools/ci_scope.py (#457): which of CI's parts a pull request runs, from the files it changes."""
import sys
import unittest

import support

sys.path.insert(0, str(support.ROOT / "tools"))
import ci_scope  # noqa: E402


class Scope(unittest.TestCase):
    def test_markdown_only_is_docs(self):
        self.assertEqual(ci_scope.scope(["README.md", "docs/running.md"]), "docs")

    def test_translations_are_words(self):
        changed = ["i18n/de.json", "lang/de.js", "docs/words/de.md", "second-thought.html", "CHANGELOG.md"]
        self.assertEqual(ci_scope.scope(changed, page_markup_changed=False), "words")

    def test_gallery_programs_are_gallery(self):
        changed = ["gallery/rye-rain.json", "second-thought.html", "gallery/README.md", "i18n/fr.json"]
        self.assertEqual(ci_scope.scope(changed, page_markup_changed=False), "gallery")
        self.assertEqual(ci_scope.gallery_files(changed), ["rye-rain.json"])

    def test_anything_else_is_all(self):
        for changed in (["web/editor/02-blocks.js"], ["python/second_thought/core.py", "i18n/de.json"],
                        ["tools/sync.py"], [".github/workflows/ci.yml"], ["gallery/README.md", "tests/e2e/page.py"]):
            with self.subTest(changed=changed):
                self.assertEqual(ci_scope.scope(changed), "all")

    def test_the_pages_own_html_changed_by_hand_is_all(self):
        self.assertEqual(ci_scope.scope(["i18n/de.json", "second-thought.html"], page_markup_changed=True), "all")

    def test_markup_ignores_what_sync_embeds(self):
        a = '<div id="x"></div>\n<script id="editor">\nold();\n</script>\n<style>\na{}\n</style>'
        b = '<div id="x"></div>\n<script id="editor">\nnew();\n</script>\n<style>\nb{}\n</style>'
        self.assertEqual(ci_scope.markup(a), ci_scope.markup(b))
        self.assertNotEqual(ci_scope.markup(a), ci_scope.markup(b.replace('id="x"', 'id="y"')))

    def test_windows_paths(self):
        self.assertEqual(ci_scope.scope(["i18n\\de.json", "lang\\de.js"]), "words")


class Parts(unittest.TestCase):
    def test_every_part_runs_everything_for_all(self):
        for name in ci_scope.PARTS:
            self.assertEqual(ci_scope.part(name, "all"), name)

    def test_narrow_scopes_run_only_the_quick_part(self):
        quick = "sources i18n gallery"
        self.assertEqual(ci_scope.part(quick, "words"), "sources i18n")
        self.assertEqual(ci_scope.part(quick, "gallery"), quick)
        self.assertEqual(ci_scope.part(quick, "docs"), "")
        for name in ci_scope.PARTS:
            if name != quick:
                for s in ("docs", "words", "gallery"):
                    self.assertEqual(ci_scope.part(name, s), "", f"{name} for {s}")

    def test_the_parts_are_cis(self):
        ci = (support.ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        listed = '[ ' + ", ".join(f'"{p}"' for p in ci_scope.PARTS) + ' ]'
        self.assertEqual(ci.count(listed), 2, "ci.yml's two matrices list exactly tools/ci_scope.py's PARTS, in order")


if __name__ == "__main__":
    unittest.main()
