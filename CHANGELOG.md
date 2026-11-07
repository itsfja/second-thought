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

A release that fixes a security problem lists it under a `### Security` heading, in this file and in the release's
notes on GitHub: that heading is what makes `--doctor` fail until the program is updated.

When you change `python/second_thought/`, add a line under **Unreleased**. When releasing, rename Unreleased to
the new version and set `RUNTIME_VERSION` in `python/second_thought/settings.py` to match. The unit tests check
that the two agree. Publishing the release on GitHub attaches `runtime.py` and `runtime.py.sha256` to it (the Release
workflow), which is what `--update-runtime` downloads; a release made before that can be given them with Run workflow.

## Unreleased

## 3.11.0 - 2026-11-07

### Fixed
- A one-word setting in `second-thought.ini` (`currency`, `save_log`, `budget`, `stream`, `resume`, `approve`, `language` and the like) ignores a note left after it (#338). Programs exported before now wrote notes on the same line, as in `; save_log = yes      write each run's log…`; with the `;` taken off, the note became part of the value and the program stopped. The page now writes each note on a line of its own, above its setting.

### Added
- Settings in layers (#340): `ST_` environment variables (such as `ST_EMAIL_ADDRESS` or `ST_CURRENCY`) for every program on the computer, then `second-thought.ini` in your home folder, then the program's own, each over the one before. Before, a program read only the first `second-thought.ini` it found, so one next to it hid the home folder's entirely, and shared settings like email and keys had to be copied into each. Ordinary environment variables still win, and the keychain still fills in missing keys. `--doctor` lists the files read and says where each key came from. `SECOND_THOUGHT_HOME_INI` names a different home file.
- Trust Wallet through its Agent Kit's MCP server (#320): name the server `trustwallet` (or start it with `twak serve`) and an agent can read your self-custody wallet: balances, portfolio, prices, history, swap quotes and token risk checks. Its tools carry no MCP annotations, so they're judged the safe way round, like Kraken's: only those known to look count as safe, and transfers, swaps, token approvals, payments and any tool a later twak adds count as money, so they always ask and never run unattended. The agent can't set twak's `autoApprove`; only the person's yes does. `create_automation` is never offered, because an automation trades later, out of sight. A gallery program, **Wallet health check**, emails what you hold and any risky tokens each Sunday, and only reads.

## 3.10.0 - 2026-11-06

### Security
- `--update-runtime` checks the release's signature when the runtime holds a signing key (#311): `UPDATE_SIGNING_KEY` in update.py carries the public half of an Ed25519 key whose private half is kept off GitHub (tools/sign_runtime.py signs each release's runtime.py, and the `.sig` is attached to the release). A runtime that isn't signed by that key is refused, so whoever can publish a release can't make a runtime this program will run. Until the first signed release, the key is empty and the SHA-256 check applies as before.
- Kraken's tools are judged the safe way round (#309): only the 118 that kraken-cli 0.5.1's catalog marks read-only or local (market data, account history, paper trading) run without the money question. Every other `kraken_` tool counts as money, so one added by a later kraken-cli asks and is refused unattended, instead of running like an ordinary tool. Before, money tools were recognised from a list of 34 names or an `acknowledged` input.
- In an agent, an MCP tool marked `destructiveHint` (MCP's mark for one that can delete or overwrite) asks first even under (no asking), and is refused when nobody is there (#309).

### Added
- GitHub through its own MCP server (#333): a recipe in the example ini and README for `MCP_GITHUB` (github-mcp-server with `--read-only` and a token that can only read, or GitHub's hosted server), and a gallery program, **Review a GitHub repository**, where an agent reads a repository's tree, README, main files and issues and writes an assessment with every point sourced. Merging, pushing, changing or deleting files and making, forking or deleting repositories always ask, even under (no asking), and never run unattended. `--doctor` says how many of each MCP server's tools can change things.
- `approve_by = telegram` in second-thought.ini (#305): a run with nobody at the keyboard, which before refused anything that had to ask first, asks on Telegram instead. The question goes to `TELEGRAM_CHAT_ID` with a fresh four-digit code; only a reply from that chat with that code, within five minutes, allows it, and the run log says who approved. Money moves and unlocks go through the same path, and it is never answered from a stopped run's journal.

### Fixed
- A Gemini call gives up after `RB_CALL_TIMEOUT` (300 seconds unless you change it), like every other service's, and is tried again (#329). google-genai waits forever by default, so a dropped connection could stall a program for good, with nothing on screen.
- A busy answer from Gemini (408, 429 or 5xx, such as 503 "This model is currently experiencing high demand") is tried twice more, after 5 and 15 seconds, as Claude's are, before backups or a 'try … times' block take over (#329). Before, the first one stopped the run.

## 3.9.2 - 2026-11-05

### Security
- `homeassistant.turn_on`, `turn_off` and `toggle` ask before reaching a lock, cover, valve or alarm wherever the target is named (#303). Before, only the entity was checked: a lock named in the data (`{"entity_id": "lock.front_door"}`), or a whole area, device, floor or label, went ahead without asking, also for an agent that a page or email had fooled. Those generic services now ask when the data names one of those devices, targets an area, device, floor or label, says `all`, or names nothing, since what they reach can't be seen. Everyday services (`light.turn_on` on an area) are unchanged.
- The agent's web tools refuse shared addresses too, such as the `100.64.0.0/10` range Tailscale gives the devices on your tailnet, and old IPv6 site-local ones (#304). Before, a page or email could steer an agent to a Home Assistant on your tailnet.
- An agent that can see private things asks before reading an address it wasn't given or didn't read, judged on whole addresses (#304). Before, any piece of an address it had read passed as one it had seen.
- A Word file is read up to 25 MB unpacked (#304), so a small `.docx` that unpacks to gigabytes can't stop a program that watches a folder.

### Changed
- MiniMax's quick tier is MiniMax M3.1 Flash (#281), at $0.15 / $0.60 per million tokens, instead of M2.7-highspeed, which is no longer on MiniMax's price list or its API's list of models. It can look at pictures. To keep the old model while MiniMax still serves it, set `MODEL_MINIMAX_QUICK = MiniMax-M2.7-highspeed`.

## 3.9.1 - 2026-11-04

### Changed
- Nothing in the runtime: exported programs behave exactly as with 3.9.0. This release puts the page's newest version on GitHub Pages, with Blockly 13 and its own keyboard navigation (#242).

## 3.9.0 - 2026-11-03

### Added
- Kraken (#262): the **Kraken tools** block gives an agent Kraken's own MCP server from kraken-cli, with market prices, your account and paper trading, or with live spot trading too. `KRAKEN_API_KEY` and `KRAKEN_API_SECRET` are new keys, and `MCP_KRAKEN` chooses its services. `--doctor` checks kraken-cli and the key, and fails on `--allow-dangerous`. A new gallery program, **Kraken week in review**, only reads.

### Security
- MCP tools that can move real money, Kraken's list in `SAFETY` and any tool that takes an `acknowledged` input, always ask, even with (no asking), and never run with nobody there to answer (a schedule, GitHub Actions, `--mcp`), whatever `approve` says. The agent can't set `acknowledged` itself: only a yes from you does, asked at the time, never replayed from a stopped run.

## 3.8.0 - 2026-11-03

### Added
- `--test` on GitHub Actions (#246): each failed case is an error on the run's page, with what was wrong, and the job's summary has a table of every case and what the tests cost. **Save as GitHub Actions** adds a test job when the program has test cases: it runs them when the program, its tests or the workflow are pushed, and from **Run workflow**, never on the schedule. `SETUP.md` says what a test run costs and how to make the scheduled runs wait while the tests fail.

## 3.7.0 - 2026-11-03

### Added
- Each account's plan, and the limits services report (#270). `PLAN_CLAUDE`, `PLAN_OPENAI`, `PLAN_GEMINI` and `PLAN_GROQ` in `second-thought.ini` name the plan, in the service's own words (Claude: start, build, scale; OpenAI: free, build, launch, grow; and so on). A misspelt one stops the program, listing the right names. Where the service publishes a monthly spend cap, this computer's spending (#269) is counted against it, shown at the end of a run, in a saved log and in `--doctor`, and a run stops before a call once it's reached. Claude's month is in UTC, as Claude's cap is. The rate limits Claude, OpenAI and Groq report with each reply are shown, labelled as theirs, in a saved log and `--doctor`, and at the end of a run when one is nearly used up. If Claude's match one plan, the end of a run suggests the `PLAN_` line, once on each computer. The plans and caps are dated, with sources, like the prices.

## 3.6.0 - 2026-11-03

### Added
- Prices for more models (#243), each from the service's own price page, dated: Mistral Small, Medium and Large; Qwen Flash, Plus and Max; Kimi K3; GLM-5.3 and GLM-5.3 Flash; MiniMax M3; GPT-OSS 120B on Groq; GPT-6 Astra; and Grok 4.7. Runs on them now show their cost, their models have a price band, and they can be held to a money budget or an allowance. OpenAI's, xAI's and Gemini's prices now come from their own pages too (the figures didn't change). Still without a price, because the service doesn't publish one: Kimi K2.6, Groq's Llama models and MiniMax M2.7.

## 3.5.0 - 2026-11-02

### Added
- Allowances for each key (#269): `quota_hourly`, `quota_daily`, `quota_weekly` and `quota_monthly` in `second-thought.ini`, in the program's currency, and `quota_<window>_<service>` for one service's own. Each key's spending at list prices is kept by the hour next to `memory.json`, as a hash of the key, for about 40 days, across every run of every program on this computer. A run stops before a model call once an allowance is used up and says when it resets; the end of a run, a saved log and `--doctor` say how much of each has gone. A model with no known price is refused under an allowance, and backups without room are left out. On GitHub Actions the tally starts afresh each run, and `--doctor` says so.

## 3.4.1 - 2026-11-02

### Fixed
- A program with `currency` set to `gbp`, `eur`, `jpy` or `cny` stopped as it started, and one whose **limit this run** block was in pounds, euros, yen or yuan stopped when it set the budget (#274). Both came in with 3.3.0: two names the runtime only found when run as part of the package, not inside an exported program. A program on 3.3.0 or 3.4.0 with a currency set needs the `currency` line taken out of `second-thought.ini` before `--update-runtime` will run; put it back afterwards.

## 3.4.0 - 2026-11-02

Not published as a release: 3.4.1 has its changes and the fix above.

### Added
- How expensive each model is (#264). The run log names each model with its band: free, budget, standard or premium, from its list price per million output tokens, or price unknown. Llama on this computer is free. `--doctor` lists each service's models with their bands. A router's models say who makes them, like *Gemma 4, by Google, through Hugging Face*.

## 3.3.0 - 2026-11-02

### Added
- Costs and money budgets in pounds, euros, yen or yuan (#263). `currency = gbp` (or `eur`, `jpy`, `cny`) in `second-thought.ini` shows the run's cost in that currency, like *about £0.02 at list prices*, and a saved log says which rate. Services charge in US dollars, so the program converts at the European Central Bank's rate of the day, fetched at most once a day and kept next to the program; offline it uses the last one kept, or a built-in one, so a money budget always has a rate. `exchange_rate` fixes the rate instead. The **limit this run** block takes pounds, euros, yen and yuan, and `budget_money` is a budget in the program's currency. `--doctor` shows the currency and its rate. Yen are whole; yuan show their code (0.40 CNY), so they aren't taken for yen.

## 3.2.0 - 2026-11-02

### Added
- A budget in money (#241). The **limit this run** block takes a unit, tokens or US dollars, and `budget_dollars = 0.50` in `second-thought.ini` caps every run. In dollars, a run stops before a model call once it has spent that much at the models' list prices. A model with no known price can't be counted, so the run stops and says so rather than running with no limit, and backups with no known price are left out. The end line and a saved log show the budget. Programs exported before keep their budgets in tokens.

## 3.1.0 - 2026-11-02

### Added
- `--doctor` (and **this program's setup check**) says when a newer runtime is out (#244): a NOTE for a newer version, a FAIL when its release notes have a Security section. It asks GitHub's list of releases; if that can't be reached, it's a NOTE. `update_check = no` in `second-thought.ini` turns it off.
- `--update-runtime` puts the newest runtime of the same major version into the program file in place (#244), so a fix reaches a program without exporting it again. It downloads the release's `runtime.py`, refuses it unless it matches the release's SHA-256 and says the version it should, and keeps the old file as `.bak`. The blocks, settings and the program's own code stay as they are, and the page still recognises the file on import. A program that acts asks to be allowed again, since the file changed. A newer major version isn't applied: it says to export the program again from the page.
- The runtime's first and last lines mark where it starts and ends in an exported program, so `--update-runtime` can find it.

## 3.0.1 - 2026-11-02

### Fixed
- Claude holds an agent's steps to their shape again while it writes (#250). The step's tool inputs were an open object, which Claude's structured replies refuse ("'additionalProperties' must be explicitly set to false"), so every step was checked after it arrived instead. A step's inputs now list every input of the agent's tools, none required, each tool's own inputs still checked when it's called. An agent given a very large set of tools may still be over Claude's limits for a reply shape; it then falls back to checking afterwards, as before.
- When Claude's reply has no text, the run says why (#251): a refusal says Claude declined to answer and isn't asked again three times; anything else names the reason Claude stopped. A reply shape Claude won't take is now remembered on its own, so Claude's other replies are still held to their shapes (#250). A run that stops says how many model calls and tokens it had used, and their cost, as the end of a finished run does.

## 3.0.0 - 2026-11-01

**Before you upgrade.** A major version, for one change: web requests are now listened for on this computer only.
If Home Assistant on another machine, IFTTT or your phone calls your program, add `WEBHOOK_HOST = 0.0.0.0` to its
`second-thought.ini` before re-exporting, or it stops receiving them. Nothing else needs doing: programs that act ask
once to be allowed again (the file changed), saying what's new.

**Known issues.** Claude refuses the agent step's reply shape, so agent steps are checked after they arrive rather
than while Claude writes (#250); agents still work. The *language-ladybird* gallery program stops after reading a
language file (#251).

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
