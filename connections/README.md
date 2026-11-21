# Connections

One folder per connection — a service a program can talk to — holding everything of its own. `python tools/sync.py`
then puts the shared files together from these folders (#455): each part file below is spliced into a marked region
of its target (a `# sync:connections-<key>-begin` / `-end` pair on its own lines, in the target's own comment
style; the region between them is rewritten from `connections/*/` in folder-name order), `sample.json` is merged
into `samples/connections.json` under the folder's name, and `fake.py`, `test.py` and `gallery/*.json` are copied to
`tests/fake_<name>.py`, `tests/unit/test_<name>.py` and `gallery/<file>.json`. The shared files stay valid and
committed — the same model as the tagged blocks in `second-thought.html` — and `python tools/sync.py --check` (run
by the tests) fails if they are out of date.

## The parts of `connections/<name>/`

| part | goes into |
| --- | --- |
| `runtime.py` | `python/second_thought/connectors.py`, region `runtime`: its reads and actions (the `Connections` methods) |
| `imports.py` | `connectors.py`, region `imports`: names it imports from `.core` |
| `safety.py` | `python/second_thought/core.py`, region `safety`: its `SAFETY` lines |
| `fns.py` | `core.py`, region `fns`: its helper functions (e.g. `powerwall_allowed`) |
| `capabilities-act.py` / `capabilities-read.py` | `core.py`, regions `capabilities-act` / `capabilities-read`: its acting / reading `CAPABILITIES` line |
| `known.py` / `secret.py` | `python/second_thought/settings.py`, regions `known` / `secret`: its setting names |
| `check.py` | `python/second_thought/doctor.py`, region `check`: its `--doctor` check |
| `check-helper.py` | `python/second_thought/doctor.py`, region `check-helper`: its `--doctor` helper method, when the check is its own method |
| `settingsmap.py` | `doctor.py`, region `settingsmap`: its label in `--doctor`'s settings table |
| `example.ini` | `second-thought.example.ini`, region `ini`: its section |
| `hues.js` / `styles.js` | `web/editor/01-theme.js`, regions `hues` / `styles`: its colour and block style |
| `caps.js` | `web/editor/02-blocks.js`, region `caps`: its `CAP_BLOCKS` lines |
| `defs.js` | `web/editor/02-blocks.js`, region `defs`: its block definitions |
| `toolbox.js` | `web/editor/03-toolbox.js`, region `toolbox`: its palette category |
| `need.js` | `web/editor/10-python-export.js`, region `need`: its line in `settingsFor` |
| `ini.js` | `10-python-export.js`, region `ini`: its `[section]` in the exported ini |
| `pyread.js` / `pyact.js` | `10-python-export.js`, regions `pyread` / `pyact`: its read / action blocks' Python |
| `page.js` | `web/editor/18-connections.js`, region `page`: its page sample and page-side functions |
| `iread.js` / `iact.js` | `web/editor/19-interpreter.js`, regions `iread` / `iact`: its read / action cases |
| `docs.md` | `docs/connections.md`, region `docs`: its section |
| `sample.json` | merged into `samples/connections.json` under the folder's name |
| `gallery/*.json` | copied to `gallery/<file>.json` |
| `fake.py` | copied to `tests/fake_<name>.py` (its stand-in service) |
| `test.py` | copied to `tests/unit/test_<name>.py` |

## Adding a connection

Make the folder, copy the parts from the current homes of the same lines (the regions marked `sync:connections-*`
in the shared files show exactly what to move), delete those lines, and run `python tools/sync.py`. No hand edits
anywhere else: the i18n keys are the English words themselves, so they stay, and `tools/blocks.json`,
`python/runtime.py`, `second-thought.html` and the embedded samples rebuild on their own. If the folder is removed
later, delete its copied files (`tests/fake_<name>.py`, `tests/unit/test_<name>.py`, its `gallery/*.json`, its key
in `samples/connections.json`) by hand — sync does not prune.

`docs/connections.md`'s table of contents at the top is still a hand-written list of the sections; add the new
connection's line there.

`powerwall/`, `pihole/`, `solax/`, `sabnzbd/`, `nzbgeek/`, `unifi/`, `mikrotik/`, `proxmox/`, `docker/` and `coinbase/` are the patterns: moved first (#455), each with its reference counts unchanged in every shared file.
