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

## Now: fixes reach people

| | Benefit | Cost |
|---|---|---|
| [#244](https://github.com/itsfja/second-thought/issues/244) Tell exported programs when their runtime is out of date, and update it in place | High: each program carries a frozen runtime, so a security fix reaches only those who re-export | Medium |
| [#241](https://github.com/itsfja/second-thought/issues/241) A budget in money, not just tokens | Medium: people think in money, and unattended runs need a cap | Low |

#244 comes first. It's the gap SECURITY.md names, and 3.0.0 and 3.0.1 are already fixes nobody is told about. #241 is cheap now the run knows its cost.

## Next: GitHub as a home

| | Benefit | Cost |
|---|---|---|
| [#246](https://github.com/itsfja/second-thought/issues/246) Run a program's test cases on GitHub Actions | Medium-high, and distinctive | Low-medium |
| [#245](https://github.com/itsfja/second-thought/issues/245) Publish the page on GitHub Pages as a second front door | Medium | Low |

## Later: upkeep

| | Benefit | Cost |
|---|---|---|
| [#242](https://github.com/itsfja/second-thought/issues/242) Blockly 12, with its own keyboard navigation | Medium | Medium |
| [#243](https://github.com/itsfja/second-thought/issues/243) Prices for the rest of the model services | Low-medium | Low, plus upkeep |

## Someday

| | Notes |
|---|---|
| [#247](https://github.com/itsfja/second-thought/issues/247) Gallery: Premium Bonds generations | Waiting on a few real lines of NS&I's pages, numbers changed |
| [#129](https://github.com/itsfja/second-thought/issues/129)–[#139](https://github.com/itsfja/second-thought/issues/139) Eleven more languages | Paused for now; each costs only the people who pick it since #120 |

## If there's a successor

Keep the three ideas at the top of this page. Rebuild around plain-English authoring with blocks as the form you inspect, a separate editor codebase from the start, and a versioned program format from day one.
