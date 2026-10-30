# Contributing to Second Thought

Thanks for helping. [ROADMAP.md](ROADMAP.md) says what's planned and in what order; issues labelled `roadmap` are a good place to start. This page covers how the pieces fit together, the few rules that keep them in step, and how to
check your change before opening a pull request.

## How the pieces fit

Second Thought is two things built from one set of sources:

- **The page**, `second-thought.html`: the block editor, published with the `lang/` folder beside it.
- **The runtime**, which every exported Python program carries a copy of.

```
python/second_thought/*.py ──┐
web/editor.css, editor/*.js, ├─ tools/sync.py ─→ python/runtime.py   (the runtime, joined into one file)
i18n/*.json, gallery/*.json, │                 ├→ second-thought.html (with the editor, the runtime and the rest embedded)
prompts/, samples/, ha/ ─────┘                 └→ lang/*.js           (one per language, loaded by the page)
```

The runtime is written as a package, `python/second_thought/`, so each module can be read and tested on its own.
`tools/sync.py` joins the modules into `python/runtime.py` and copies it, along with the model services, the
capability list, the list of languages, the gallery, the conversion prompt and the sample data, into the page. Each
language's words go into `lang/<language>.js` instead, which the page loads for the chosen language only, so adding a
language doesn't make the page bigger for everyone. The editor's styles live in `web/editor.css` and its code in
`web/editor/`, one file per area joined in name order (its README says what each holds), which `tools/sync.py` copies into the page too, so they can be read and reviewed on their own. Only its
HTML (the toolbar, panels and log) is edited in `second-thought.html` itself.

**Publishing.** The page is published as a claude.ai artifact, with every file in `lang/` as a supporting file at the
same path (`lang/fr.js` and so on). Publish them together: if a language's file is missing, the page still works, in
English, with a note saying the language couldn't be loaded.

## The rules

1. **Never edit `python/runtime.py`, `lang/`, or the embedded `<style>` and `<script>` blocks in `second-thought.html`, by hand.** Edit the
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


**Merging translation files.** Pull requests that add words usually add them at the end of the same sections of
`i18n/*.json`, which git calls a conflict. Run this once in your clone, and git merges those files key by key instead,
keeping the words both sides added:

```
python tools/merge_i18n.py --install
```

Only a word changed differently on both sides is still a conflict. Files `tools/sync.py` makes (`python/runtime.py`,
`lang/*.js`) keep your side, so after a merge or rebase run `python tools/sync.py` and commit what it rebuilds.
GitHub's web editor doesn't use merge drivers, so resolve those conflicts locally.

## Checking your change

Unit tests need nothing installed and take a few seconds:

```
python -m unittest discover -s tests/unit
```

The editor's own functions (sums, clock times, schedules and their GitHub Actions cron lines, block formats, page
words) have unit tests too, run in Node without a browser, in about a second. They need Node 22 or later, and
`tools/sync.py` run first:

```
node --test "tests/editor/*.test.cjs"
```

`tests/editor/page.cjs` runs the editor's code with stand-ins for the page; the functions it can test are listed in
`window.__editorUnits`, at the end of `web/editor/23-schedules.js`. Where the runtime has the same function, the cases
are in `tests/parity/`, which the Python tests read as well, so both sides stay alike.

The end-to-end suite drives the page in a headless browser and runs every example's exported Python against stand-in
services. Nothing calls a real model.

```
bash tests/setup.sh          # once
python tests/run_tests.py    # unit tests too; ends with "All checks passed"
```

CI runs the unit tests (and the editor's) on Python 3.9 to 3.13 and Windows, and the end-to-end suite on Linux and Windows.

If you have API keys, `python tools/smoke_test.py` checks the real services (it costs a few pence).

`python tools/smoke_test.py gallery` runs every community gallery program once against the real models, after
`tests/setup.sh`. Only the models are real: every connection goes to the stand-in services, and the folders the
programs look in are made-up ones, so nothing real is read or sent. Only the model keys in your settings are passed
on. A program that needs a service you have no key for is skipped. Each program stops at 20,000 tokens
(`--budget`), and no new one starts after 400,000 (`--total`). With Claude alone that caps the cost at a few pounds for the
whole gallery. The report goes to `smoke-gallery.md`. Run it before a release, or after changing a gallery program;
CI never runs it.

## Common changes

- **A translation, or a new language:** see [Languages](README.md#languages) in the README. Copy an existing
  `i18n/*.json`, translate the words (never the choice values, `%1` or `{name}` markers), and run `tools/sync.py`.
  The tests list anything missing. Scripts most computers lack need a `"font"`, plus a copy in `tests/setup.sh` and
  `FONTS` in `tests/run_tests.py`; see the Linear B, Sanskrit and Akkadian files for examples.
- **New words in a change:** every text shown through `tr()` needs a translation in each language. `python
  tools/i18n.py missing` lists what's missing. Write the translations into one file (`{"page": {"English": {"de": "…",
  …}}, "python": {…}}`) and `python tools/i18n.py add words.json` puts each in its language file. Give Mycenaean Greek
  and Akkadian page words romanised, as their Python words are; the tool writes them in Linear B and cuneiform,
  leaving `{placeholders}`, names and file names alone. `python tools/i18n.py script akk "…"` shows a line first.
- **A gallery program:** see [`gallery/README.md`](gallery/README.md).
- **A model service:** one entry in `SERVICES` in `providers.py`; see
  [Development and tests](README.md#development-and-tests).
- **Model names:** services retire models. `python tools/smoke_test.py models` lists, for each service you have a
  key for, the tiers whose model it no longer lists (it only reads the model list, so it's free). Update those
  names in `SERVICES`, and add a line to `CHANGELOG.md`.
- **What always asks** (unlocking, opening and disarming, the agent tools that ask, what a fooled agent can't do
  unasked): edit `SAFETY` in `python/second_thought/core.py`, then run `tools/sync.py`, which copies it into the page.
  Both sides read that one list, and `tests/e2e/safety.py` checks they give the same answers.
- **Changing a block's shape** (renaming a block, a field or an input, or changing what a field holds): saved programs,
  gallery files and exported Python all keep the old shape. Bump `FORMAT_VERSION` in the page and add
  `MIGRATIONS[old version]`, a function that turns an old program into a new one. Every way a program loads runs it.
- **A new example:** examples live in the page. Add its translations to each language's `examples` section (the
  tests check every language has every example).
- **The screenshots:** after a visible change to the page, `python tools/record_demo.py` remakes
  `screenshots/demo.gif`, `editor.png` and `social-preview.png`.

## Reporting problems

Use the issue templates. For a bug in an exported program, include the output of `python my-program.py --version`
and `--doctor` (with your keys removed). For anything security-related, see [SECURITY.md](SECURITY.md) instead.
