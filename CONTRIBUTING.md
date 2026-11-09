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

### Built-in connections, and MCP for the rest

Second Thought builds in its own connections to the services it ships with: Telegram, Discord, Slack, email, GitHub,
Home Assistant, Homey, MQTT, calendars, news feeds, web pages, folders and web requests (`connectors.py`), and every
model service (`providers.py`). Anything else comes through MCP (`mcp.py`), from servers a person adds themselves. No
MCP server comes built in. That's deliberate, for two reasons:

- **One file you own.** An exported program runs on Python's standard library and a model service's SDK. A built-in
  connection adds nothing to install; an MCP server is another program, kept somewhere else, that has to be installed
  and kept running.
- **The asking rules are exact.** For a built-in connection, `SAFETY` in `core.py` says precisely which actions always
  ask, like unlocking, opening, disarming and sending, and the tests check the page and the runtime agree. Through MCP,
  the program can only go by each server's own say-so about which of its tools change things.

So:

- **A service people already use with Second Thought, with an API that's stable and documented,** is built in, as
  above: its capabilities declared, what it does that acts in `SAFETY`, the same answers on the page and in Python, and
  tests with a stand-in for the service. It may not need a package beyond the standard library; if one helps, it's
  optional, and `--doctor` says how to install it (as `pypdf` is for PDFs).
- **A service whose API someone else maintains, or one with a good MCP server of its own,** comes through MCP. Where
  some of its tools spend money or change things that matter, they go in `SAFETY` too, by name, so they always ask
  (Kraken, #262).
- **Swapping a built-in connection for an MCP server** needs a reason that outweighs both points above, and it keeps the
  asking rules the built-in one had.

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

CI runs the unit tests (and the editor's) on Python 3.9 to 3.13 and Windows, and the end-to-end suite on Linux and Windows,
in five parts side by side on each (`page`, `python --share 1/3`, `2/3` and `3/3`, and `sources i18n gallery`), so a
failure names its part. Share 1 runs the Python checks that aren't per-program, shares 2 and 3 the exported programs
(`share_of` in tests/e2e/python_export.py balances them).

`ruff check` (after `pip install ruff`) looks for unused and undefined names and likely bugs, as CI does (`ruff.toml`).
`tests/unit/test_fuzz.py` feeds the parsers that read outside input thousands of broken inputs from a fixed seed;
`FUZZ_ROUNDS=50000 python -m unittest test_fuzz` in `tests/unit` tries harder.

If you have API keys, `python tools/smoke_test.py` checks the real services (it costs a few pence).

`python tools/smoke_test.py gallery` runs every community gallery program once against the real models, after
`tests/setup.sh`. Only the models are real: every connection goes to the stand-in services, and the folders the
programs look in are made-up ones, so nothing real is read or sent. Only the model keys in your settings are passed
on. A program that needs a service you have no key for is skipped. Each program stops at 20,000 tokens
(`--budget`), and no new one starts after 400,000 (`--total`). With Claude alone that caps the cost at a few pounds for the
whole gallery. The report goes to `smoke-gallery.md`. Run it before a release, or after changing a gallery program;
CI never runs it.

## Common changes

- **A translation, or a new language:** see [Languages](docs/using-the-page.md#languages) in the guide. Copy an existing
  `i18n/*.json`, translate the words (never the choice values, `%1` or `{name}` markers), and run `tools/sync.py`.
  The tests list anything missing. Scripts most computers lack need a `"font"`, plus a copy in `tests/setup.sh` and
  `FONTS` in `tests/e2e/common.py`; see the Linear B, Sanskrit, Akkadian, Sumerian, Hittite, Gothic, Middle Egyptian, Coptic and Syriac files for examples.
- **New words in a change:** every text shown through `tr()` needs a translation in each language. `python
  tools/i18n.py missing` lists what's missing. Write the translations into one file (`{"page": {"English": {"de": "…",
  …}}, "python": {…}}`) and `python tools/i18n.py add words.json` puts each in its language file. Give Mycenaean Greek,
  Akkadian, Sumerian, Hittite, Middle Egyptian, Coptic, Syriac and Gothic page words romanised, as their Python words are; the tool writes them in
  Linear B, cuneiform, hieroglyphs, Coptic letters, Estrangela and Gothic letters (a Coptic or Syriac word marked `^`, such as an
  English name, stays in Latin letters, and a Syriac proclitic on it keeps a hyphen: `d^Claude` becomes `ܕ-Claude`),
  leaving `{placeholders}`, names and file names alone. `python tools/i18n.py script akk "…"` shows a line first.
- **A gallery program:** see [`gallery/README.md`](gallery/README.md).
- **A model service:** one entry in `SERVICES` in `providers.py`; see
  [Development and tests](#development-and-tests).
- **Model names:** services retire models. `python tools/smoke_test.py models` lists, for each service you have a
  key for, the tiers whose model it no longer lists (it only reads the model list, so it's free). Update those
  names in `SERVICES`, and add a line to `CHANGELOG.md`. It also lists services whose `prices` were checked more than 90
  days ago: look them up at `prices_source` and update `prices` and `prices_checked`. A tier's model with no price
  just shows no cost, so add one only from the service's own price list, or a source you'd trust as much.
- **Exchange rates:** `RATES` in `providers.py` is the European Central Bank's rates on one day: the page's only
  rates, and exported programs' last resort offline. `python tools/smoke_test.py models` notes them when they're more
  than 30 days old; copy the day's rates from `RATES["source"]` and change the date.
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

## Repository layout

| Path | What it is |
|---|---|
| `second-thought.html` | The page itself: its HTML, with everything below embedded by `tools/sync.py`. |
| `web/editor.css`, `web/editor/` | The editor's styles, and its code in one file per area (see `web/editor/README.md`). `tools/sync.py` copies them into the page. |
| `python/second_thought/` | The runtime that comes with every exported program, as a package of ten modules (below). |
| `python/runtime.py` | The same runtime joined into one file, which every exported program gets a copy of. `tools/sync.py` builds it, so don't edit it by hand. |
| `prompts/convert-guide.txt` | The instructions Claude reads when it turns Python back into blocks. |
| `ha/sample-house.json` | The sample house the Home Assistant blocks use on the page. |
| `samples/connections.json` | The sample feeds, GitHub projects, Telegram messages, emails and calendar the page uses. |
| `i18n/` | The page's words in other languages, one file each. |
| `lang/` | The same, as scripts the page loads for the chosen language only. `tools/sync.py` makes them; publish them with the page. |
| `gallery/` | Programs people have shared, one file each. They appear on the page in the **Community** groups, by category. |
| `second-thought.example.ini` | Every setting a program understands, with a note on each. |
| `tools/sync.py` | Joins the runtime into one file, copies it and the other embedded parts into the page, and writes `lang/`, so they always match. |
| `tools/smoke_test.py` | Checks the real model services with your own keys. |
| `tools/pages.py` | Builds the copy of the page for GitHub Pages, which `.github/workflows/pages.yml` publishes with each release. |
| `tools/offline.py` | Builds `second-thought-offline.html`, the page as one file with its libraries and languages inside, which the Release workflow attaches to each release (#314). |
| `tools/record_demo.py` | Records `screenshots/demo.gif`, `editor.png` and `social-preview.png` (the picture GitHub shows when the repo is shared) from the page. |
| `tests/` | Unit tests (`tests/unit/`), and the end-to-end suite (`tests/e2e/`, one file per area, run by `tests/run_tests.py`). |
| `docs/ladybird-book.md` | The picture book. |
| `CHANGELOG.md` | What changed in each runtime version. |
| `CONTRIBUTING.md`, `SECURITY.md` | How to contribute; how to report a security problem, and what an exported program can and can't do. |

The runtime's modules, in the order `tools/sync.py` joins them:

| Module | What it does |
|---|---|
| `settings.py` | Reads `second-thought.ini` and the environment before anything else. |
| `providers.py` | Every model service, and how to call each one. |
| `core.py` | Limits, errors, and the sums and text handling that match the blocks exactly. |
| `connectors.py` | Web pages, news, calendars, Home Assistant, messages, MQTT and Homey. |
| `mcp.py` | Borrowing tools from MCP servers, for the agent. |
| `agent.py` | The agent block and its tools. |
| `spending.py` | What each key has spent on this computer, and its hourly, daily, weekly and monthly allowances. |
| `doctor.py` | `--doctor`: checks a program's setup without acting on anything. |
| `update.py` | Whether a newer runtime is out, and `--update-runtime`, which swaps it into the program file. |
| `runtime.py` | Everything else: memory, drafts, output, scripts and schedules. |

Each module starts with the imports it needs from the others. When `tools/sync.py` joins them, it leaves those lines out, because in one file every name is already there.

## Development and tests

[ROADMAP.md](ROADMAP.md) says what's next and why. [CONTRIBUTING.md](CONTRIBUTING.md) has the rules for a pull request, and [SECURITY.md](SECURITY.md) how to report a security problem and what limits an exported program.

If you change anything in `python/second_thought/`, `i18n/`, `gallery/`, `prompts/convert-guide.txt` or the sample files, run `python tools/sync.py` so `python/runtime.py` and the page pick up your changes. `python tools/sync.py --check` fails if either is out of date, and CI runs it.

**Unit tests** need nothing installed and take a few seconds:

```
python -m unittest discover -s tests/unit
```

**End-to-end tests** drive the page in a headless browser with stand-ins for Claude, then export every example to Python and run that too, against a stand-in Anthropic SDK. Nothing calls a real model, so they cost nothing.

```
bash tests/setup.sh          # once: Playwright, Chromium and local copies of the page's libraries
python tests/run_tests.py    # runs the unit tests too
```

At the end it says **All checks passed**, or lists what failed. To run only some areas, name them: `python tests/run_tests.py i18n gallery`. The areas are `sources`, `page`, `i18n`, `gallery` and `python` (which runs `page` too, for the programs it exports).

**Real services.** To check the real model services with your own keys:

```
python tools/smoke_test.py
```

It asks each service you have a key for a few short questions and reports what works: structured answers, streaming, continuing after a long answer is cut off, and the agent using a tool, plus which kind of structured answer every other service understands. It costs a few pence and prints the tokens used. Add a name to check one service, like `python tools/smoke_test.py claude`.

**Adding a model service.** Every service is one entry in `SERVICES`, near the top of `providers.py`: its name, its address, where its key goes, and its quick, default and complex models. The page reads the same list (`tools/sync.py` copies it in), so the new service appears in the model menus, the backups, the blocks, the exported settings file and the notes, all from that one entry. If the service speaks OpenAI's chat format, which most do, that's all it needs. Then add its settings to `second-thought.example.ini` (the tests say which), and a line to `CHANGELOG.md`.

**Versioning.** The runtime follows semantic versioning: the major number goes up when an exported program might behave differently, the minor for something new, and the patch for a fix. When you change the runtime, add a line to `CHANGELOG.md` under **Unreleased**.
