# Roadmap

Where Second Thought is going, and in what order. Each item is an issue; this page says why it's where it is.

## What Second Thought is for

Second Thought is for people who have a checklist, a rubric or house rules, but nobody to automate them. Three ideas make that work, and everything here is judged by whether it strengthens them:

1. **Programs check their own work** against criteria a person wrote down.
2. **Actions ask first.** A program says what it can do before its first run, and asks before each thing it sends or changes.
3. **One file you own.** Any program exports as a single Python file that runs with nothing else installed.

The project has grown wide: over 160 examples, 31 community programs, 19 languages, 15 model services. The next gains come from **trust and reach**, not more blocks. Items are ordered by expected benefit against cost; the labels `priority: 1` to `priority: 4` say the same.

## Done

Trust: the prompt-injection tests ([#188](https://github.com/itsfja/second-thought/issues/188)) and a real-model run of the gallery ([#189](https://github.com/itsfja/second-thought/issues/189)). Reach: plain-English authoring ([#192](https://github.com/itsfja/second-thought/issues/192)), GitHub Actions export ([#191](https://github.com/itsfja/second-thought/issues/191)), retired-model warnings ([#190](https://github.com/itsfja/second-thought/issues/190)) and eight gallery packs ([#196](https://github.com/itsfja/second-thought/issues/196)–[#203](https://github.com/itsfja/second-thought/issues/203)). Depth: test cases for programs ([#193](https://github.com/itsfja/second-thought/issues/193)), a versioned block format ([#195](https://github.com/itsfja/second-thought/issues/195)), programs as MCP tools ([#194](https://github.com/itsfja/second-thought/issues/194)), keys in the keychain ([#123](https://github.com/itsfja/second-thought/issues/123)) and the editor's code in its own files ([#122](https://github.com/itsfja/second-thought/issues/122)).

Safety and cost of change, released in 3.0.0: one source for the safety rules ([#219](https://github.com/itsfja/second-thought/issues/219)), the DNS-rebinding gap closed ([#220](https://github.com/itsfja/second-thought/issues/220)), translation files merged key by key ([#217](https://github.com/itsfja/second-thought/issues/217)) and a translation tool ([#218](https://github.com/itsfja/second-thought/issues/218)). The editor split into files by area ([#221](https://github.com/itsfja/second-thought/issues/221)), with unit tests ([#222](https://github.com/itsfja/second-thought/issues/222)) and keyboard and screen-reader use ([#223](https://github.com/itsfja/second-thought/issues/223)). Polish: a run's cost in money ([#224](https://github.com/itsfja/second-thought/issues/224)), saying what's new when a program asks again ([#225](https://github.com/itsfja/second-thought/issues/225)), and a real run on GitHub Actions ([#226](https://github.com/itsfja/second-thought/issues/226)).

Fixes reach people, released in 3.1.0: exported programs say when their runtime is out of date and update it in place ([#244](https://github.com/itsfja/second-thought/issues/244)).

What a run costs, in terms people use, released in 3.2.0 and 3.3.0: a budget in money ([#241](https://github.com/itsfja/second-thought/issues/241)), and costs and budgets in pounds, euros, yen or yuan ([#263](https://github.com/itsfja/second-thought/issues/263)).

What models and keys cost, released in 3.4.1 to 3.7.0: how expensive each model is and who makes it ([#264](https://github.com/itsfja/second-thought/issues/264)), prices for the rest of the services ([#243](https://github.com/itsfja/second-thought/issues/243)), each key's spending with hourly, daily, weekly and monthly allowances ([#269](https://github.com/itsfja/second-thought/issues/269)), and each account's plan with the limits services report ([#270](https://github.com/itsfja/second-thought/issues/270)). Also fixed: programs with a currency set stopped at start ([#274](https://github.com/itsfja/second-thought/issues/274)).

GitHub as a home, released in 3.8.0: a program's test cases on GitHub Actions ([#246](https://github.com/itsfja/second-thought/issues/246)), and the page on GitHub Pages as a second front door ([#245](https://github.com/itsfja/second-thought/issues/245)).

Reach and trust, released in 3.9.0 and 3.9.1: the Pages copy runs programs with your own API key ([#293](https://github.com/itsfja/second-thought/issues/293)), Kraken through its own MCP server with tools that move money always asking ([#262](https://github.com/itsfja/second-thought/issues/262)), and Blockly 13 with its own keyboard navigation ([#242](https://github.com/itsfja/second-thought/issues/242)). Then MiniMax's quick tier moved to M3.1 Flash, which has a price ([#281](https://github.com/itsfja/second-thought/issues/281)).

## Later: important, not urgent

| | Benefit | Cost |
|---|---|---|
| [#247](https://github.com/itsfja/second-thought/issues/247) Gallery: Premium Bonds generations | Medium: an agent whose arithmetic is checked | Low-medium, once a few real lines of NS&I's pages are in (numbers changed) |

## Someday

| | Notes |
|---|---|
| [#129](https://github.com/itsfja/second-thought/issues/129)–[#139](https://github.com/itsfja/second-thought/issues/139) Eleven more languages | Paused for now; each costs only the people who pick it since #120 |

## If there's a successor

Keep the three ideas at the top of this page. Rebuild around plain-English authoring with blocks as the form you inspect, a separate editor codebase from the start, and a versioned program format from day one.
