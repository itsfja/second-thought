## GitHub

The **GitHub** blocks look at your projects and can comment, always asking first:

- **when a pull request asks for my review**, checked every 5 minutes. **when a new issue is opened in** `owner/name`, checked every 5 minutes (pull requests don't count). **when a release is published in** `owner/name`, checked every 15 minutes. **what arrived** gives the pull request's or issue's `repo`, `number`, `title`, `user` or `author`, `link` and `text` (plus `body` and `labels` for an issue; `tag`, `name`, `previous_tag` and `notes` for a release).
- The agent's **GitHub** tools read your repositories, search them, read a pull request, list its branches and commits, and comment on a pull request or open and label an issue — commenting always asks you first, even when nothing else does.

On the page these blocks use **sample projects**, and nothing is posted: try **When someone asks for my review (GitHub)**. The listeners start from what's new after the program starts; pull requests and issues that arrived while it was off don't start the script.

**Settings:** `[github]` in `second-thought.ini` — `GITHUB_TOKEN`, from github.com/settings/tokens. Read access is enough to look; to comment, it also needs write access to pull requests. `--doctor` reads your pull requests when the program can.
