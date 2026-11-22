# Notes for AI helpers

The rules every helper follows, whichever tool it runs in. Read [CONTRIBUTING.md](CONTRIBUTING.md) first: it has the
layout, the rules and the tests. Each tool's own file ([CLAUDE.md](CLAUDE.md), [MISTRAL.md](MISTRAL.md)) adds only
what's different where it runs: how it reaches GitHub, what it can publish, and how its commits are signed. Where this
page and a tool's file disagree about the environment, trust the tool's file.

## How Francis works
- Work goes through GitHub issues ("APARs"), each closed by one pull request ("PTF", with `Closes #n`), on its own
  branch. "Severity n" is the `priority: n` label. ROADMAP.md and the `roadmap` label say what's next; take them in
  priority order.
- "#n is conflicted": rebase that PR's branch on main, rebuild with `python tools/sync.py`, push with
  `--force-with-lease`.
- After PRs that change the page are merged, the artifact is republished from main (below).
- Releasing: a "Release x.y.z" PR (Unreleased becomes x.y.z, `RUNTIME_VERSION` and the README badge follow) is merged
  first; then Francis publishes the GitHub release on main. The Release workflow refuses a tag whose runtime says
  another version, and then `--update-runtime` has nothing to download. If that happens, the tag has to be deleted
  and made again on main (deleting the release alone leaves the tag where it was).
- Remake the pictures with the release (#454): `python tools/record_demo.py && python tools/record_docs.py` (after
  `bash tests/setup.sh`; needs ffmpeg and mmdc on the PATH), and commit the new `screenshots/` with the release PR.
- The language issues (#129–139, `priority:8`) are under way again (Francis, November 2026): Classical Chinese (#129),
  Classical Syriac (#130), Church Slavonic (#132), Ottoman Turkish (#133), Pali (#134), Classical Nahuatl (#135),
  Sumerian (#137), Hittite (#138) and Gothic (#139) are done.
- Never commit `second-thought.ini` or keys. Real-key checks (`tools/smoke_test.py`) cost money: Francis runs them,
  or says to.
- Commit messages and PR bodies say what changed and why, in plain English, ending with the attribution lines your
  tool's file gives.
- Page and word changes follow [docs/design.md](docs/design.md): the tokens in `web/editor.css`, the layout rules,
  and the voice (short sentences, plain words, British spelling, what a thing does before how it works).

## Tests
- `bash tests/setup.sh` once (it fetches `tests/vendor`, git-ignored). In a git worktree, symlink `tests/vendor` from
  the main checkout.
- `python tests/run_tests.py --parallel` runs the full suite as CI's five parts side by side, in about 10 minutes
  (25 in one process); run it in the background, one at a time (two would fight over the CPUs).
  `python tests/run_tests.py sources i18n gallery` is quicker, and `python -m unittest discover -s tests/unit` takes
  about a minute.
- CI runs on GitHub Actions, where `GITHUB_ACTIONS` is set; the tests clear it (tests/e2e/common.py).

## Words and languages
- **i18n merges:** `python tools/merge_i18n.py --install` once per clone.
- **Who read the words (#460):** each `i18n/*.json` has `"read_by"`. Words a model wrote are `model`; only Francis
  changes one to `speaker`, once a named speaker has read it through.
- **New words:** `python tools/i18n.py missing`, then write translations for all 34 languages (not qnr, qar or qcg,
  below) into a JSON file and `python tools/i18n.py add words.json` (Mycenaean Greek, Akkadian, Sumerian, Hittite,
  Middle Egyptian, Coptic, Syriac and Gothic romanised; the tool writes the scripts).
- **Old Norse in runes (`qnr`, #465) and Old English in runes (`qar`, #466)** are made from `i18n/non.json` and
  `i18n/ang.json`: never edit `i18n/qnr.json` or `i18n/qar.json`. `i18n.py add` writes them again; after any other
  change to non.json or ang.json, run `python tools/i18n.py derive`. A new name or English field name that must stay
  in Latin letters goes in `tools/latin_kept.json` (`own` there lists Old English words spelled like one: on, to).
  Church Slavonic in Glagolitic (`qcg`, #467) is made the same way from `i18n/cu.json`, letter for letter.

## What done means
A pull request is ready when every box in [the pull-request template](.github/pull_request_template.md) is ticked or
doesn't apply: the tests pass, `python tools/sync.py --check` passes with the rebuilt files committed, the runtime
change has a changelog line, a new block is in the block list and the conversion guide (sync writes both), and a
visible page change has new pictures.

## The artifact
The page is published at https://claude.ai/artifact/XmNRmDbYLY3bo7o31nvdzN: `second-thought.html` with every
`lang/<code>.js` as a supporting file at `lang/<code>.js` (all 37). If the publish says files changed since last
seen, read them first (they'll match an earlier main), then publish. Your tool's file says whether you can publish
it or Francis does.

## Loose ends
- itsfja/rain-watcher (private) is the Rain window program on GitHub Actions (#226). Its summer-time cron line
  (17:00 UTC, weekdays) should start and do nothing; Friday 18:00 London should send the Telegram message.
