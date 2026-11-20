"""The page's self-hosted typefaces (#453): web/fonts/*.woff2 are pinned by SHA-384 in tools/fonts.sha384.json (like
the CDN libraries in tools/sri.json), web/fonts/fonts.css faces exactly those files, and the vendor copies
tests/setup.sh unpacks from the fontsource packages hash to the same pins, so a changed or wrong font file is caught.
tools/pages.py serves the files on GitHub Pages and tools/offline.py puts them inside the offline page; the page
itself keeps Google Fonts for claude.ai."""
import base64
import hashlib
import re
import sys
import unittest

import support

ROOT = support.ROOT
sys.path.insert(0, str(ROOT / "tools"))
import fonts as fonts_tool  # noqa: E402

VENDOR = ROOT / "tests" / "vendor"


class FontPins(unittest.TestCase):
    def test_every_font_file_is_pinned_and_matches(self):
        self.assertEqual(fonts_tool.check(), [],
                         "web/fonts/*.woff2 are exactly the files pinned in tools/fonts.sha384.json, hashes matching "
                         "(run python tools/fonts.py --refresh after replacing one)")

    def test_fonts_css_faces_exactly_the_pinned_files(self):
        css = (ROOT / "web" / "fonts" / "fonts.css").read_text(encoding="utf-8")
        srcs = re.findall(r'src: url\("([^"]+\.woff2)"\)', css)
        pinned = sorted(k.split("/")[-1] for k in fonts_tool.pins())
        self.assertEqual(sorted(srcs), pinned, "fonts.css points at exactly the pinned woff2 files")
        self.assertEqual(len(re.findall(r"@font-face", css)), len(pinned))
        fams = {re.search(r"font-family: '([^']+)'", b).group(1)
                for b in re.findall(r"@font-face \{(.*?)\}", css, re.S)}
        self.assertEqual(fams, {"Atkinson Hyperlegible", "Bricolage Grotesque", "JetBrains Mono"})
        for b in re.findall(r"@font-face \{(.*?)\}", css, re.S):
            for prop in ("font-weight:", "unicode-range:"):
                self.assertIn(prop, b, "every face declares its weight and subset")

    def test_vendor_copies_hash_to_the_pins(self):
        # tests/setup.sh unpacks the fontsource packages; their files must be the same bytes we committed
        wrong, seen = [], 0
        for rel, want in fonts_tool.pins().items():
            name = rel.split("/")[-1]
            pkg = next(p for prefix, p in fonts_tool.PACKAGES.items() if name.startswith(prefix + "-"))
            path = VENDOR / pkg.split("@")[0] / "package" / "files" / name
            if path.is_file():
                seen += 1
                have = "sha384-" + base64.b64encode(hashlib.sha384(path.read_bytes()).digest()).decode()
                if have != want:
                    wrong.append(name)
        if VENDOR.is_dir() and seen:
            self.assertEqual(wrong, [], f"the vendor copies of the typefaces hash to the pins; don't: {wrong}")

    def test_the_page_has_the_google_fonts_links_once(self):
        page = (ROOT / "second-thought.html").read_text(encoding="utf-8")
        self.assertEqual(len(fonts_tool.GOOGLE_FONTS.findall(page)), 1,
                         "the page loads its typefaces from Google Fonts exactly once (pages.py/offline.py swap that block)")


if __name__ == "__main__":
    unittest.main()
