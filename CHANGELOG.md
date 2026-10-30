# Changelog

What changed in the Python runtime that comes with every exported program. Run an exported program with
`--version` to see which runtime it has. To give a program a newer runtime, import it on the Second Thought page
and export it again: the blocks are saved inside the file, so nothing is lost.

Versions follow [semantic versioning](https://semver.org):

- **Major** (2.0.0): an exported program might behave differently, or need a change to keep working, such as a
  renamed setting, a block that gives a different answer, or a removed model.
- **Minor** (1.1.0): something new that existing programs don't notice, such as a new block, setting, service or
  agent tool.
- **Patch** (1.0.1): a fix that makes a program do what it was always meant to.

When you change `python/second_thought/`, add a line under **Unreleased**. When releasing, rename Unreleased to
the new version and set `RUNTIME_VERSION` in `python/second_thought/settings.py` to match. The unit tests check
that the two agree.

## Unreleased

### Changed
- Found by running a program on GitHub Actions for real (#226). Telegram messages show a model's Markdown as Telegram's own formatting, so `**bold**` arrives bold (Slack gets its own formatting too; Discord already read Markdown). A Claude key made for a whole Console organisation, not one workspace, works with the new `ANTHROPIC_WORKSPACE_ID` setting, and a run refused for that, for no credit or for a wrong key now says what to do in plain words. On GitHub Actions a run that stops puts its reason on the run's page (an error annotation), says to fix it and use Run workflow rather than to run it again to carry on, and says settings are repository secrets rather than lines in `second-thought.ini`. Save as GitHub Actions uses `actions/checkout@v5` and `actions/setup-python@v6`, and offers an optional `ANTHROPIC_WORKSPACE_ID` secret.
- When a program that can act changes and asks to be allowed again, it says what it can do now that it couldn't when you last allowed it, and what it no longer does, before the full list (#225). If nothing changed there, it says so. `--doctor` says the same.
- Pages and feeds the agent reads through a proxy go to the address that was checked (#220). Before, the proxy looked the name up again, so a name that changed its answer could reach your own network. Redirects are followed and checked the same way, and the certificate is still checked against the name.
- `--doctor` says more when a service no longer lists a model the program uses (#190): that it may have been retired, and the `MODEL_<TIER>` line for `second-thought.ini` that switches to a model the service does list, with the nearest one of the same kind as an example.
- Agents ask in more places, even with the no-asking tools (#188). Every lock, cover and valve action but locking, closing and stopping asks (toggling or setting a position could open them), as does `homeassistant.turn_on`, `turn_off` or `toggle` aimed at one. When an agent chooses them, Home Assistant scripts, scenes, automations and buttons, Homey flows, and MQTT messages saying unlock, open or disarm ask too. An agent with private tools asks before reading a page or feed address that wasn't in its goal or anything it read. An unattended program relying on its agent doing these without asking now says no to them instead.
- Web requests are now listened for on this computer only (127.0.0.1), not on every network it's on (#106). If Home Assistant on another machine, IFTTT or your phone calls the program, add `WEBHOOK_HOST = 0.0.0.0` to its `second-thought.ini`. `--doctor` checks the same address, and the startup line shows `http://127.0.0.1:…` when only this computer can call it. This needs a major version at release, since such a program stops receiving requests until the line is added.

### Added
- The run's last line says what it cost at the models' list prices, from the exact token counts, like *about $0.03 at list prices* (#224), and a saved log has a Cost line. It says nothing if any call used a model whose price isn't known (or was changed with `MODEL_<TIER>`). Prices are in `SERVICES` for Claude, Gemini, OpenAI, DeepSeek and Grok 4.3, each dated with a source.
- Keys can come from your computer's keychain (#123), if the `keyring` package is installed: `python -m keyring set second-thought ANTHROPIC_API_KEY`. The environment and `second-thought.ini` still win. `--doctor` lists where each key came from, and says if the keychain couldn't be read. `keychain = no` turns it off.
- `--mcp` (#194) serves the program as an MCP tool over stdio, named after the program: its input becomes message value, each call runs the 'when Run is clicked' scripts, and the result comes back. Questions fail the call and asking actions are refused, as on a schedule; a program that can act serves only once allowed to without asking. `--doctor` names the tool.
- `--test` (#193) runs the program's test cases from `<program>.tests.json` (made on the page with Save as test case): each replays the saved answers, with the models live, and a strict reviewer checks the result against its criteria. Nothing acts in a test, and memory is a copy. PASS or FAIL per case, and exit code 1 if any failed.
- `--run-schedule N` (#191) runs scheduled script N once, if it's due: a 'when it's' script within an hour after its time, on its days, so a scheduler that starts it late, or at both the winter and summer times, runs it once. `--now` runs it whatever the time. The page's new **Save as GitHub Actions** uses it.
- Two GitHub listeners (#145): **when a new issue is opened in** a project (pull requests don't count), and **when a release is published in** a project, with the release before it as `previous_tag`. Like the pull-request listener, they start from what's new after the program starts, and only need read access.
- **files in folder … matching …** (#146): a folder's files as records (name, path, modified, size), newest first, without reading them. A program that uses it, or the folder listener, now lists "look at the files in a folder, and watch it for new ones" before its first run.
- The folder listener gives a picture as `picture` (#146), for PNG, JPEG, WebP and GIF files up to 20 MB, so 'what arrived: picture' goes straight into the picture blocks.
- **this program's setup check** (#147): the same report as `--doctor`, as text, from inside a running program, for programs that email their own health. It runs the checks on a fresh runtime, so the run's draft and counts are untouched.
- Five more GitHub tools for the agent (#144). **GitHub: projects and pull requests** can now list a project's branches (`list_branches`) and commits (`list_commits`), and read a file or folder (`read_github_file`). **GitHub: comment, open and label issues** can open issues (`open_issue`) and add labels the project already has (`add_labels`); like commenting, each asks first. Before its first run, a program with that tool now lists "comment on GitHub, and open and label issues"; like any re-exported program, it asks again.
- Exported programs print in German when exported from the page in German (#74).
- Exported programs print in Dutch when exported from the page in Dutch (#75).
- Exported programs print in Italian when exported from the page in Italian (#76).
- Exported programs print in Portuguese when exported from the page in Portuguese (#77).
- Exported programs print in Simplified Chinese when exported from the page in Chinese (#78).
- Exported programs print in Japanese when exported from the page in Japanese (#79).
- Exported programs print in Greek when exported from the page in Greek (#84).
- Blocks, page and exported programs in Latin, with Latin words for Blockly's own blocks and menus too, since Blockly has none (#85).
- Blocks, page and exported programs in Old English (Ænglisc), with its own words for Blockly's blocks and menus (#92).
- Blocks, page and exported programs in Middle English (Englisch), the English of Chaucer, with its own words for Blockly's blocks and menus (#96).
- Mycenaean Greek in Linear B (#95): the page shows Linear B signs, loading the Noto Sans Linear B font for this language only (a language file can now name a `font`), and exported programs print the transcription (ko-no-so).
- Blocks, page and exported programs in Koine Greek (Κοινή), in polytonic spelling, with its own words for Blockly's blocks and menus (#87).
- Blocks, page and exported programs in Old Norse (Norrœnt mál), in normalised Old Icelandic spelling, with its own words for Blockly's blocks and menus (#91).
- Blocks, page and exported programs in Hebrew (עברית) (#88). A language file can now say `"dir": "rtl"`: the page, Blockly's workspace, toolbox and flyout are then mirrored right to left, while code, file names and the status line stay left to right.
- Blocks, page and exported programs in Sanskrit (संस्कृतम्), in Devanagari with the Noto Sans Devanagari font, and its own words for Blockly's blocks and menus (#102). A language's font is now loaded for whichever script it names, not just Linear B.
- Blocks, page and exported programs in Akkadian (#103): the page in cuneiform, with the Noto Sans Cuneiform font, spelled syllable by syllable from Old Babylonian words; exported programs print the transliteration. A language's font now comes first in the page's font lists, so its script never shows as boxes in bold text.
- Blocks, page and exported programs in Jewish Babylonian Aramaic (ארמית), right to left like Hebrew (#89). Blockly has no Aramaic translation, so its own blocks and menus come from the file's `blocklyMsg`.

## 2.2.0 - 2026-10-11

### Changed
- A question at the keyboard takes yes and no in the program's language, from its words (`(yes)` and `(no)`, like
  `o, oui` or `j, ja`), as well as y and n. This used to be built in for Spanish only, so each new language now needs
  only its words. Added for French (#73).

## 2.1.0 - 2026-10-11

### Added
- Exported programs can print in Spanish: the run log, questions at the keyboard (answer s or y for yes), errors,
  the first-run approval and `--doctor`. A program exported while the page shows Spanish carries the Spanish words
  (`EXPORT_LANGUAGE` and `EXPORT_WORDS`, above the runtime) and speaks Spanish; `language = en` in
  `second-thought.ini` switches it back to English. A program exported in English is unchanged. `--doctor` keeps its
  `ok`, `FAIL` and `NOTE` markers as they are, for scripts that read them. The words live under `python` in
  `i18n/es.json`, and a test fails if the runtime prints a text that isn't there (#71).

## 2.0.0 - 2026-10-10

**Upgrading:** programs keep their old runtime until you import them on the page and export them again. After that,
a program that can act on the world (send messages, control devices, publish MQTT, accept web requests, comment on
GitHub, use MCP tools) lists what it can do and asks once before its first run. Run each scheduled one once by hand
and answer y, or put `approve = no` in `second-thought.ini` on a computer with nobody at it. Then try
`python my-program.py --doctor` to check everything it needs is in place.

### Added
- `--doctor` checks an exported program's setup without spending anything or acting on anything (#54). It checks only
  what the program uses (from `CAN`): Python, the settings file, packages, each model service's key (with its free list
  of models, noting a model it doesn't list, such as a Llama model that hasn't been pulled), and each connection by
  reading from it: Home Assistant, Homey, MQTT, Telegram, Discord, Slack, email (reading, and signing in to send without
  sending), GitHub, calendars, feeds, the web-request port, MCP servers' tool lists, memory and the outputs folder. It
  also says whether the first-run approval is recorded. Exit code 0 when nothing fails. A program exported before `CAN`
  is checked for whatever is set up. `CAN` now also names the program's MCP servers.
- The agent's memory tools include `search_memory`, which finds saved notes by what's in their names and contents,
  best first, so a long-running agent with many notes can find the right one without knowing its name (#46). It ranks
  with BM25 over names (counted twice) and contents, with a light trim of English endings and partial matches for word
  starts, and nothing extra to install. The page ranks notes exactly the same way, and a test checks that.
- The agent can use the tools of any MCP server (#43): a **tools from MCP server** block, with the server set up as
  `MCP_<NAME>` in `second-thought.ini`, either the command that starts it or its https:// address (plus
  `MCP_<NAME>_TOKEN`). It speaks the current MCP (2026-07-28, every request saying its version, found with
  `server/discover`) and falls back to the earlier `initialize` handshake (2025-11-25 back to 2024-11-05), over stdio
  or Streamable HTTP, with nothing extra to install. It asks before tools not marked read-only unless told otherwise,
  and tool calls are journaled so a resumed run doesn't repeat them. Programs using it list "use the tools of the MCP
  servers you set up" and ask before their first run. `mcp_timeout` sets how long a call may take.
- Exported programs list what they can do beyond asking their models (send email, control Home Assistant, publish
  MQTT, read your calendars, and so on), in their notes and in `CAN`. The list is worked out from the blocks; every
  block and agent tool is classified, and a test fails if a new one isn't. Importing a program on the page says what
  it can do, the things that act first (#44).
- A program that can act on the world lists those things and asks before its first run. The yes is kept in
  `.<program>.approved` until the program file changes. `approve = no` in `second-thought.ini` skips the question.

### Fixed
- Turning text into a list (the list blocks, and a model's list replies) took any leading digits for list numbering,
  so "10 green bottles" became "green bottles" and "2024 plan" became "plan"; "-5 °C" lost its sign too. Now only
  real markers come off: "- " or "* ", "•", and a number followed by "." or ")" ("1.", "3)", "(2)"), but not a
  number like 1.5. The page does the same, and a test checks the two agree.
- On Python 3.9, two questions at the keyboard at once (or two Telegram fetches) crashed with "attached to a
  different loop": the runtime's locks were made before the program's event loop started. They're now made when first
  needed.

### Changed
- **Needs one step after re-exporting:** a scheduled program that can act won't start until someone has run it once
  by hand and said yes (or set `approve = no`). Under the rules above that makes the next release 2.0.0.
- Every model service is now one entry in `SERVICES` (in `python/second_thought/providers.py`). `MODELS`,
  `PROVIDERS` and the other tables are made from it, and the page builds its model menus, backups, block choices,
  exported settings and notes from the same list. Exported programs behave exactly as before; adding a service that
  speaks OpenAI's chat format now needs only its entry (#42).

## 1.0.0 - 2026-10-10

The first numbered runtime. Programs exported before this have the same runtime, without the number.

### Added
- `RUNTIME_VERSION`, which says which runtime an exported program has; `--version` prints it, and saved run logs
  record it.
- The export header says which runtime it was made with. Importing a program exported with a different runtime says
  so, and how to upgrade.
- Unit tests for the runtime's parts (`tests/unit`), which need nothing installed.

### Changed
- The runtime's source is now the `python/second_thought` package. `tools/sync.py` joins it into
  `python/runtime.py`, so exported programs are still one file with nothing extra to install (#41).
