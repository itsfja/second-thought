# Roadmap

Where Second Thought is going, and in what order. Each item is an issue; this page says why it's where it is.

## What Second Thought is for

Second Thought is for people who have a checklist, a rubric or house rules, but nobody to automate them. Three ideas make that work, and everything here is judged by whether it strengthens them:

1. **Programs check their own work** against criteria a person wrote down.
2. **Actions ask first.** A program says what it can do before its first run, and asks before each thing it sends or changes.
3. **One file you own.** Any program exports as a single Python file that runs with nothing else installed.

The project has grown wide: over 150 examples, 74 community programs, 30 languages, 15 model services. The next gains come from **trust and reach**, not more blocks. Items are ordered by expected benefit against cost; the labels `priority: 1` to `priority: 4` say the same.

## Done

Trust: the prompt-injection tests ([#188](https://github.com/itsfja/second-thought/issues/188)) and a real-model run of the gallery ([#189](https://github.com/itsfja/second-thought/issues/189)). Reach: plain-English authoring ([#192](https://github.com/itsfja/second-thought/issues/192)), GitHub Actions export ([#191](https://github.com/itsfja/second-thought/issues/191)), retired-model warnings ([#190](https://github.com/itsfja/second-thought/issues/190)) and eight gallery packs ([#196](https://github.com/itsfja/second-thought/issues/196)–[#203](https://github.com/itsfja/second-thought/issues/203)). Depth: test cases for programs ([#193](https://github.com/itsfja/second-thought/issues/193)), a versioned block format ([#195](https://github.com/itsfja/second-thought/issues/195)), programs as MCP tools ([#194](https://github.com/itsfja/second-thought/issues/194)), keys in the keychain ([#123](https://github.com/itsfja/second-thought/issues/123)) and the editor's code in its own files ([#122](https://github.com/itsfja/second-thought/issues/122)).

Safety and cost of change, released in 3.0.0: one source for the safety rules ([#219](https://github.com/itsfja/second-thought/issues/219)), the DNS-rebinding gap closed ([#220](https://github.com/itsfja/second-thought/issues/220)), translation files merged key by key ([#217](https://github.com/itsfja/second-thought/issues/217)) and a translation tool ([#218](https://github.com/itsfja/second-thought/issues/218)). The editor split into files by area ([#221](https://github.com/itsfja/second-thought/issues/221)), with unit tests ([#222](https://github.com/itsfja/second-thought/issues/222)) and keyboard and screen-reader use ([#223](https://github.com/itsfja/second-thought/issues/223)). Polish: a run's cost in money ([#224](https://github.com/itsfja/second-thought/issues/224)), saying what's new when a program asks again ([#225](https://github.com/itsfja/second-thought/issues/225)), and a real run on GitHub Actions ([#226](https://github.com/itsfja/second-thought/issues/226)).

Fixes reach people, released in 3.1.0: exported programs say when their runtime is out of date and update it in place ([#244](https://github.com/itsfja/second-thought/issues/244)).

What a run costs, in terms people use, released in 3.2.0 and 3.3.0: a budget in money ([#241](https://github.com/itsfja/second-thought/issues/241)), and costs and budgets in pounds, euros, yen or yuan ([#263](https://github.com/itsfja/second-thought/issues/263)).

What models and keys cost, released in 3.4.1 to 3.7.0: how expensive each model is and who makes it ([#264](https://github.com/itsfja/second-thought/issues/264)), prices for the rest of the services ([#243](https://github.com/itsfja/second-thought/issues/243)), each key's spending with hourly, daily, weekly and monthly allowances ([#269](https://github.com/itsfja/second-thought/issues/269)), and each account's plan with the limits services report ([#270](https://github.com/itsfja/second-thought/issues/270)). Also fixed: programs with a currency set stopped at start ([#274](https://github.com/itsfja/second-thought/issues/274)).

GitHub as a home, released in 3.8.0: a program's test cases on GitHub Actions ([#246](https://github.com/itsfja/second-thought/issues/246)), and the page on GitHub Pages as a second front door ([#245](https://github.com/itsfja/second-thought/issues/245)).

Reach and trust, released in 3.9.0 and 3.9.1: the Pages copy runs programs with your own API key ([#293](https://github.com/itsfja/second-thought/issues/293)), Kraken through its own MCP server with tools that move money always asking ([#262](https://github.com/itsfja/second-thought/issues/262)), and Blockly 13 with its own keyboard navigation ([#242](https://github.com/itsfja/second-thought/issues/242)). Then MiniMax's quick tier moved to M3.1 Flash, which has a price ([#281](https://github.com/itsfja/second-thought/issues/281)).

Two languages and two security fixes, released in 3.9.2: Middle Egyptian ([#136](https://github.com/itsfja/second-thought/issues/136)) and Sahidic Coptic ([#131](https://github.com/itsfja/second-thought/issues/131)) on the page; Home Assistant's generic services ask whatever their target ([#303](https://github.com/itsfja/second-thought/issues/303)); and the agent refuses shared addresses such as Tailscale's, compares whole addresses, and reads Word files up to 25 MB ([#304](https://github.com/itsfja/second-thought/issues/304)). Both came from outside reviews of the code.

Released in 3.10.0, mostly from the outside reviews: unknown Kraken tools count as money and destructive MCP tools always ask ([#309](https://github.com/itsfja/second-thought/issues/309)); releases can be signed with a key kept off GitHub ([#311](https://github.com/itsfja/second-thought/issues/311)); unattended runs ask on Telegram instead of refusing ([#305](https://github.com/itsfja/second-thought/issues/305)); **Change this program** says what's different before loading ([#306](https://github.com/itsfja/second-thought/issues/306)); GitHub through its own MCP server, with a **Review a GitHub repository** program ([#333](https://github.com/itsfja/second-thought/issues/333)); and Gemini calls that give up after a time limit and retry when it's busy ([#329](https://github.com/itsfja/second-thought/issues/329)).

Released in 3.11.0: Trust Wallet through its Agent Kit's MCP server, with money tools asking and a **Wallet health check** program ([#320](https://github.com/itsfja/second-thought/issues/320)); settings in layers, `ST_` variables then your home folder's ini then the program's ([#340](https://github.com/itsfja/second-thought/issues/340)); and exported settings files with every note on its own line ([#338](https://github.com/itsfja/second-thought/issues/338)). CI runs its end-to-end suite in three parts side by side ([#341](https://github.com/itsfja/second-thought/pull/341)).

Released in 3.12.0: drafts and revisions can use the web, and say so when a task names an address they can't open ([#332](https://github.com/itsfja/second-thought/issues/332)); a review loop stops when the review keeps raising the same problems, and says what's probably missing ([#331](https://github.com/itsfja/second-thought/issues/331)). The README became a short front page with pictures, with the detail in a guide in `docs/` ([#345](https://github.com/itsfja/second-thought/issues/345)).

Released in 3.13.0: agents say where each fact came from, and flag a source they never read ([#312](https://github.com/itsfja/second-thought/issues/312)); the files a program keeps are only yours, and settings can't set `LD_PRELOAD` and friends ([#307](https://github.com/itsfja/second-thought/issues/307)); Ruff in CI, and fuzz tests that found and fixed three crashes on broken input ([#313](https://github.com/itsfja/second-thought/issues/313)). Off claude.ai, the page runs programs with the model service of your choice and your own key ([#321](https://github.com/itsfja/second-thought/issues/321)), and each release has **second-thought-offline.html**, the page as one file that works with no network ([#314](https://github.com/itsfja/second-thought/issues/314)). CI runs the exported programs in three shares side by side ([#342](https://github.com/itsfja/second-thought/issues/342)).

## Later: important, not urgent

| | Benefit | Cost |
|---|---|---|
| [#321](https://github.com/itsfja/second-thought/issues/321) The page runs programs with the service of your choice | High: off claude.ai the page runs only with Claude (#293); a program whose primary is another service sees Claude standing in until after export, so GitHub — the Pages copy or a local clone — can't try the model the program will really use | Medium-high: a second family of model calls in the browser (OpenAI-compatible, which most services speak), keys and a wider security policy for more than one service, and a third page behaviour to keep true |

## Backlog: raised in the reviews, not yet scheduled

Everything the outside reviews of the code raised that isn't closed or listed above, `priority: 3` first and then `priority: 4`:

| | Benefit | Cost |
|---|---|---|
| [#305](https://github.com/itsfja/second-thought/issues/305) Approve from your phone: unattended runs ask on Telegram instead of refusing | High: a scheduled program that reaches a question no longer stops at the exact moment it matters, and the ask-first rule holds, answered fresh each time | Medium: a per-run question on Telegram with a short-lived answer, never replayed from a stopped run's journal |
| [#306](https://github.com/itsfja/second-thought/issues/306) Change this program: say what's different before loading it, new connections first | Medium: a changed program might do different things, so the page should say what before it loads, as Python's approval does | Low-medium: compare the two programs' blocks and describe the difference |
| [#309](https://github.com/itsfja/second-thought/issues/309) Kraken: a tool we don't know counts as money, and MCP tools marked destructive ask | Medium: the money rules follow what the server says its tools do, rather than a list that goes stale as kraken-cli changes | Low-medium: ask the server's tool catalog, and mark unknown tools as money rather than ordinary |
| [#311](https://github.com/itsfja/second-thought/issues/311) --update-runtime: say what the SHA-256 proves, and decide on signed releases | High: the updater is code execution on every exported program that self-updates, so its anchor wants a hold somewhere the repo can't reach | Medium: a signed manifest, or the SHA published in a second place the updater checks against |
| [#307](https://github.com/itsfja/second-thought/issues/307) Private files only for you, and second-thought.ini can't set LD_PRELOAD and friends | Medium: a settings file is shared and backed up more often than keys are, so it shouldn't be able to change how the program itself runs | Low-medium: keep the settings that change process behaviour to the environment |
| [#312](https://github.com/itsfja/second-thought/issues/312) Agent answers say where each fact came from | Medium: a made-up fact has no source to name, so provenance is a prompt-injection check as well as something a reader can follow | Medium: the agent carries its sources with its steps, and the summary shows them |
| [#313](https://github.com/itsfja/second-thought/issues/313) CI quality floor: Ruff, and fuzz tests for the parsers that read outside input | Medium: a linter and fuzzing catch what a careful writer misses, before a change lands, cheaply forever | Low-medium: a CI job; the parsers already have unit tests to hang the cases on |
| [#314](https://github.com/itsfja/second-thought/issues/314) A downloadable offline page as a release asset | Medium: the page keeps working when a CDN doesn't, and "one file you own" applies to the product itself | Medium: the libraries vendored in, and a release workflow that attaches the file |
| [#320](https://github.com/itsfja/second-thought/issues/320) Trust Wallet through its Agent Kit's MCP server (twak), money tools asking | Medium: the money rules reach another service, with the same always-asking before anything that moves money | Medium: an MCP server, so no settings beyond its own, and the money tools named in SAFETY |
| [#391](https://github.com/itsfja/second-thought/issues/391) A formal grammar for the program format, and --doctor checking a program against it | Medium: the program format is stated once, formally, so authoring a complex program rests on more than prose, and a broken one is caught before it runs | Medium: a grammar page in `docs/`, and a structural check in `--doctor` next to the environment checks it already does |
| [#392](https://github.com/itsfja/second-thought/issues/392) Systemd and Windows Task Scheduler unit examples in the docs, for a program that runs headless on a home server | Low-medium: the headless mode already exists, and copy-paste unit files are the missing step between an exported program and one that runs forever on a homelab box, whichever OS it runs | Low: one documented example per OS, with the restart and sandbox settings that make sense there |

## Backlog: the homelab and media connections, raised November 2026

The media stack around Docker and Proxmox: the same reads-first, ask-first shape as the connections that are already in, one issue each.

| | Benefit | Cost |
|---|---|---|
| [#397](https://github.com/itsfja/second-thought/issues/397) SABnzbd: the download queue, pausing and resuming always asking | Medium: a program could watch the queue and the failures, and pause when the bandwidth is wanted elsewhere | Low-medium: a JSON API with everything needed, and a short safety list |
| [#398](https://github.com/itsfja/second-thought/issues/398) Radarr and Sonarr (the Servarr family): the wanted list, searching always asking | Medium-high: a program could watch what's missing, what's stuck and what failed to import, across the whole family with one block | Medium: one connection over the shared Servarr API, a URL and key per service |
| [#399](https://github.com/itsfja/second-thought/issues/399) Unraid: the array, disks, shares and VMs, power actions always asking | Medium-high: a program could check the server each morning: array, disks, shares, containers and VMs | Medium: no official API; a community API plugin or the web UI's own endpoints |
| [#400](https://github.com/itsfja/second-thought/issues/400) NZBGeek: searching the indexer, fetching always asking | Low-medium: a program could report what the indexer has for the missing list | Low-medium if done through Prowlarr (#398); a small read-only API otherwise |
| [#401](https://github.com/itsfja/second-thought/issues/401) Pi-hole: DNS stats and blocking, changing lists always asking | Medium: a program could watch the blocked share and warn when blocking is off | Low-medium: a REST API (v6) with everything needed |
| [#402](https://github.com/itsfja/second-thought/issues/402) Plex (and Tautulli): the library, sessions and stats, stopping streams always asking | Medium: a program could check the server, last night's streams and the week's new items | Medium: a semi-documented API, and Tautulli's for the stats |

## Someday

| | Notes |
|---|---|
| [#129](https://github.com/itsfja/second-thought/issues/129)–[#139](https://github.com/itsfja/second-thought/issues/139) Eleven more languages | Paused for now; each costs only the people who pick it since #120 |

## If there's a successor

Keep the three ideas at the top of this page. Rebuild around plain-English authoring with blocks as the form you inspect, a separate editor codebase from the start, and a versioned program format from day one.
