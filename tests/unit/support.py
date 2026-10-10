"""Shared set-up for the unit tests: imports python/second_thought with settings that can't leak in from your machine.

The runtime reads second-thought.ini and the environment when it's first imported, so this runs before any test
module imports it: an empty settings file, a memory file in a temporary folder, and no keys.
"""
import os
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
TMP = pathlib.Path(tempfile.mkdtemp(prefix="second-thought-unit-"))
(TMP / "empty.ini").write_text("", encoding="utf-8")
os.environ["SECOND_THOUGHT_INI"] = str(TMP / "empty.ini")
os.environ["RB_MEMORY_FILE"] = str(TMP / "memory.json")
for name in list(os.environ):
    if name.endswith(("_API_KEY", "_TOKEN")) or name.startswith("RB_") and name != "RB_MEMORY_FILE":
        del os.environ[name]
sys.path.insert(0, str(ROOT / "python"))

import second_thought  # noqa: E402,F401  (imported here so every test sees the settings above)
