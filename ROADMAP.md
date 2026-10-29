# Roadmap

Where Second Thought is going, and in what order. Each item is an issue; this page says why it's where it is.

## What Second Thought is for

Second Thought is for people who have a checklist, a rubric or house rules, but nobody to automate them. Three ideas make that work, and everything here is judged by whether it strengthens them:

1. **Programs check their own work** against criteria a person wrote down.
2. **Actions ask first.** A program says what it can do before its first run, and asks before each thing it sends or changes.
3. **One file you own.** Any program exports as a single Python file that runs with nothing else installed.

The project has grown wide: over 160 examples, 31 community programs, 19 languages, 15 model services. The next gains come from **trust and reach**, not more blocks. Items are ordered by expected benefit against cost; the labels `priority: 1` to `priority: 4` say the same.

## Now: trust

| | Benefit | Cost |
|---|---|---|
| [#188](https://github.com/itsfja/second-thought/issues/188) Prompt-injection test suite: hostile emails, issues and pages must never cause an unasked action | High: agents now read untrusted text and act | Medium |
| [#189](https://github.com/itsfja/second-thought/issues/189) Run every gallery program once against real models, with a cost cap | High: prompts are only tested against fakes today | Low |

#188 comes first. The asking gates are the safety story, and gallery programs like issue-triage-bot run against public input.

## Next: reach

| | Benefit | Cost |
|---|---|---|
| [#192](https://github.com/itsfja/second-thought/issues/192) Write a program in plain English: Claude builds the blocks, you check them | Very high | Medium |
| [#191](https://github.com/itsfja/second-thought/issues/191) Export as a GitHub Actions workflow, so scheduled programs run free | High | Medium |
| [#190](https://github.com/itsfja/second-thought/issues/190) Warn when a model name has been retired | Medium | Low |
| [#196](https://github.com/itsfja/second-thought/issues/196) Gallery pack: Teaching | High | Low |
| [#197](https://github.com/itsfja/second-thought/issues/197) Gallery pack: Food businesses | High | Low |
| [#198](https://github.com/itsfja/second-thought/issues/198) Gallery pack: Plain English and accessibility | High | Low |

Plain-English authoring is the biggest unlock for the people this is for: the blocks become the readable, checkable form of a request. GitHub Actions export removes the need for an always-on computer, the biggest hurdle after that.

## Later: depth

| | Benefit | Cost |
|---|---|---|
| [#193](https://github.com/itsfja/second-thought/issues/193) Tests for programs: saved inputs plus what the result should achieve | High | High |
| [#195](https://github.com/itsfja/second-thought/issues/195) Version the block file format, with migrations | Medium | Medium |
| [#194](https://github.com/itsfja/second-thought/issues/194) Serve a program as an MCP tool | Medium | Medium |
| [#122](https://github.com/itsfja/second-thought/issues/122) Keep the editor's CSS and JS in source files | Medium | Medium |
| [#123](https://github.com/itsfja/second-thought/issues/123) Optional keychain storage for API keys | Low-medium | Low |
| [#199](https://github.com/itsfja/second-thought/issues/199) Gallery pack: Charities and volunteer groups | Medium-high | Low |
| [#200](https://github.com/itsfja/second-thought/issues/200) Gallery pack: Small professional practices | Medium | Low |
| [#201](https://github.com/itsfja/second-thought/issues/201) Gallery pack: Local news and civic groups | Medium | Low |

## Someday

| | Notes |
|---|---|
| [#202](https://github.com/itsfja/second-thought/issues/202) Gallery pack: Archives and family history | A natural home for the historical languages |
| [#203](https://github.com/itsfja/second-thought/issues/203) Gallery pack: Small research labs | arXiv fisher, generalised |
| [#129](https://github.com/itsfja/second-thought/issues/129)–[#139](https://github.com/itsfja/second-thought/issues/139) Eleven more languages | Paused for now; each costs only the people who pick it since #120 |

## If there's a successor

Keep the three ideas at the top of this page. Rebuild around plain-English authoring with blocks as the form you inspect, a separate editor codebase from the start, and a versioned program format from day one.
