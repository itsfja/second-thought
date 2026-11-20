# Roadmap addendum: what's next

*Written by Claude at Francis's request on 15 November 2026, from main at `717a2a7`: runtime 3.13.0 plus the unreleased connections.*

[ROADMAP.md](ROADMAP.md) says the scheduled work is done, and that what's next starts with an idea and an issue of its own. This page is those ideas: features and design, in the order I'd take them, each sized to be one issue or a short run of them. They're judged the way the roadmap judges everything: does it strengthen *programs check their own work*, *actions ask first* and *one file you own*, or bring those three to more people? Each item now has an issue, linked beside it (#417–#462; 0.1 was #414); as they're done, they move to ROADMAP.md's Done.

## In short

1. **Mend main first.** One wrong block name in a gallery file stops the page from starting, and CI has been red since #412. Nothing published has it yet; the next republish or release would.
2. **Give the blocks one list.** A block is described by hand in half a dozen places, and two of them drifted in the last week: it's what broke main, and it's why *Describe a program* can't use 62 of the 202 blocks.
3. **Deepen the checking.** The review is the idea the project is named for, and it's still one verdict, from the model that wrote the draft. A verdict for each rule, exact checks done by code, a second model, and tests for the rules themselves.
4. **Look after programs that run alone.** A rehearsal, a record of what was done, a limit on how often they act, a message when one fails or goes quiet, and questions that reach your phone.
5. **Put plain English at the front, and give the canvas the screen.** A first screen with three ways in, one row of controls, and panels that open over the editor instead of pushing it down the page.
6. **Make a program a link.** All 80 gallery programs have one author. A link that opens a program, and a button that offers it to the gallery, are the shortest road to a second.

## What this is based on

I read the sources, the docs and the two outside reviews, and ran main's page in headless Chrome at 1440×900, 1280×720, 1024×768 and 390×844, with Blockly 13.4.0 from npm: once as built, and once with the one block name corrected. The page's own typefaces weren't reachable, so its fallbacks were used and the pixel counts are approximate. I didn't call a model. There were no open issues when this was written, so nothing here repeats one.

| What I found | Where it shows |
|---|---|
| **Main's page doesn't finish starting.** Run, Stop, Load, Browse examples, Import / export, Programs, Memory, Home Assistant, Backups, Step, Schedules and Build it do nothing. Blocks can be dragged and zoomed, and little else works. | `gallery/ai-spend-report.json` (from #413) has a block of type `rb_telegram_send`; the block is `rb_tg_send`. `fillExamples` in `web/editor/08-workspace.js` loads every gallery program at start-up to say what it can do, and the error stops everything after it in the editor's one function. |
| **CI on main has failed since #412**, and #413 was merged with ten end-to-end jobs failing. | A pull request that changes only Markdown skips the end-to-end jobs, and the checks that read the docs are among them. The `safe` ruleset asks for a pull request and a linear history, but not for CI. |
| ***Describe a program* and *Change this program* know 140 of the 202 blocks.** | `prompts/convert-guide.txt` is kept by hand. It names no block for Coinbase, Docker, MikroTik, UniFi, Proxmox, SABnzbd, Radarr and Sonarr, Unraid, NZBGeek, Pi-hole, Plex and Tautulli, Solax or Powerwall (59 blocks), nor the MCP, Kraken and Flightradar24 tool blocks. |
| **The canvas starts a long way down:** 30% of the way down a 1440×900 window, 44% at 1280×720 and 66% on a phone. On the GitHub Pages copy, with its banner, 39%, 55% and 83%. | Eleven buttons and four menus in the header (three rows at 1280 wide), then the example's description, the banner and the Describe box. |
| **Panels push the editor away.** Browse examples puts the canvas 19,000 pixels down the page (64,000 on a phone). Import / export at 1280×720 puts it below the bottom of the window. | The panels are sections above the editor. All 238 example cards are in one, with no search. |
| **The palette is long:** 37 categories, taller than its box at every size I tried. Fifteen of them are for a single service. | `web/editor/03-toolbox.js` |
| **The palette's phone rules do nothing.** It takes 171 pixels of a 358-pixel canvas. | `web/editor.css` styles `.blocklyToolboxDiv`, `.blocklyTreeRow` and `.blocklyTreeLabel`. Blockly 13 has nothing by those names: they're `.blocklyToolbox`, `.blocklyToolboxCategory` and `.blocklyToolboxCategoryLabel`. |
| **Twenty of the 35 block colours give their white labels less than 4.5:1 contrast.** Three are under 3:1, including the yellow hat every program starts with (2.3:1). | `HUES` in `web/editor/01-theme.js`. Labels are white, bold and 12 point, which is below the size where 3:1 is enough. |
| **A review is one yes or no for all the rules, from the model that wrote the draft.** | `review()` in `python/second_thought/runtime.py` asks for `{"approved", "problems"}`. The best draft is the one with the fewest problems, and a stuck loop is spotted by shared words (`same_problem` in `core.py`). |
| **No release has been signed.** | `UPDATE_SIGNING_KEY = ""` and `UPDATE_SIGNING_SPARE_KEY = ""` in `python/second_thought/update.py`; both empty. The runtime now holds two keys and accepts either (#429), so a key can be retired later without re-exporting every program. |
| **A program that runs alone has no limit on how often it acts, and can only be answered at a keyboard.** | `_allowed()` counts nothing; the *You* blocks read the terminal (`_input()`), and only approvals can go to Telegram. (What it did is now receipted: `.<program>.receipts.jsonl`, chained and private, and `--receipts` reads it — #431.) |
| **Adding one connection changed 113 files.** | Pi-hole (#401): 21 files by hand, 30 translations, 62 rebuilt. `connectors.py` was 2,112 lines at the 4 November review and is 3,655 now. |
| **Every gallery program has the same author.** | 80 of 80 say `itsfja`. Sharing one means editing JSON by hand, running `tools/sync.py` and opening a pull request. |
| **Most of the repository is translations, half of them a rebuilt copy.** | `i18n/*.json` is 10.2 MB, and `lang/*.js`, made from it, 9.8 MB, of 27.6 MB. |

None of this takes away from what's there: nearly 500 unit tests where there were 277 eleven days ago, one source for the safety rules, asking rules worked out for every connection, and docs that read as if someone meant them.

## Before the next release

Five small changes. The first is urgent. The others are why it won't happen again.

**0.1 Mend main ([#414](https://github.com/itsfja/second-thought/issues/414), fixed by [#415](https://github.com/itsfja/second-thought/pull/415)).** Four things were wrong. In `gallery/ai-spend-report.json` the Telegram block was called `rb_telegram_send`, and it's `rb_tg_send`: that's what stopped the page, and with the one word changed it starts cleanly, with all 238 examples. The usage tool's sentence on the page had been reworded after it was translated, so no language had it. ROADMAP.md said 79 community programs, and `gallery/` has 80. And its "last eleven languages" read to the docs check as a count of the page's languages, which is 30. The claude.ai page was last published on 10 November, and the GitHub Pages copy follows releases, so neither has the first of these: don't republish from main, or release the unreleased work, until the fix is merged.

**0.2 A program that won't load can't stop the page.** [#417](https://github.com/itsfja/second-thought/issues/417) Build the example cards when *Browse examples* first opens, not at start-up, and catch a program that fails: show its card as one that can't be loaded, with the reason, and carry on. Set up the toolbar's buttons before anything that reads data the editor didn't write. Start-up gets lighter as well. The hidden cards are 1,439 of the page's 2,524 elements, and loading the 80 shared programs to see what they can do is about a third of the half-second the page spends starting (in headless Chrome, on a fast machine).

**0.3 Catch it in seconds.** [#418](https://github.com/itsfja/second-thought/issues/418) Add a unit test that every block type in `gallery/*.json` is one the editor defines. A search of `web/editor/*.js` finds all 202 today and the browser agrees, so the mistake fails in the first job instead of the slowest.

**0.4 Make the checks count.** [#419](https://github.com/itsfja/second-thought/issues/419) Two gaps let these in. A pull request that changes only Markdown skips the end-to-end jobs, and the checks that read the Markdown (`docs_check` and `links_check`, in the `sources` area) are among them: that's how #412 was green as a pull request and failed on main. Move those two into the unit tests, which always run and take seconds. And #413 was merged with ten jobs failing, because the `safe` ruleset asks for a pull request and a linear history but not for CI: add required status checks to it. More than one AI helper opens pull requests now, and a required check is the one rule none of them can forget.

**0.5 The palette's phone rules.** [#420](https://github.com/itsfja/second-thought/issues/420) Rename the three selectors in the `max-width:600px` block of `web/editor.css` to Blockly 13's names, and have the end-to-end tests measure the palette at 390 pixels wide, so a Blockly upgrade can't quietly undo it again.

## Features

### A. One list of blocks

The project already does this for the safety rules (`SAFETY`, #219) and the model services (`SERVICES`): one source, copied everywhere by `tools/sync.py`, with a test that both sides agree. Blocks are the last big thing kept in step by hand.

**A1. The list.** [#421](https://github.com/itsfja/second-thought/issues/421) `tools/sync.py` writes a list of every block from its definition: type, words, slots, tooltip, category and capability. Unit tests then check, in seconds, that the gallery and the built-in examples use only blocks on it, and that the guide, every language and the capability table cover all of it.

**A2. The guide's block catalogue is built from it.** [#422](https://github.com/itsfja/second-thought/issues/422) Keep the hand-written parts of `prompts/convert-guide.txt` (the format, how to map code) and generate the catalogue. *Describe a program* gains the 62 blocks it doesn't know, and can't fall behind again. If the prompt grows too long, send the everyday blocks plus the services the description names.

**A3. A block reference.** [#423](https://github.com/itsfja/second-thought/issues/423) `docs/blocks.md`, generated from the same list: every block, what it does (its tooltip), what it lets a program do, and whether it asks. There are 202 blocks and no page that lists them.

### B. Checking, deeper

**B1. A verdict for each rule.** [#424](https://github.com/itsfja/second-thought/issues/424) The reviewer answers rule by rule: met or not, the problem, and the words in the draft that show it. The run log can then show the checking instead of describing it:

| Rule | Round 1 | Round 2 | Round 3 |
|---|---|---|---|
| accurate and specific | met | met | met |
| jargon explained | not met: "autolyse" is never explained | met | met |
| under 200 words | not met | not met | met |

The best draft becomes the one that meets the most rules. Today it's the one with the fewest problems, which favours a reviewer that lumps them together. A loop is stuck when the same rule fails twice running, with no need to compare wording. Test cases say which rule failed. Rules can be typed one to a line as well as with semicolons. This changes what a review asks a model, as #331 did, so it needs the same call: a minor version with a note, or kept for 4.0.0.

**B2. Count with code, judge with a model.** [#425](https://github.com/itsfja/second-thought/issues/425) "Under 200 words" is put to a model today, and models count badly. Add a few exact checks as blocks that sit in the review block beside the written rules, the way tools sit in an agent: *at most … words*, *mentions …*, *doesn't mention …*, *is valid JSON*, *has a link*. The runtime works them out, puts a failure in the problems with the real number ("231 words; the limit is 200"), and they cost nothing. It's the sums tool's rule, numbers are calculated and not guessed, applied to reviewing. Exact checks also make test cases repeatable.

**B3. A second opinion without building one.** [#426](https://github.com/itsfja/second-thought/issues/426) The review runs on whatever model wrote the draft, unless the program wraps it in *with model*. Add a choice on the review blocks, and a `reviewer` setting: the same model, another maker's model when a key for one is set, or a named one. The run log says who wrote and who checked. The 4 November review named same-family checking as the idea's real limit. This makes the answer one choice instead of a pattern to copy from an example. (Done — #426: the review blocks' "checked by" choice and the `reviewer` setting — same, another maker's model with a key, or a named tier; the run log names the writer and the checker, and says so when no other maker has a key instead of failing.)

**B4. Test the rules as well as the program.** [#427](https://github.com/itsfja/second-thought/issues/427) A test case today is a good run that must still pass. Add the opposite: a saved bad draft that must fail, and the rule it should break, so a rule that passes everything shows up. And `--test --times 3` runs each case several times and lists the rules that pass on some runs and fail on others. Those are the ones to rewrite. (Done — #427: a must-fail case saves a bad run with the rule it must break and passes only if the review fails it on that rule; `--test --times N` runs each case up to 10 times and reports the flaky rules, on the command line and in the GitHub Actions report.)

**B5. Rules from corrections.** [#428](https://github.com/itsfja/second-thought/issues/428) When someone says no at an *approve* step, or sends a result back, ask why in a sentence and offer it as a new rule: *Add "prices in pounds, not dollars" to the rules?* The people this is for arrive with half a checklist. This is how the other half gets written down. (Done — #428: a no at an *approve* step offers the reason as a rule; on the page it is added to the review blocks' rules, in Python it is saved in `.<program>.rules.json` beside the program and checked by every review, with the line to add on the page printed.)

### C. Programs that run alone

**C1. Sign the releases, after deciding how a key is changed.** [#429](https://github.com/itsfja/second-thought/issues/429) The signature check from #311 is built and has never been switched on. Before the first signed release, let the runtime hold two keys, the working one and a spare kept somewhere else, and accept either; say in SECURITY.md how one is retired. A single key, once it's inside every exported program, can't be changed from outside: lose it, and each program has to be exported again to get another. Then set the keys, sign the next release, and have `--doctor` say that this runtime checks signatures.

**C2. A rehearsal.** [#430](https://github.com/itsfja/second-thought/issues/430) `--rehearse`, or `rehearse = yes`: the program runs for real, models and reading included, but nothing is sent, switched, saved or spent, and the log says what would have happened. The test runner already works this way (`testing`, in `_allowed()` and the agent), so it's mostly a flag and its words. It's how to try a new schedule for a week before trusting it.

**C3. Receipts.** [#431](https://github.com/itsfja/second-thought/issues/431) One line for each thing a program does to the world, kept next to it and readable only by you: when, what (the sentence the approval question uses), which block or agent step, and how it was allowed.

```
2026-11-15 07:02  sent a Telegram message: Bins tonight: green and food.   allowed: no asking, approved at the first run
2026-11-15 22:31  light.turn_off on light.kitchen (agent, step 3)          allowed: yes 4821 on Telegram, by Alex
```

Each line carries a fingerprint of the one before, so a missing or altered line shows, and `--receipts` prints the week. Both outside reviews asked for this. It's the paper trail for the people the asking rules protect most: the ones with locks and money.

**C4. A limit on actions.** [#432](https://github.com/itsfja/second-thought/issues/432) *Limit this run to …* stops a run that spends too much. Nothing stops one that sends too much: a script that sends a Telegram message sends it every time it runs, and nothing counts. Add allowances like the spending ones, by kind (messages, the home, money) and by hour and day, with defaults switched on. A program that reaches one stops acting, says so once, and carries on reading. (Done — #432: `allow_messages_hourly`/`_daily`, `allow_ha_hourly`/`_daily` and `allow_money_hourly`/`_daily`, on by default (10/50 messages, 30/200 home actions, 1/5 money moves an hour/day; 0 turns one off), counted across runs on this computer from the receipts each action writes, kept next to `memory.json`. A run that reaches one stops acting, says so once with the kind, the amount and when it resets, and carries on reading; `--doctor` shows each kind's count. In `second-thought.example.ini` and the docs; on GitHub Actions the counts start afresh each run.)

**C5. Say when it fails, or goes quiet.** [#433](https://github.com/itsfja/second-thought/issues/433) `notify_on_failure` sends one message when a scheduled run stops with an error, with the reason. `heartbeat_url` is fetched after each scheduled run that finishes, for Healthchecks.io or an Uptime Kuma push monitor, so silence gets noticed too. Today a schedule that breaks at three in the morning tells the terminal. (Done — #433: `notify_on_failure = telegram` sends one message, with the reason, when a scheduled run — including a `--run-schedule N` one, like GitHub Actions' — stops with an error; `heartbeat_url` is fetched after each scheduled run that finishes, and a fetch that fails is only a note. Both in `second-thought.example.ini`, the docs and `--doctor`; tests and rehearsals never send or fetch anything.)

**C6. Questions that reach you.** [#434](https://github.com/itsfja/second-thought/issues/434) `approve_by = telegram` carries approvals to a phone. The *You* blocks (ask me, approve, let me choose, pause) still read the keyboard, so a scheduled program can't ask anything. Let them use the same channel when nobody's there, with a time limit and the answer to assume when it runs out, both set on the block. Then put other channels behind the same small set of jobs (ask, wait, who answered): [ntfy](https://docs.ntfy.sh/publish/#action-buttons), whose notifications carry buttons, and [Home Assistant's actionable notifications](https://companion.home-assistant.io/docs/notifications/actionable-notifications), whose taps arrive as events the runtime already listens for. Check that ntfy's iOS app shows the buttons before relying on them. (Done — #434: the You blocks use `approve_by`'s channel when nobody's at the keyboard, with a time limit and a default answer set on the block; Telegram first, behind one small interface — ask, wait, who answered — that ntfy and Home Assistant actionable notifications can follow; channel answers are never journaled.)

**C7. A weekly account.** [#435](https://github.com/itsfja/second-thought/issues/435) `--report`: how many runs; how many passed review first time, after revising, or as a best effort; what was done and what was refused; what it cost; what failed. It reads the receipts and the spending record, and a scheduled program can send it. A slide in quality after a model changes shows here first. `--status` says the same in one line, for a home server with a dozen programs. (Done — #435: `--report` reads the saved logs (runs, review outcomes, refusals, rules by round), the receipts and the spending record for the last 7 days, and `--status` prints the same in one line; both exit 1 on a broken receipts chain. Documented in docs/running.md.)

### D. Sharing and reach

**D1. A link that is a program.** [#436](https://github.com/itsfja/second-thought/issues/436) On the GitHub Pages copy, `#p=` followed by the block file, deflated and written in base64. *Import / export* gets **Copy link**. Opening one shows what the program is and what it can do before anything loads, exactly as an import does. All 80 gallery programs come out under 1,800 characters this way, half of them under 1,000, and the page already unpacks deflate to read zip files. (Done — #436: **Copy link** in Import / export packs the program into `#p=` + deflate-raw + base64url; opening a link offers the program's name, block count and what it can do, and loads it only on **Load**; a broken or too-new link says so and loads nothing. All 80 gallery programs come out under 1,800 characters, 42 under 1,000.)

**D2. Offer it to the gallery from the page.** [#437](https://github.com/itsfja/second-thought/issues/437) **Share…** asks for the title, category, description, tip and author, shows the card as it will look, with what the program can do worked out as now, and opens a *Share a program* issue form with the fields and the link filled in ([issue forms take values from the address](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-githubs-form-schema)). A workflow turns an accepted issue into the pull request. Nobody edits JSON or installs git. (Done — #437: **Share…** on the page fills in a *Share a program* issue form (`.github/ISSUE_TEMPLATE/share-a-program.yml`) with the fields and the #p= link, showing the card as it will look; the `gallery-share` workflow turns a `gallery-accepted` issue into the PR with `gallery/<name>.json` (tools/gallery_from_issue.py) and the rebuilt page.)

**D3. The gallery as web pages.** [#438](https://github.com/itsfja/second-thought/issues/438) `tools/pages.py` writes a page for each program next to the editor: what it does, what it can do, its blocks drawn, **Open in the editor** (D1) and, once E1 exists, **Download Python**. A search for "Pi-hole daily report Telegram" can then find one, and a forum answer can link to it. The docs can go on the same site.

**D4. Export for Docker.** [#439](https://github.com/itsfja/second-thought/issues/439) **Save for Docker (.zip)**: the program, a `Dockerfile` that runs it as an ordinary user with its folder as a volume, a `compose.yaml` with `restart: unless-stopped` and the keys in an env file, and `SETUP.md`. Most of the newest connections (Unraid, Proxmox, Docker, the download and media servers) are for people who run everything in containers, and the installers in the zip are for a computer's own start-up.

**D5. Somewhere to talk.** [#440](https://github.com/itsfja/second-thought/issues/440) Turn on Discussions (show and tell, questions, ideas) and link to it from the README and the page, so issues stay for work.

### E. One file you own, further

**E1. Export without the page.** [#441](https://github.com/itsfja/second-thought/issues/441) `node tools/export.cjs program.json` writes the Python the page would, from the editor's own code, with the real `blockly` package in place of the stand-in that `tests/editor/page.cjs` uses. Every gallery program can then be a download on each release. A program can be exported again for a new major runtime without opening anything. Most export checks no longer need a browser. And the page becomes one of two ways to get a program, which is the third idea applied to the project itself.

**E2. Inputs with names.** [#442](https://github.com/itsfja/second-thought/issues/442) A program takes one thing in, its *message value*. Let it declare a few named inputs (`town`, `date`), filled in from a small form on the page, `--town Rye` on the command line, and a proper schema when it's served as an MCP tool. Later than the rest of this page, but it's what lets other people run a program without editing its blocks.

## Design

Each new word on the page is thirty translations, so these designs reuse the words that are there wherever they can.

### F. The page

**F1. A first screen.** [#443](https://github.com/itsfja/second-thought/issues/443) On a first visit, three ways in: **Describe it** (the plain-English box, large, with three sentences to click), **Start from an example** (six chosen ones, not 238), **Open a file**. Then the editor, with the result on the canvas. Anyone who has a program lands in the editor, as now. This is the successor's "plain-English authoring with blocks as the form you inspect", done in the page that exists. (Done — #443: a browser with nothing kept sees the first screen — Describe it (large box, three sentences to click), Start from an example (six chosen), Open a file — each path lands in the editor with the program on the canvas; a browser with a program kept lands in the editor as before.)

**F2. One row of controls.** [#444](https://github.com/itsfja/second-thought/issues/444)

```
+------------------------------------------------------------------------------------------------------+
| Second Thought  [Program v] [Data v]  [ Describe a change...    ]  Step  Stop  [ Run ]  [Settings v] |
| This program can: send Telegram messages (asks first), search the web                                |
+---------------------+----------------------------------------------+---------------------------------+
| Events              | when it's 18:00 on Fridays                   | Run log                         |
| Control             |   set task to [ the weekend's drying ]       |                                 |
| ...                 |   write a first draft                        | Review         round 1   2   3  |
| Draft               |   review the draft against                   | names a day        yes yes yes  |
| Review              |       [ names a day and a time ]             | no jargon           no yes yes  |
| Agent               |       [ no jargon              ]             | at most 60 words    71  64  58  |
| You                 |       ( at most 60 words       )             |                                 |
| Connections         |     revise to fix the problems               | Result                          |
|   Telegram          |   send Telegram message  (!)                 | Dry from two till five on       |
|   Home Assistant    |   finish and show the result                 | Saturday. Hang it out then.     |
|   + add a service   |                                              |                                 |
| Output              |                                              | [Copy as text]  [Save as test]  |
+---------------------+----------------------------------------------+---------------------------------+
```

**Program** holds new, examples, my programs, import, export and share. **Settings** holds the model and its backups, currency, language, theme, schedules and keyboard help. Memory and the sample house go under **Data**. The Describe box becomes a field in the row that opens when it's used. In the sketch, square brackets are written rules, round ones an exact check (B2), and `(!)` marks a block that acts (F6). Aim: at 1280×720 the canvas starts within 120 pixels of the top (it's 317 now), and Run is always on the first row, in every language. (Done — #444: one row with Program, Data, the Describe field, Step, Stop, Run and Settings as disclosure menus; the canvas starts at 82 px at 1280×720 in the longest language, with the off-claude.ai banner showing.)

**F3. Panels open over the editor.** [#445](https://github.com/itsfja/second-thought/issues/445) Examples, import and export, programs, memory, the sample house, backups and keyboard help become drawers over the canvas, with the focus kept inside and Esc to close, so the program stays where it was. Examples gets a search box, and filters from what the page already works out: only uses models, reads, sends, controls, money; which services it needs; built in or shared. (Done — #445: all seven panels are drawers with a focus trap and Esc to close, and the gallery has a search box plus filters by capability, service and built in or shared.)

**F4. A palette that shows what you use.** [#446](https://github.com/itsfja/second-thought/issues/446) One **Connections** category holding the services you've turned on, from a list in Settings. Loading a program that uses a service turns it on, and *Find a block* and *Describe a program* still reach everything. Few people have more than two or three of the fifteen. (Done — #446: the fifteen one-service categories carry a `service` id and nest inside **Connections** only when turned on in **Settings → Connections** (a checkbox list in a new drawer, kept in the browser); loading any program turns on the services its blocks use; the full palette still feeds block search and Describe a program. The 2 new page words are translated in all 34 languages.)

**F5. Colours that say what a block is for, and can be read.** [#447](https://github.com/itsfja/second-thought/issues/447) The guide says blocks are colour-coded by job. With 35 colours they no longer are: give every connection one family, and keep a colour for each job. Choose each so its white label reaches 4.5:1, or use dark labels on the light ones, and add a test that works the contrast out from `HUES`, so a new colour can't slip under. (Done — #447: all 16 connection hues are the one `conn` pink #C2185B (5.9:1), and the 13 job colours that failed were darkened in place to 4.7:1 or better (the start hat's yellow 2.3:1 became amber #936D12); tests/editor/hues.test.cjs computes the WCAG contrast of every HUES entry against white and asserts ≥4.5:1, that each service category's hue is the conn colour, and that job colours stay distinct. The guide's colour list is updated; the screenshots are remade at release, G4.)

**F6. Show what can act, before Run.** [#448](https://github.com/itsfja/second-thought/issues/448) A line under the controls, always there, worked out from the blocks as the import panel does: *This program can: send Telegram messages (asks first) · read your calendar.* And a small mark on every block that sends, changes or spends, a shape and not a colour, with a different one for the no-asking forms. It's the second idea, visible at a glance. (Done — #448: a `role="status"` line in the subbar under the controls lists what the program can do, updated on every block change, and each acting block carries a triangle (asks first) or diamond (no-asking `_free` agent kinds) mark in its corner.)

**F7. A run log that shows the second thought.** [#449](https://github.com/itsfja/second-thought/issues/449) For a review loop: a strip of the rounds (three problems, then one, then approved), the table from B1, and what each revision changed, with additions and removals marked and tied to the problem they answer. Results shown as formatted text (headings, lists, bold, links, tables) with *Copy as text* beside them; today a model's `**bold**` shows as asterisks. This is also the picture for the top of the README.

**F8. On a phone, run and answer.** [#450](https://github.com/itsfja/second-thought/issues/450) At phone width: the program as a short outline that can't be edited, a large Run, and the run log with its questions and approvals. **Edit blocks** opens the full editor for anyone who wants it. Buttons at least 44 pixels high: nineteen in the header and the zoom group aren't.

### G. The design, written down

**G1. `docs/design.md`.** [#451](https://github.com/itsfja/second-thought/issues/451) The tokens in `web/editor.css` (colours, the three typefaces, corners, the pill states), the layout rules above, and the voice: short sentences, plain words, British spelling, what a thing does before how it works, with an example of each. The words are the most consistent part of the design, and nothing says so. With more than one AI helper writing texts for thirty languages, something should.

**G2. A light and dark switch.** [#452](https://github.com/itsfja/second-thought/issues/452) The page follows the computer's setting and already honours `data-theme`. There's no control for it.

**G3. Typefaces that come with the page.** [#453](https://github.com/itsfja/second-thought/issues/453) The three typefaces load from Google Fonts, so the offline page and a blocked network fall back to the system's. Serve them from the site on the GitHub Pages copy, and put them inside the offline page.

**G4. Pictures that match the page.** [#454](https://github.com/itsfja/second-thought/issues/454) `screenshots/demo.gif` was recorded at runtime 2.2.0, and the terminal picture shows the review on a cheaper model than the draft, which a program only does if it's told to. Add `tools/record_demo.py` and `tools/record_docs.py` to the release steps in `CLAUDE.md` and `MISTRAL.md`.

## Underneath

### H. Keeping it cheap to change

**H1. A connection in one place.** [#455](https://github.com/itsfja/second-thought/issues/455) `connections/<name>/` holding its reads and actions, its blocks and page sample, its lines for `SAFETY`, `CAPABILITIES`, the settings and the example ini, its section of the docs, its stand-in service and its gallery program; `tools/sync.py` puts `connectors.py`, the editor's files and `docs/connections.md` together from them. It turns 21 hand edits into one folder, and it's what would let someone else add a connection. Until then, hold new built-in connections to the rule CONTRIBUTING already has, a service people already use with Second Thought, and send the rest through MCP. (The pattern is in place — #455's first pull request: `connections/<name>/` with its parts, and `tools/sync.py` splicing them into the shared files at `sync:connections-*` markers, with Powerwall moved as the example; each remaining connection follows in its own pull request.)

**H2. Rebuilt files out of review.** [#456](https://github.com/itsfja/second-thought/issues/456) Mark `lang/*.js`, `python/runtime.py` and `docs/words/*.md` as `linguist-generated` in `.gitattributes`, so GitHub folds them away in a pull request; the merge rules are already there. Later, build `lang/` in the Pages, Release and publish steps and stop committing it. That's 9.8 MB and thirty files off every change to the words. (Step 1 done — #456: `lang/*.js`, `python/runtime.py` and `docs/words/*.md` are marked `linguist-generated` (and `docs/words/*.md` joined the `merge=generated` set) in `.gitattributes`, so pull requests fold them away; step 2, building `lang/` in the Pages, Release and publish steps and git-ignoring it, is still open.)

**H3. Tests that fit the change.** [#457](https://github.com/itsfja/second-thought/issues/457) The full suite takes ten minutes side by side and grows with every example. Let a pull request run what it touches (a gallery file: that program's load, run and export; words only: the translation checks), and run everything on main, each night and before a release. Quick answers are what make a required check (0.4) painless.

**H4. One page of rules for every helper.** [#458](https://github.com/itsfja/second-thought/issues/458) `MISTRAL.md` mirrors `CLAUDE.md` by hand. Move what's shared to `AGENTS.md` (how Francis works, the rules, the tests, what done means) and leave each tool's file with its own sandbox's quirks. Add a pull-request template with the things that have been missed: the tests passed, `tools/sync.py --check`, a changelog line, the block list and the guide, new pictures if the page changed.

### I. Languages

**I1. Five living languages, each with a reader.** [#459](https://github.com/itsfja/second-thought/issues/459) The page speaks thirty languages besides English, and none of them is Arabic, Hindi, Korean, Russian or Turkish. Right-to-left already works, and Devanagari is already here. For reach these come before the next ancient one. Each needs a named speaker to read it through, because no test can.

**I2. Say how sure the words are.** [#460](https://github.com/itsfja/second-thought/issues/460) Each language's file has more than 2,300 entries. In the **Blocks** menu and `docs/words/`, mark each language *read by a speaker* or *made by a model: corrections welcome*, with a link to the language form. The ancient ones stay a delight, and the living ones become something to rely on.

**I3. The next ancient ones.** [#461](https://github.com/itsfja/second-thought/issues/461) Cheapest first: another script for a language that's already here, such as runes for Old Norse and Old English, or Glagolitic for Church Slavonic. Then languages with a script in Unicode and plenty of surviving text: Ge'ez, Classical Armenian, Old Irish. Then the small ones, for the pleasure of it: Ugaritic, Old Persian, Phoenician. The language form's question, how much of the vocabulary is attested, should set the order.

**I4. Finish the words #413 added.** [#462](https://github.com/itsfja/second-thought/issues/462) Ten languages (Akkadian, Sumerian, Hittite, Middle Egyptian, Coptic, Syriac, Gothic, Mycenaean Greek, Pali and Classical Nahuatl) have English where the other twenty have a translation, for 13 texts about spending: the tests check that a text is there, not that it was translated. Translate them; put back the fuller sentence about what the page can't count, this time with its translations; and add a check that lists texts left the same as the English, with a short list of the names that should be.

## Not now

- **More built-in connections**, before H1, unless someone is using the service with Second Thought today.
- **Accounts, a hosted runner or a marketplace.** Each trades *one file you own* for convenience.
- **Programs that update themselves.** Updating stays a person's choice. C1 makes the choice safer.
- **Building on a phone, or two people editing at once.**
- **Reviewers that review reviewers.** B3 and B4 are the answer to a weak review, not more layers.
- **A rewrite.** See the last section.

## Suggested order

Sizes: **S** is one pull request, **M** two to four, **L** a structural pass with a plan of its own. The last column is the label I'd give the issues, from the ones the repository has: `priority: 1` do first, `priority: 2` do next, `priority: 3` when there's time, `priority: 4` someday, and `priority:8`, ad hoc, as the language issues have.

| | Items | Why here | Size | Label |
|---|---|---|---|---|
| 1 | **0.1–0.5** Mend main, and keep it mended | Blocks every release and republish | S each | `priority: 1` |
| 2 | **A1–A2** One list of blocks; the guide built from it | Gives *Describe a program* its 62 blocks, and stops a repeat of 0.1 | M | `priority: 2` |
| 3 | **C1** Signed releases, with a spare key | Built and never switched on; the key design can't change after the first signed release | S | `priority: 2` |
| 4 | **F2–F3** One row of controls; panels over the editor | The most visible gain for the least risk | M | `priority: 2` |
| 5 | **B1–B2** A verdict for each rule; exact checks | The first idea, deepened | M | `priority: 2` |
| 6 | **C2–C3** A rehearsal; receipts | Trust for programs with nobody watching | S, M | `priority: 2` |
| 7 | **C5–C6** Failure and silence; questions that reach you | Makes a schedule something to depend on | S, M | `priority: 3` |
| 8 | **F1, F6** A first screen; show what can act | The way in for people who don't program | M | `priority: 3` |
| 9 | **D1–D2** A program as a link; offer it to the gallery | The first outside author | M | `priority: 3` |
| 10 | **H1–H2** A connection in one place; rebuilt files out of review | Before the next connection | L, S | `priority: 3` |
| 11 | **C4, C7** A limit on actions; the weekly account | They build on the receipts | S, M | `priority: 3` |
| 12 | **B3–B5** A second opinion; tests for the rules; rules from corrections | They build on B1 | M | `priority: 3` |
| 13 | **F4–F5, F7–F8, G1–G4** Palette, colours, run log, phone, the design written down | They build on F2 and B1 | M | `priority: 4` |
| 14 | **E1, D3, A3** Export without the page; gallery pages; the block reference | D3 needs D1 and E1 | L, M, S | `priority: 4` |
| 15 | **D4–D5, H3–H4, E2** Docker; Discussions; tests that fit; one page of rules; named inputs | Small, and can go in any gap | S each; E2 is M | `priority: 4` |
| 16 | **I1–I4** Languages | Alongside, as now; I4 is small and can go first | M each; I4 is S | `priority:8` |

## How we'll know

Each of these can be a test, which is how this project has kept its promises so far.

- The page starts, and Run works, with any file in `gallery/`, however broken.
- A pull request that changes only Markdown still runs the checks that read it, and nothing merges while CI is red.
- Every block is in the list, the guide, the reference and every language.
- At 1280×720 the canvas starts within 120 pixels of the top, and Run is on the first row, in the language with the longest words.
- A program can be described, run and exported without opening the palette.
- A review loop's run log shows each rule's verdict for each round.
- After a week of scheduled runs, `--receipts` accounts for every message that was sent.
- Every block's label reaches 4.5:1 against its colour.
- One gallery program whose author isn't `itsfja`.

## Towards the successor

ROADMAP.md ends by saying what a successor should do: plain-English authoring with blocks as the form you inspect, an editor with a codebase of its own, and a versioned program format from the start. The format has since been written down (#391). F1 puts plain English first in the page that exists. A1 and E1 make the blocks and the exporter things that stand apart from the page, and H1 does the same for connections. If those land, most of what a successor was for will have happened here, without the cost of starting again.
