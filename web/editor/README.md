# The editor's code

The page's code, one file per area. `tools/sync.py` joins them in the order of their names into the page's
`<script id="editor">`, so they all run inside one function: a name declared in one file is seen by every file, and a
file can use what a later one declares once the page has loaded (from an event, say), but not while it's being set up.
Never edit the copy in `second-thought.html`; edit these, then run `python tools/sync.py`.

A function that needs no page (no blocks on screen, no clicks) can be tested in Node without a browser: add it to
`window.__editorUnits` at the end of `23-schedules.js` and test it in `tests/editor/`.

To add an area, add a file whose number puts it where it needs to run. To move code between files, move it whole: a
file needn't end where a function does, but it reads better if it does.

| File | What it holds |
|---|---|
| `00-start.js` | The editor's opening: shared limits and small helpers ($, STORE_KEY, MAX_*). Every file below runs inside the same function, so names declared in one are seen by the rest. |
| `01-theme.js` | Colours and Blockly's theme. Every colour in `HUES` passes 4.5:1 with a white label (tests/editor/hues.test.cjs), and all connections share the one `conn` pink (#447). |
| `02-blocks.js` | Every block's definition, and the long-text field. |
| `03-toolbox.js` | The block palette (toolbox) and its categories; the one-service categories carry a `service` id and only show when turned on in Settings (#446). |
| `04-examples.js` | Building example programs: the helpers the example library uses. |
| `connections/ha/05-home-assistant.js` | Home Assistant on the page, kept as a whole editor file in its connection's folder (`connections/<name>/NN-name.js` joins this list at its name's place): the sample house, its blocks' behaviour and the safety rules (SAFETY, copied in by tools/sync.py). |
| `06-example-library.js` | The example library, Home Assistant examples included. |
| `07-format.js` | Block file format versions and their migrations. |
| `08-workspace.js` | The Blockly workspace: injecting it, saving and loading, the autosave. |
| `09-import-export.js` | Import and export: block files, backup models, Save as GitHub Actions. |
| `10-python-export.js` | Turning blocks into Python, and the exported settings and launchers. |
| `11-zip.js` | Making and reading zip files. |
| `12-claude.js` | Asking Claude to convert code or build a program from a description, and Claude access. |
| `13-run-log.js` | The run log's steps. |
| `14-memory.js` | Memory that survives between runs. |
| `15-library.js` | Saved programs and the prompt library. |
| `16-pictures-files.js` | Pictures, files and error messages. |
| `17-agent.js` | The agent and its built-in tools. |
| `18-connections.js` | Connections on the page: sample feeds, GitHub, Telegram, email, calendar, Homey, MQTT, Coinbase, MikroTik, UniFi, Proxmox, Docker and the rest. |
| `19-interpreter.js` | Running blocks: structured replies, asking you, values and statements, results. |
| `20-test-cases.js` | Test cases: Save as test case and Run tests. |
| `21-log-watch-step.js` | Saving the log, the watch panel, step mode and running one script. |
| `22-search.js` | Finding a block. |
| `23-gallery-share.js` | Offering a program to the community gallery: the Share… form, its card preview, and the prefilled issue form's address (#437). |
| `23-first-screen.js` | The first screen for a browser with nothing kept: Describe it, six examples, open a file (#443). |
| `23-acts.js` | What the program can act on before Run: the line under the controls and the mark on acting blocks (#448). |
| `23-connections.js` | The Connections list in Settings: the checkboxes that turn a service's palette category on and off (#446). |
| `23-review-log.js` | The run log's second thought (#449): the review loop's rounds strip and each revision's diff, and results rendered as sanitised Markdown. |
| `23-phone.js` | On a phone (#450): the program as a read-only outline with a large Run; "Edit blocks" opens the full editor. |
| `23-schedules.js` | Schedules and listeners on the page, and the editor's closing line. |
