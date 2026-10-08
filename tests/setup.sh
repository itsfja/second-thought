#!/usr/bin/env bash
# One-time setup for the test suite: a headless browser, plus local copies of
# the libraries the page normally loads from a CDN (the tests run offline).
set -euo pipefail
cd "$(dirname "$0")"

PY=python3
python -c "" 2>/dev/null && PY=python   # on Windows, python3 is often a stub
"$PY" -m pip install --quiet playwright pypdf paho-mqtt
"$PY" -m playwright install chromium

mkdir -p vendor
cd vendor
for pkg in blockly@11.2.1 @blockly/field-multilineinput@5.0.15 pdfjs-dist@3.11.174; do
  name="${pkg%@*}"; name="${name#@blockly/}"
  if [ ! -d "$name" ]; then
    tarball=$(npm pack "$pkg" --silent)
    mkdir -p "$name" && tar xzf "$tarball" -C "$name" && rm "$tarball"
  fi
done
echo "Test setup complete."
