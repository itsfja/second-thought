"""The docs' counts and links, checked against the sources in the unit tests — which always run, so a pull request
that changes only Markdown can't skip them (#412, #419). docs_check and links_check used to live in tests/e2e/sources.py,
which the end-to-end jobs run; those jobs are skipped for Markdown-only pull requests, so #412 was green as a pull
request and failed on main.

The numbers in README.md, the guide in docs/, CONTRIBUTING.md, ROADMAP.md and SECURITY.md are checked here: the
runtime's module table (in CONTRIBUTING.md since #345), every count of examples, community programs, languages,
model services or Home Assistant examples (#308), and every relative link and #anchor leading somewhere (#345).
Counts drift as the project grows, so anything the docs count is checked against what it counts."""
import json
import re
import sys
import unittest

import support

sys.path.insert(0, str(support.ROOT / "tools"))
import sync  # noqa: E402

ROOT = support.ROOT

# Counts the docs spell out as words ("ten groups of Home Assistant examples"), so they can be checked like digits.
NUMBER_WORDS = {w: n for n, w in
                enumerate("one two three four five six seven eight nine ten eleven twelve".split(), 1)}
# The words the number may be written as: a digit, or one of the words above.
_MAYBE_A_NUMBER = r"(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|\d+)"


def _said(pattern, texts):
    """Every counting phrase in the docs that matches, as (the number said, the words that said it)."""
    found = []
    for text in texts:
        for m in re.finditer(pattern, text):
            word = next(g for g in m.groups() if g is not None)
            found.append((int(word) if word.isdigit() else NUMBER_WORDS.get(word), " ".join(m.group(0).split())))
    return found


class Counts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = ["README.md", "CONTRIBUTING.md", "ROADMAP.md"] + sorted(str(p.relative_to(ROOT)) for p in (ROOT / "docs").glob("*.md"))
        cls.texts = [(ROOT / name).read_text(encoding="utf-8") for name in cls.docs]
        cls.library = (ROOT / "web" / "editor" / "06-example-library.js").read_text(encoding="utf-8")

    def _counts(self, what, found, actual, over=False):
        """The docs count 'what' at least once, and every count matches what the sources have ('over N' stays below it)."""
        ok = bool(found) and all(n is not None and (n < actual if over else n == actual) for n, _ in found)
        self.assertTrue(ok, f"the docs' {what} counts match the sources ({actual} now)" +
                        ("" if ok else f", but the docs say: {'; '.join(words for _, words in found)}"))

    def test_module_table_lists_every_module_in_join_order(self):
        # The module table lists exactly what python/second_thought/ holds, in tools/sync.py's join order.
        contributing = self.texts[1]
        table = contributing[contributing.index("The runtime's modules, in the order"):contributing.index("Each module starts with")]
        listed = re.findall(r"^\| `([a-z_]+)\.py` \|", table, re.M)
        self.assertEqual(listed, sync.MODULES,
                         "CONTRIBUTING.md's module table lists every module in python/second_thought/, in tools/sync.py's join order "
                         f"(it lists: {', '.join(listed) or 'nothing'})")

    def test_package_of_n_modules(self):
        contributing = self.texts[1]
        m = re.search(r"package of (\w+) modules", contributing)
        self.assertIsNotNone(m, "CONTRIBUTING.md says 'a package of N modules'")
        self.assertEqual(NUMBER_WORDS.get(m.group(1)), len(sync.MODULES),
                         f"CONTRIBUTING.md says 'a package of {m.group(1) if m else '…'} modules'; "
                         f"python/second_thought/ has {len(sync.MODULES)}")

    def test_counts_match_the_sources(self):
        # What the sources can count, and what the docs say about each.
        texts, library = self.texts, self.library
        examples = len(re.findall(r'\{ key:"', library))
        self._counts("example", [(int(m.group(1)), m.group(0)) for t in texts for m in re.finditer(r"over (\d+)", t)
                                 if "example" in t[max(0, m.start() - 120):m.end() + 120]], examples, over=True)
        self._counts("community program", _said(rf"over {_MAYBE_A_NUMBER} community programs|(?<!over ){_MAYBE_A_NUMBER} community programs", texts),
                     len(list((ROOT / "gallery").glob("*.json"))))
        self._counts("language", _said(rf"over {_MAYBE_A_NUMBER} languages|(?<!over ){_MAYBE_A_NUMBER} languages", texts),
                     len(list((ROOT / "i18n").glob("*.json"))))
        self._counts("model service", _said(rf"over {_MAYBE_A_NUMBER} model services|(?<!over ){_MAYBE_A_NUMBER} model services", texts),
                     len(json.loads(sync.services_json())))
        self._counts("agent example", _said(rf"(?<!over ){_MAYBE_A_NUMBER} agent examples", texts),
                     len(re.findall(r'cat:"Agents"', library)))
        self._counts("Home Assistant example", _said(r"more than (\d+) Home Assistant examples", texts),
                     len(re.findall(r"cat:HC\.", library)), over=True)
        self._counts("group of Home Assistant examples", _said(rf"{_MAYBE_A_NUMBER} groups of Home Assistant examples", texts),
                     len(set(re.findall(r'"(Home Assistant:[^"]+)"', library))))


class Links(unittest.TestCase):
    def test_every_link_leads_somewhere(self):
        """Every relative link and #anchor in the pages leads somewhere: the file exists, and the heading it names is
        in it. GitHub makes each heading's anchor by lower-casing it, dropping punctuation and turning spaces into
        hyphens."""
        def anchors(path):
            text = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
            return {re.sub(r"\s", "-", re.sub(r"[^\w\s-]", "", h.strip().lower())) for h in re.findall(r"^#{1,6} (.+)$", text, re.M)}
        pages = [ROOT / n for n in ("README.md", "CONTRIBUTING.md", "SECURITY.md", "ROADMAP.md")] + sorted((ROOT / "docs").glob("*.md"))
        broken = []
        for page in pages:
            text = re.sub(r"```.*?```", "", page.read_text(encoding="utf-8"), flags=re.S)
            targets = re.findall(r"\]\(([^)\s]+)\)", text) + re.findall(r'<img src="([^"]+)"', text)
            for t in targets:
                if re.match(r"^[a-z]+:", t):
                    continue
                path, _, anchor = t.partition("#")
                dest = (page.parent / path).resolve() if path else page
                if not dest.exists():
                    broken.append(f"{page.relative_to(ROOT)}: {t}")
                elif anchor and dest.suffix == ".md" and anchor not in anchors(dest):
                    broken.append(f"{page.relative_to(ROOT)}: {t} (no such heading)")
        self.assertFalse(broken, f"every link in the README, the guide, CONTRIBUTING, SECURITY and ROADMAP leads somewhere ({len(pages)} pages)"
                                 + (": " + "; ".join(broken[:12]) if broken else ""))


class DesignNotes(unittest.TestCase):
    def test_design_md_exists_and_is_linked_from_the_notes(self):
        """The design notes (#451): docs/design.md exists, and CONTRIBUTING.md and the helpers' shared notes
        (AGENTS.md, #458) link it."""
        design = ROOT / "docs" / "design.md"
        self.assertTrue(design.exists(), "docs/design.md exists")
        for note in ("CONTRIBUTING.md", "AGENTS.md"):
            self.assertIn("docs/design.md", (ROOT / note).read_text(encoding="utf-8"),
                          f"{note} links docs/design.md")

    def test_each_helpers_notes_point_to_agents_md(self):
        """One page of rules for every helper (#458): each tool's own file sends its reader to AGENTS.md first, and
        new pull requests open with the template."""
        for note in ("CLAUDE.md", "MISTRAL.md"):
            self.assertIn("(AGENTS.md)", (ROOT / note).read_text(encoding="utf-8"), f"{note} links AGENTS.md")
        self.assertTrue((ROOT / ".github" / "pull_request_template.md").exists(), "the pull-request template exists")
class RecordedPictures(unittest.TestCase):
    def test_terminal_picture_matches_the_default_run(self):
        """The scripted terminal run in tools/record_docs.py (#454): every model line uses one price band — the review
        on a cheaper model than the draft only happens when a program is told to (the reviewer setting) — and the
        --doctor picture names the current runtime."""
        from second_thought.settings import RUNTIME_VERSION
        src = (ROOT / "tools" / "record_docs.py").read_text(encoding="utf-8")
        def block(name):
            start = src.index(name + ' = """') + len(name) + 4
            return src[start:src.index('"""', start)]
        bands = re.findall(r"Claude, [^(]+\((\w+)\)", block("RUN"))
        self.assertTrue(bands and len(set(bands)) == 1,
                        f"the terminal run's model lines share one price band (the default: review uses the draft's model): {bands}")
        doctor = block("DOCTOR")
        self.assertIn(f"runtime {RUNTIME_VERSION}", doctor,
                      f"the --doctor picture names the current runtime {RUNTIME_VERSION}")


if __name__ == "__main__":
    unittest.main()
