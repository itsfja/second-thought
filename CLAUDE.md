# Notes for Claude sessions

Read [AGENTS.md](AGENTS.md) first: how Francis works, the tests, the words and what done means are there, for every
helper. This file is only what's different in a Claude cloud session.

## Signing commits and PRs
End commit messages and PR bodies with the attribution lines the session gives.

## The environment (cloud sessions)
- **GitHub:** only `gh api` (REST) works: GraphQL (`gh pr`, `gh issue`) is blocked. Open PRs with
  `gh api repos/itsfja/second-thought/pulls -f title=… -f head=<branch> -f base=main -F body=@file`. Actions job logs,
  secrets, branch deletion, tags and releases are blocked too (Francis makes releases on GitHub); ask Francis for
  logs (or read annotations via `check-runs/<id>/annotations`).
- **Pushing a new branch:** pushes sometimes fail with a server error; retry after a few seconds. If a stop hook says
  a branch has no remote, `git push -u origin <branch>` again.

## The artifact
A Claude session can publish the page itself, to the URL in AGENTS.md, with all 41 `lang/<code>.js` files.
