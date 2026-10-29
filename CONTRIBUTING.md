# Contributing to Second Thought

Thanks for helping. This page covers how the pieces fit together, the few rules that keep them in step, and how to
check your change before opening a pull request.

## How the pieces fit

Second Thought is two things built from one set of sources:

- **The page**, `second-thought.html`: the block editor, published with the `lang/` folder beside it.
- **The runtime**, which every exported Python program carries a copy of.

```
python/second_thought/*.py ──┐
                             ├─ tools/sync.py ─→ python/runtime.py   (the runtime, joined into one file)
i18n/*.json, gallery/*.json, │                 ├→ second-thought.html (with the runtime and the rest embedded)
prompts/, samples/, ha/ ─────┘                 └→ lang/*.js           (one per language, loaded by the page)
```

The runtime is written as a package, `python/second_thought/`, so each module can be read and tested on its own.
`tools/sync.py` joins the modules into `python/runtime.py` and copies it, along with the model services, the
capability list, the list of languages, the gallery, the conversion prompt and the sample data, into the page. Each
language's words go into `lang/<language>.js` instead, which the page loads for the chosen language only, so adding a
language doesn't make the page bigger for everyone. The editor's own HTML, CSS and JavaScript are edited in place in
`second-thought.html`.

**Publishing.** The page is published as a claude.ai artifact, with every file in `lang/` as a supporting file at the
same path (`lang/fr.js` and so on). Publish them together: if a language's file is missing, the page still works, in
English, with a note saying the language couldn't be loaded.

## The rules

1. **Never edit `python/runtime.py`, `lang/`, or the embedded `<script>` blocks in `second-thought.html`, by hand.** Edit the
   source files, then run:

   ```
   python tools/sync.py
   ```

   `python tools/sync.py --check` fails if either is out of date, and CI runs it on every pull request. Commit the
   rebuilt files with your change.

2. **Changes to the runtime go in `CHANGELOG.md`.** If your change touches `python/second_thought/`, add a line
   under **Unreleased**, saying what an exported program now does differently and why it matters. The changelog
   explains when a change is major, minor or a patch; mark a change that will need a major version, as the
   `WEBHOOK_HOST` entry does. `RUNTIME_VERSION` is only changed when releasing.

3. **Every block declares what it lets a program do.** If you add a block or an agent tool that reads, sends or
   changes something, add it to `CAPABILITIES` in `core.py` (or classify it as doing nothing to declare). The tests
   fail if a block is missing. This is what the approval prompt and the gallery cards are built from.

4. **One change per pull request**, on its own branch, linked to its issue (`Closes #123`).

## Checking your change

Unit tests need nothing installed and take a few seconds:

```
python -m unittest discover -s tests/unit
```

The end-to-end suite drives the page in a headless browser and runs every example's exported Python against stand-in
services. Nothing calls a real model.

```
bash tests/setup.sh          # once
python tests/run_tests.py    # unit tests too; ends with "All checks passed"
```

CI runs the unit tests on Python 3.9 to 3.13 and Windows, and the end-to-end suite on Linux and Windows.

If you have API keys, `python tools/smoke_test.py` checks the real services (it costs a few pence).

## Common changes

- **A translation, or a new language:** see [Languages](README.md#languages) in the README. Copy an existing
  `i18n/*.json`, translate the words (never the choice values, `%1` or `{name}` markers), and run `tools/sync.py`.
  The tests list anything missing. Scripts most computers lack need a `"font"`, plus a copy in `tests/setup.sh` and
  `FONTS` in `tests/run_tests.py`; see the Linear B, Sanskrit and Akkadian files for examples.
- **A gallery program:** see [`gallery/README.md`](gallery/README.md).
- **A model service:** one entry in `SERVICES` in `providers.py`; see
  [Development and tests](README.md#development-and-tests).
- **A new example:** examples live in the page. Add its translations to each language's `examples` section (the
  tests check every language has every example).
- **The screenshots:** after a visible change to the page, `python tools/record_demo.py` remakes
  `screenshots/demo.gif`, `editor.png` and `social-preview.png`.

## Reporting problems

Use the issue templates. For a bug in an exported program, include the output of `python my-program.py --version`
and `--doctor` (with your keys removed). For anything security-related, see [SECURITY.md](SECURITY.md) instead.
