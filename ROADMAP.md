# Roadmap

Where Second Thought is going, and in what order. Each item is an issue; this page says why it's where it is.

## What Second Thought is for

Second Thought is for people who have a checklist, a rubric or house rules, but nobody to automate them. Three ideas make that work, and everything here is judged by whether it strengthens them:

1. **Programs check their own work** against criteria a person wrote down.
2. **Actions ask first.** A program says what it can do before its first run, and asks before each thing it sends or changes.
3. **One file you own.** Any program exports as a single Python file that runs with nothing else installed.

The project has grown wide: over 160 examples, 31 community programs, 19 languages, 15 model services. The next gains come from **trust and reach**, not more blocks. Items are ordered by expected benefit against cost; the labels `priority: 1` to `priority: 4` say the same.

## Done

Trust: the prompt-injection tests ([#188](https://github.com/itsfja/second-thought/issues/188)) and a real-model run of the gallery ([#189](https://github.com/itsfja/second-thought/issues/189)). Reach: plain-English authoring ([#192](https://github.com/itsfja/second-thought/issues/192)), GitHub Actions export ([#191](https://github.com/itsfja/second-thought/issues/191)), retired-model warnings ([#190](https://github.com/itsfja/second-thought/issues/190)) and six gallery packs ([#196](https://github.com/itsfja/second-thought/issues/196)–[#201](https://github.com/itsfja/second-thought/issues/201)). Depth: test cases for programs ([#193](https://github.com/itsfja/second-thought/issues/193)), a versioned block format ([#195](https://github.com/itsfja/second-thought/issues/195)), programs as MCP tools ([#194](https://github.com/itsfja/second-thought/issues/194)), keys in the keychain ([#123](https://github.com/itsfja/second-thought/issues/123)) and the editor's code in its own files ([#122](https://github.com/itsfja/second-thought/issues/122)).

## Now: keep it safe, and cheaper to change

| | Benefit | Cost |
|---|---|---|
| [#219](https://github.com/itsfja/second-thought/issues/219) One source for the safety rules, shared by the page and the runtime | High: the asking rules are the safety promise, and are written twice | Medium |
| [#220](https://github.com/itsfja/second-thought/issues/220) Close the DNS-rebinding gap for pages and feeds the agent reads | Medium-high | Low-medium |
| [#217](https://github.com/itsfja/second-thought/issues/217) Merge i18n files key by key, so translation PRs stop conflicting | High | Low |
| [#218](https://github.com/itsfja/second-thought/issues/218) A translation tool: list missing words, add them, write Linear B and cuneiform safely | High | Low-medium |

#219 comes first. The page and exported Python must agree on what asks, and today that rests on care. #217 and #218 cut the cost of every future change: each new feature now costs 19 translations and, often, a round of conflicts.

## Next: the editor

| | Benefit | Cost |
|---|---|---|
| [#221](https://github.com/itsfja/second-thought/issues/221) Split web/editor.js into files by area | Medium | Medium |
| [#222](https://github.com/itsfja/second-thought/issues/222) Unit tests for the editor's logic, without a browser | Medium | Medium |
| [#223](https://github.com/itsfja/second-thought/issues/223) Keyboard and screen-reader use of the blocks and the run log | Medium | Medium |

## Later: polish

| | Benefit | Cost |
|---|---|---|
| [#224](https://github.com/itsfja/second-thought/issues/224) Show what a run cost in money, not just tokens | Low-medium | Low, plus upkeep |
| [#225](https://github.com/itsfja/second-thought/issues/225) When a program asks again, say what's new since it was allowed | Low-medium | Low |
| [#226](https://github.com/itsfja/second-thought/issues/226) Run Save as GitHub Actions for real once, and write down what's checked | Low-medium | Low |

## Someday

| | Notes |
|---|---|
| [#202](https://github.com/itsfja/second-thought/issues/202) Gallery pack: Archives and family history | A natural home for the historical languages |
| [#203](https://github.com/itsfja/second-thought/issues/203) Gallery pack: Small research labs | arXiv fisher, generalised |
| [#129](https://github.com/itsfja/second-thought/issues/129)–[#139](https://github.com/itsfja/second-thought/issues/139) Eleven more languages | Paused for now; each costs only the people who pick it since #120 |

## If there's a successor

Keep the three ideas at the top of this page. Rebuild around plain-English authoring with blocks as the form you inspect, a separate editor codebase from the start, and a versioned program format from day one.
