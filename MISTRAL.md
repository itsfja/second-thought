# Notes for Mistral sessions

Read [AGENTS.md](AGENTS.md) first: how Francis works, the tests, the words and what done means are there, for every
helper. This file is only what's different in a Mistral sandbox session.

## Signing commits and PRs
End commit messages and PR bodies with:
```
Co-authored-by: Vibe Nuage Agent <vibe@mistral.ai>
Co-authored-by: itsfja <itsfja@users.noreply.github.com>
```

## Commands
**Commands for the terminal must be single-line strings**, chained with `&&`, never multi-line blocks. Multi-line
pastes fragment bash history, so up-arrow recall then yields one orphaned line at a time and the terminal becomes
unusable for recall. One logical operation = one line.

## The environment (Mistral sandbox sessions)
- **Clone:** the session clones the repo itself (e.g. `gh repo clone itsfja/second-thought -- --depth 1`); there is
  no preselected checkout. Work on a task branch, never directly on main.
- **GitHub:** `gh` is authenticated and works (REST and GraphQL). If a call fails with 502 or a rate-limit message,
  wait about 60 seconds and retry once, then report it.
- **Actions job logs, secrets, releases and tags** are best left to Francis; ask for logs rather than fetching them.

## The artifact
A session can't reach claude.ai's publish flow: it can rebuild `second-thought.html`, and Francis publishes after
merge.
