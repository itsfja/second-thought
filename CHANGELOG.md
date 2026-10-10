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
