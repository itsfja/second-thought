#!/usr/bin/env bash
# One-time setup for the test suite: a headless browser, plus local copies of
# the libraries the page normally loads from a CDN (the tests run offline).
set -euo pipefail
cd "$(dirname "$0")"

PY=python3
python -c "" 2>/dev/null && PY=python   # on Windows, python3 is often a stub
"$PY" -m pip install --quiet playwright pypdf paho-mqtt pyyaml cryptography
"$PY" -m playwright install chromium

mkdir -p vendor
cd vendor
for pkg in blockly@13.4.0 @blockly/field-multilineinput@13.4.0 axe-core@4.10.3 pdfjs-dist@3.11.174 @fontsource/noto-sans-linear-b@5.3.0 \
           @fontsource/noto-sans-devanagari@5.3.0 @fontsource/noto-sans-cuneiform@5.3.0 @fontsource/noto-sans-egyptian-hieroglyphs@5.3.0 @fontsource/noto-sans-coptic@5.3.0 @fontsource/noto-sans-syriac@5.3.0 \
           @fontsource/noto-sans-gothic@5.3.0 @fontsource/noto-sans-runic@5.3.0 @fontsource/noto-sans-glagolitic@5.3.0 @fontsource/noto-sans-ethiopic@5.3.0 @fontsource/noto-sans-armenian@5.3.0 @fontsource/noto-sans-ugaritic@5.3.0 @fontsource/noto-sans-phoenician@5.3.0 \
           @fontsource/atkinson-hyperlegible@5.3.0 @fontsource/bricolage-grotesque@5.3.0 @fontsource/jetbrains-mono@5.3.0; do  # the last three: the page's own typefaces (#453)
  name="${pkg%@*}"; name="${name#@blockly/}"
  if [ ! -d "$name" ]; then
    tarball=$(npm pack "$pkg" --silent)
    mkdir -p "$name" && tar xzf "$tarball" -C "$name" && rm "$tarball"
  fi
done
echo "Test setup complete."
