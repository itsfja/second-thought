"""Reading second-thought.ini (and the environment) before anything else.

Part of the second_thought package. tools/sync.py joins these files, in order, into
python/runtime.py, which is what ships inside every exported program and the page.
"""
# ---- package only: tools/sync.py leaves everything above this line out of python/runtime.py ----
# ---------------------------------------------------------------------------
# Runtime: how each block behaves. You normally don't need to edit this part.
# ---------------------------------------------------------------------------
import asyncio
import base64
import contextlib
import contextvars
import copy
import datetime
import hashlib
import json
import math
import os
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

# Which runtime this is. Every exported program carries its own copy of the runtime, so this says which one it has:
# run the program with --version to see it. What changed in each version is in CHANGELOG.md, in the Second Thought folder.
RUNTIME_VERSION = "2.2.0"

# Windows consoles and redirected output can't always show every character; never crash over one.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

# ----- Settings file -----
# Keys and settings live in second-thought.ini, next to this program (it comes in the exported zip).
# Python looks for it next to the program, then in the current folder, then in your home folder;
# SECOND_THOUGHT_INI can point somewhere else. A real environment variable wins over the file.
SETTINGS_FILE = "second-thought.ini"
SETTING_NAMES = {"primary": "RB_MODEL_TIER", "model": "RB_MODEL_TIER", "backups": "RB_BACKUPS",
                 "max_seconds": "RB_MAX_SECONDS", "call_timeout": "RB_CALL_TIMEOUT",
                 "budget": "RB_BUDGET", "save_log": "RB_SAVE_LOG", "stream": "RB_STREAM", "resume": "RB_RESUME",
                 "feeds": "RB_FEEDS", "local_pages": "RB_LOCAL_PAGES",
                 "approve": "RB_APPROVE", "mcp_timeout": "RB_MCP_TIMEOUT", "language": "RB_LANGUAGE",
                 "keychain": "RB_KEYCHAIN"}


def _load_settings():
    import configparser
    here = os.path.dirname(os.path.abspath(sys.argv[0])) if sys.argv and sys.argv[0] else os.getcwd()
    places = [os.environ.get("SECOND_THOUGHT_INI", ""), os.path.join(here, SETTINGS_FILE),
              os.path.join(os.getcwd(), SETTINGS_FILE), os.path.join(os.path.expanduser("~"), SETTINGS_FILE)]
    path = next((p for p in places if p and os.path.isfile(p)), None)
    if not path:
        return None
    cp = configparser.ConfigParser(interpolation=None, inline_comment_prefixes=(";", "#"))
    cp.optionxform = str
    try:
        cp.read(path, encoding="utf-8-sig")  # -sig: Notepad sometimes adds a marker at the start
    except (configparser.Error, UnicodeDecodeError) as e:
        sys.exit(f"There's a mistake in {path}:\n{e}")
    for section in cp.sections():
        for name, value in cp.items(section):
            value = value.strip().strip('"').strip("'")
            key = SETTING_NAMES.get(name.lower(), name.upper())
            if value and not os.environ.get(key):
                os.environ[key] = value
                KEY_SOURCES[key] = "file"
    return path


# Where each key came from, for --doctor: "environment", "file" (second-thought.ini) or "keychain".
KEY_SOURCES = {k: "environment" for k in os.environ}
SETTINGS_PATH = _load_settings()

# ----- Keychain (optional) -----
# Keys can live in your computer's keychain (macOS Keychain, Windows Credential Manager, the Secret Service on Linux)
# instead of second-thought.ini, if the keyring package is installed:  pip install keyring  then, for each key,
#   python -m keyring set second-thought ANTHROPIC_API_KEY
# A key in the environment or second-thought.ini wins over the keychain. Without keyring, nothing changes.
KEYCHAIN_SERVICE = "second-thought"
KEYCHAIN_NAMES = (
    "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "LLAMA_API_KEY", "DEEPSEEK_API_KEY", "XAI_API_KEY", "OPENAI_API_KEY",
    "MISTRAL_API_KEY", "DASHSCOPE_API_KEY", "MOONSHOT_API_KEY", "PERPLEXITY_API_KEY", "HF_TOKEN", "GROQ_API_KEY", "ZAI_API_KEY",
    "MINIMAX_API_KEY", "OPENROUTER_API_KEY", "HUGGINGFACE_API_KEY", "KIMI_API_KEY", "QWEN_API_KEY", "ZHIPUAI_API_KEY", "GITHUB_TOKEN", "TELEGRAM_BOT_TOKEN", "DISCORD_BOT_TOKEN", "SLACK_BOT_TOKEN",
    "EMAIL_PASSWORD", "HA_TOKEN", "HOMEY_API_KEY", "MQTT_PASSWORD", "WEBHOOK_SECRET")


def _load_keychain():
    """Fills in keys missing from the environment and second-thought.ini from the keychain. Gives back the problem, if
    keyring is installed but couldn't be read (no keychain on this computer, say); None otherwise."""
    import importlib.util
    if os.environ.get("RB_KEYCHAIN", "").strip().lower() in ("no", "0", "false", "off") or importlib.util.find_spec("keyring") is None:
        return None
    try:
        import keyring
        for name in KEYCHAIN_NAMES:
            if not os.environ.get(name):
                value = keyring.get_password(KEYCHAIN_SERVICE, name)
                if value:
                    os.environ[name] = value.strip()
                    KEY_SOURCES[name] = "keychain"
    except Exception as e:  # noqa: BLE001 - a keychain that can't be read must never stop a program
        return f"{type(e).__name__}: {e}"
    return None


KEYCHAIN_PROBLEM = _load_keychain()


# ----- Language -----
# What the program prints (its run log, questions, errors and --doctor) can be in another language. A program exported
# from a page shown in Spanish carries the Spanish words (EXPORT_WORDS, written above this runtime) and speaks Spanish;
# language = en in second-thought.ini switches it back to English. A program without the words speaks English.
_WORDS = globals().get("EXPORT_WORDS") or {}
LANGUAGE = (os.environ.get("RB_LANGUAGE") or globals().get("EXPORT_LANGUAGE") or "en").strip().lower()


def tr(_text, **slots):
    """The text in the program's language, with each {name} filled in: tr("Saved {name}.", name=n)."""
    words = _WORDS.get(_text, _text) if LANGUAGE != "en" else _text
    if not slots:
        return words
    return re.sub(r"\{(\w+)\}", lambda m: str(slots[m.group(1)]) if m.group(1) in slots else m.group(0), words)


def said_yes(answer):
    """y or yes, or a yes in the program's language: its words give "(yes)" as a list, like "s, si, sí" or "o, oui"."""
    a = str(answer).strip().lower()
    yes = tr("(yes)")
    return a in ("y", "yes") or (yes != "(yes)" and a in [w.strip().lower() for w in yes.split(",") if w.strip()])


def said_no(answer):
    """n or no, or a no in the program's language ("(no)" in its words, like "n, nein")."""
    a = str(answer).strip().lower()
    no = tr("(no)")
    return a in ("n", "no") or (no != "(no)" and a in [w.strip().lower() for w in no.split(",") if w.strip()])


def on_github_actions():
    """Running on GitHub Actions (saved with Save as GitHub Actions), where settings are the repository's secrets."""
    return os.environ.get("GITHUB_ACTIONS", "").lower() == "true"


WHERE_KEYS = (tr("as a repository secret (Settings → Secrets and variables → Actions)") if on_github_actions() else
              tr("in {path}", path=SETTINGS_PATH) if SETTINGS_PATH else tr("in {path}, next to this program", path=SETTINGS_FILE))

