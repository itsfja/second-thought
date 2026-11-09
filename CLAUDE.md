# Notes for Claude sessions

Read CONTRIBUTING.md first: it has the layout, the rules and the tests. This file is what a session would otherwise
learn by trial and error.

## How Francis works
- Work goes through GitHub issues ("APARs"), each closed by one pull request (`Closes #n`), on its own branch.
  ROADMAP.md and the `roadmap` label say what's next; take them in priority order.
- "#n is conflicted": rebase that PR's branch on main, rebuild with `python tools/sync.py`, push with
  `--force-with-lease`.
- After PRs that change the page are merged, republish the artifact (below).
- Releasing: a "Release x.y.z" PR (Unreleased becomes x.y.z, `RUNTIME_VERSION` and the README badge follow) is merged
  first; then Francis publishes the GitHub release on main. The Release workflow refuses a tag whose runtime says
  another version, and then `--update-runtime` has nothing to download. If that happens, the tag has to be deleted
  and made again on main (deleting the release alone leaves the tag where it was).
- The language issues (#129–139, `priority:8`) are under way again (Francis, November 2026): Classical Chinese (#129), Classical Syriac (#130), Church Slavonic (#132), Ottoman Turkish (#133), Pali (#134) and Classical Nahuatl (#135) are done; the rest follow one PR each.
- Never commit `second-thought.ini` or keys. Real-key checks (`tools/smoke_test.py`) cost money: Francis runs them,
  or says to.
- Commit messages and PR bodies say what changed and why, in plain English, ending with the attribution lines.

## The environment (cloud sessions)
- **GitHub:** only `gh api` (REST) works: GraphQL (`gh pr`, `gh issue`) is blocked. Open PRs with
  `gh api repos/itsfja/second-thought/pulls -f title=… -f head=<branch> -f base=main -F body=@file`. Actions job logs,
  secrets, branch deletion, tags and releases are blocked too (Francis makes releases on GitHub); ask Francis for logs (or read annotations via `check-runs/<id>/annotations`).
- **Pushing a new branch:** pushes sometimes fail with a server error; retry after a few seconds. If a stop hook says
  a branch has no remote, `git push -u origin <branch>` again.
- **Tests:** `bash tests/setup.sh` once (it fetches `tests/vendor`, git-ignored). In a git worktree, symlink
  `tests/vendor` from the main checkout. Run one full suite at a time (the stand-in services use fixed ports); it
  takes about 25 minutes, so run it in the background. `python tests/run_tests.py sources i18n gallery` is quicker.
- **CI runs on GitHub Actions**, where `GITHUB_ACTIONS` is set; the tests clear it (tests/e2e/common.py).
- **i18n merges:** `python tools/merge_i18n.py --install` once per clone.
- **New words:** `python tools/i18n.py missing`, then write translations for all 27 languages into a JSON file and
  `python tools/i18n.py add words.json` (Mycenaean Greek, Akkadian, Middle Egyptian, Coptic and Syriac romanised; the tool writes the scripts).

## The artifact
The page is published at https://claude.ai/artifact/XmNRmDbYLY3bo7o31nvdzN. Publish `second-thought.html` with every
`lang/<code>.js` as a supporting file at `lang/<code>.js` (all 27), to that URL. If the publish says files changed
since last seen, read them first (they'll match an earlier main), then publish.

## Loose ends
- itsfja/rain-watcher (private) is the Rain window program on GitHub Actions (#226). Its summer-time cron line
  (17:00 UTC, weekdays) should start and do nothing; Friday 18:00 London should send the Telegram message.
- #247 (Premium Bonds) needs a few real lines of NS&I's holdings and prize history pages, numbers changed.
