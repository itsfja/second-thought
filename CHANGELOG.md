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
