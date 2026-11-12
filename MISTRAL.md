# Notes for Mistral sessions

Read CONTRIBUTING.md first: it has the layout, the rules and the tests. This file is what a session would otherwise
learn by trial and error. It mirrors CLAUDE.md; where the two disagree about the environment, trust the one that
matches where you're running.

## How Francis works
- Work goes through GitHub issues ("APARs"), each closed by one pull request (`Closes #n`), on its own branch.
  ROADMAP.md and the `roadmap` label say what's next; take them in priority order.
- "#n is conflicted": rebase that PR's branch on main, rebuild with `python tools/sync.py`, push with
  `--force-with-lease`.
- After PRs that change the page are merged, republish the artifact (below). Francis does the publishing; a session
  can rebuild `second-thought.html` but not publish it.
- Releasing: a "Release x.y.z" PR (Unreleased becomes x.y.z, `RUNTIME_VERSION` and the README badge follow) is merged
  first; then Francis publishes the GitHub release on main. The Release workflow refuses a tag whose runtime says
  another version, and then `--update-runtime` has nothing to download. If that happens, the tag has to be deleted
  and made again on main (deleting the release alone leaves the tag where it was).
- The language issues (#129–139, `priority:8`) are under way again (Francis, November 2026): Classical Chinese (#129), Classical Syriac (#130), Church Slavonic (#132), Ottoman Turkish (#133), Pali (#134), Classical Nahuatl (#135), Sumerian (#137), Hittite (#138) and Gothic (#139) are done.
- Never commit `second-thought.ini` or keys. Real-key checks (`tools/smoke_test.py`) cost money: Francis runs them,
  or says to.
- Commit messages and PR bodies say what changed and why, in plain English, ending with the attribution lines:

  ```
  Co-authored-by: Vibe Nuage Agent <vibe@mistral.ai>
  Co-authored-by: itsfja <itsfja@users.noreply.github.com>
  ```

## The environment (Mistral sandbox sessions)
- **Clone:** the session clones the repo itself (e.g. `gh repo clone itsfja/second-thought -- --depth 1`); there is
  no preselected checkout. Work on a task branch, never directly on main.
- **GitHub:** `gh` is authenticated and works (REST and GraphQL). If a call fails with 502 or a rate-limit message,
  wait about 60 seconds and retry once, then report it.
- **Actions job logs, secrets, releases and tags** are best left to Francis; ask for logs rather than fetching them.
- **Tests:** `bash tests/setup.sh` once (it fetches `tests/vendor`, git-ignored). In a git worktree, symlink
  `tests/vendor` from the main checkout. `python tests/run_tests.py --parallel` runs the full suite as CI's five
  parts side by side, in about 10 minutes (25 in one process); run it in the background, one at a time (two would fight
  over the CPUs). `python tests/run_tests.py sources i18n gallery` is quicker.
- **CI runs on GitHub Actions**, where `GITHUB_ACTIONS` is set; the tests clear it (tests/e2e/common.py).
- **i18n merges:** `python tools/merge_i18n.py --install` once per clone.
- **New words:** `python tools/i18n.py missing`, then write translations for all 30 languages into a JSON file and
  `python tools/i18n.py add words.json` (Mycenaean Greek, Akkadian, Sumerian, Hittite, Middle Egyptian, Coptic, Syriac and Gothic romanised; the tool writes the scripts).

## The artifact
The page is published at https://claude.ai/artifact/XmNRmDbYLY3bo7o31nvdzN. Publishing needs `second-thought.html` with
every `lang/<code>.js` as a supporting file at `lang/<code>.js` (all 30), to that URL — a session can't reach
claude.ai's publish flow, so Francis publishes after merge. If the publish says files changed since last seen, read
them first (they'll match an earlier main).

## Loose ends
- itsfja/rain-watcher (private) is the Rain window program on GitHub Actions (#226). Its summer-time cron line
  (17:00 UTC, weekdays) should start and do nothing; Friday 18:00 London should send the Telegram message.
