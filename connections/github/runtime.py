    # GitHub
    async def _gh(self, path, method="GET", body=None):
        token = os.environ.get("GITHUB_TOKEN", "")
        if not token:
            raise RunError(tr("GitHub needs a token: set GITHUB_TOKEN {where_keys} (make one at https://github.com/settings/tokens).", where_keys=WHERE_KEYS))
        req = urllib.request.Request(GITHUB_API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                                              "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "SecondThought",
                                              "Content-Type": "application/json"})

        def go():
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    return json.loads(r.read() or b"null")
            except urllib.error.HTTPError as e:
                why = {401: "the token was refused. Check GITHUB_TOKEN", 403: "GitHub said no (the token may lack access, or the hourly limit was reached)",
                       404: "not found, or the token can't see it", 422: "GitHub couldn't use that request"}.get(e.code, f"GitHub answered {e.code}")
                raise RunError(tr("GitHub: {why}.", why=why)) from None
            except urllib.error.URLError as e:
                raise RunError(tr("Couldn't reach GitHub ({reason}).", reason=e.reason)) from None
        return await asyncio.to_thread(go)

    @staticmethod
    def _gh_repo(repo):
        repo = to_str(repo).strip().removeprefix("https://github.com/").strip("/")
        if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
            raise RunError(tr("“{repo}” isn't a GitHub project. Use owner/name, like octocat/hello-world.", repo=repo))
        return repo

    @staticmethod
    def _ago(iso):
        d = _parse_date(iso)
        if not d:
            return ""
        h = (datetime.datetime.now() - d).total_seconds() / 3600
        return "just now" if h < 1 else f"{int(h)} h ago" if h < 48 else f"{int(h // 24)} days ago"

    async def gh_repos(self, owner=""):
        owner = to_str(owner).strip()
        rows = await self._gh(f"/users/{urllib.parse.quote(owner)}/repos?sort=pushed&per_page=30" if owner else "/user/repos?sort=pushed&per_page=30")
        return "\n".join(f"{r['full_name']}: {r.get('description') or '(no description)'} · {r.get('language') or '-'} · "
                         f"★{r.get('stargazers_count', 0)} · {r.get('open_issues_count', 0)} open issues and pull requests · pushed {self._ago(r.get('pushed_at'))}"
                         for r in rows) or "No projects."

    async def gh_pulls(self, repo, state="open"):
        repo = self._gh_repo(repo)
        state = to_str(state).strip().lower() or "open"
        rows = await self._gh(f"/repos/{repo}/pulls?state={state if state in ('open', 'closed', 'all') else 'open'}&per_page=20&sort=updated&direction=desc")
        return "\n".join(f"#{r['number']} {r['title']} · by {r['user']['login']} · updated {self._ago(r.get('updated_at'))}"
                         + (" · draft" if r.get("draft") else "") for r in rows) or f"No {state} pull requests in {repo}."

    async def _gh_search(self, q, n=20):
        data = await self._gh("/search/issues?per_page=" + str(n) + "&sort=updated&q=" + urllib.parse.quote(q))
        out = []
        for r in data.get("items", []):
            repo = r.get("repository_url", "").split("/repos/", 1)[-1]
            kind = "pull request" if "pull_request" in r else "issue"
            out.append(f"{repo} #{r['number']} {r['title']} · {kind} by {r['user']['login']} · {r.get('state', '')} · updated {self._ago(r.get('updated_at'))}")
        return out

    async def gh_for_me(self):
        review = await self._gh_search("is:pr is:open review-requested:@me archived:false")
        mine = await self._gh_search("is:pr is:open author:@me archived:false")
        return ("Waiting for your review:\n" + ("\n".join(review) or "(none)") + "\n\nYour open pull requests:\n" + ("\n".join(mine) or "(none)"))

    async def gh_search(self, query):
        query = to_str(query).strip()
        if not query:
            raise RunError(tr("search_github needs something to search for."))
        return "\n".join(await self._gh_search(query)) or f"Nothing found for “{query}”."

    async def gh_read_pr(self, repo, number):
        repo, n = self._gh_repo(repo), round_js(num(number))
        pr = await self._gh(f"/repos/{repo}/pulls/{n}")
        files = await self._gh(f"/repos/{repo}/pulls/{n}/files?per_page=50")
        comments = await self._gh(f"/repos/{repo}/issues/{n}/comments?per_page=30")
        lines = [f"{repo} #{n}: {pr['title']}", f"By {pr['user']['login']} · {pr['state']}" + (" · draft" if pr.get("draft") else "")
                 + (" · merged" if pr.get("merged") else "") + f" · {pr['head']['ref']} → {pr['base']['ref']} · updated {self._ago(pr.get('updated_at'))}",
                 "", _short(pr.get("body") or "(no description)", 2000), "", f"Files changed ({len(files)}):"]
        budget = 9000
        for f in files:
            lines.append(f"- {f['filename']} (+{f.get('additions', 0)} −{f.get('deletions', 0)})")
            patch = f.get("patch") or ""
            if patch and budget > 0:
                lines.append(patch[:min(1500, budget)])
                budget -= min(1500, len(patch))
        if comments:
            lines += ["", "Comments:"] + [f"- {c['user']['login']}: {_short(c.get('body', ''), 400)}" for c in comments[-10:]]
        return "\n".join(lines)

    async def gh_branches(self, repo):
        """Each branch with its last commit's age and author, oldest first, and any open pull request from it."""
        repo = self._gh_repo(repo)
        info = await self._gh(f"/repos/{repo}")
        branches = (await self._gh(f"/repos/{repo}/branches?per_page=100"))[:40]
        pulls = await self._gh(f"/repos/{repo}/pulls?state=open&per_page=100")
        open_from = {p["head"]["ref"]: p["number"] for p in pulls  # pull requests from this project's own branches, not forks
                     if ((p.get("head") or {}).get("repo") or {}).get("full_name", repo) == repo}
        commits = await asyncio.gather(*(self._gh(f"/repos/{repo}/commits/{b['commit']['sha']}") for b in branches))
        rows = []
        for b, c in zip(branches, commits):
            who = ((c.get("author") or {}).get("login") or (c.get("commit", {}).get("author") or {}).get("name") or "?")
            when = (c.get("commit", {}).get("committer") or {}).get("date") or (c.get("commit", {}).get("author") or {}).get("date")
            rows.append((_parse_date(when) or datetime.datetime.min, f"{b['name']} · last commit {self._ago(when)} by {who}"
                         + (" · default branch" if b["name"] == info.get("default_branch") else "")
                         + (f" · open pull request #{open_from[b['name']]}" if b["name"] in open_from else "")))
        rows.sort(key=lambda r: r[0])
        return "\n".join(r[1] for r in rows) or f"No branches in {repo}."

    @staticmethod
    def _gh_since(since):
        """'yesterday', 'today', a number of days, or YYYY-MM-DD, as an ISO time for GitHub. 7 days if empty."""
        s = to_str(since).strip().lower()
        today = datetime.datetime.now(datetime.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        if s in ("", "week", "last week"):
            day = today - datetime.timedelta(days=7)
        elif s == "today":
            day = today
        elif s == "yesterday":
            day = today - datetime.timedelta(days=1)
        elif re.fullmatch(r"\d+( days?)?", s):
            day = today - datetime.timedelta(days=int(s.split()[0]))
        elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            day = datetime.datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
        else:
            return None
        return day.strftime("%Y-%m-%dT%H:%M:%SZ")

    async def gh_commits(self, repo, author="", since=""):
        """Commits on the default branch, newest first. author 'me' means the token's owner."""
        repo, author = self._gh_repo(repo), to_str(author).strip()
        if author.lower() in ("me", "@me"):
            author = (await self._gh("/user")).get("login", "")
        start = self._gh_since(since)
        if not start:
            return f"“{since}” isn't a time to start from. Use today, yesterday, a number of days, or a date like 2026-10-01."
        q = f"per_page=50&since={start}" + (f"&author={urllib.parse.quote(author)}" if author else "")
        rows = await self._gh(f"/repos/{repo}/commits?{q}")
        return "\n".join(f"{c['sha'][:7]} · {self._ago((c.get('commit', {}).get('author') or {}).get('date'))} · "
                         f"{(c.get('author') or {}).get('login') or (c.get('commit', {}).get('author') or {}).get('name') or '?'}: "
                         f"{_short((c.get('commit') or {}).get('message', '').split(chr(10))[0], 200)}" for c in rows) \
            or f"No commits in {repo}" + (f" by {author}" if author else "") + " in that time."

    async def gh_read_file(self, repo, path="", ref=""):
        """One file's text, or a folder's contents. ref is a branch, tag or commit (the default branch if empty)."""
        repo, path, ref = self._gh_repo(repo), to_str(path).strip().strip("/"), to_str(ref).strip()
        data = await self._gh(f"/repos/{repo}/contents/{urllib.parse.quote(path)}" + (f"?ref={urllib.parse.quote(ref)}" if ref else ""))
        where = f"{repo}/{path}" + (f" at {ref}" if ref else "")
        if isinstance(data, list):
            return f"{where or repo} is a folder:\n" + "\n".join(f"{x['name']}{'/' if x.get('type') == 'dir' else ''}" for x in data)
        if data.get("encoding") != "base64" or data.get("content") is None:
            return f"{where} can't be read as text (it's too big for GitHub to send, or not a file)."
        raw = base64.b64decode(data["content"])
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return f"{where} isn't a text file ({len(raw):,} bytes)."
        limit = 30000
        return f"{where}:\n{text[:limit]}" + (f"\n\n(Only the first {limit:,} of {len(text):,} characters.)" if len(text) > limit else "")

    async def gh_open_issue(self, repo, title, body, approved=False):
        """Opens an issue, asking first. Says what happened, for the agent."""
        repo, title, body = self._gh_repo(repo), to_str(title).strip(), to_str(body).strip()
        if not title:
            return "Not opened: an issue needs a title."
        if (not approved or self.dry_run()) and not await self._allowed(["messages"], f"open an issue in {repo}: {_short(title, 120)}"):
            return "Not opened: the person said no, or nobody was there to ask."
        made = await self._gh(f"/repos/{repo}/issues", "POST", {"title": title, "body": body})
        self.log(tr("GitHub issue opened in {repo}: #{n}", repo=repo, n=made.get("number")), title + ("\n\n" + body if body else ""), tr("sent"))
        return f"Opened {repo} #{made.get('number')}: {made.get('html_url', '')}"

    async def gh_add_labels(self, repo, number, labels, approved=False):
        """Adds labels the repo already has, asking first. Says what happened, for the agent."""
        repo, n = self._gh_repo(repo), round_js(num(number))
        want = [to_str(x).strip() for x in (labels if isinstance(labels, list) else re.split(r"\s*,\s*", to_str(labels))) if to_str(x).strip()]
        if not want:
            return "Not labelled: give at least one label."
        have = {lb["name"].lower(): lb["name"] for lb in await self._gh(f"/repos/{repo}/labels?per_page=100")}
        unknown = [x for x in want if x.lower() not in have]
        if unknown:
            return (f"Not labelled: {repo} has no label {', '.join(unknown)}. Use only its own labels: "
                    + (", ".join(sorted(have.values())) or "(it has none)") + ".")
        names = [have[x.lower()] for x in want]
        if (not approved or self.dry_run()) and not await self._allowed(["messages"], f"label {repo} #{n}: {', '.join(names)}"):
            return "Not labelled: the person said no, or nobody was there to ask."
        await self._gh(f"/repos/{repo}/issues/{n}/labels", "POST", {"labels": names})
        self.log(tr("GitHub labels on {repo} #{n}", repo=repo, n=n), ", ".join(names), tr("sent"))
        return f"Labelled {repo} #{n}: {', '.join(names)}."

    async def gh_comment(self, repo, number, text, approved=False):
        repo, n, text = self._gh_repo(repo), round_js(num(number)), to_str(text).strip()
        if not text:
            raise RunError(tr("A comment needs some text."))
        if (not approved or self.dry_run()) and not await self._allowed(["messages"], f"comment on {repo} #{n}: {_short(text, 120)}"):
            return False
        await self._gh(f"/repos/{repo}/issues/{n}/comments", "POST", {"body": text})
        self.log(tr("GitHub comment on {repo} #{n}", repo=repo, n=n), text, tr("sent"))
        return True

    async def _listen_github(self, items):
        seen = None
        while True:
            try:
                data = await self._gh("/search/issues?per_page=50&q=" + urllib.parse.quote("is:pr is:open review-requested:@me archived:false"))
                now = {}
                for r in data.get("items", []):
                    repo = r.get("repository_url", "").split("/repos/", 1)[-1]
                    now[f"{repo}#{r['number']}"] = {"repo": repo, "number": r["number"], "title": r["title"], "user": r["user"]["login"],
                                                     "link": r.get("html_url", ""), "text": f"{repo} #{r['number']}: {r['title']} (by {r['user']['login']})"}
                if seen is not None:
                    for k, rec in now.items():
                        if k not in seen:
                            for _, fn in items:
                                self._fire(fn, dict(rec), tr("Review requested: {pr}", pr=k))
                seen = set(now)
            except RunError as e:
                print(tr("  (GitHub check failed: {e})", e=e), flush=True)
            await asyncio.sleep(self._poll(300))

    async def _listen_github_issue(self, items):
        """New issues in each project named in a 'when a new issue is opened in …' block (pull requests don't count)."""
        seen = {}
        while True:
            for repo in dict.fromkeys(to_str(a).strip() for a, _ in items):
                try:
                    rows = await self._gh(f"/repos/{self._gh_repo(repo)}/issues?state=open&sort=created&direction=desc&per_page=30")
                    now = {r["number"]: r for r in rows if "pull_request" not in r}
                    if repo in seen:
                        for n in sorted(set(now) - seen[repo]):
                            r = now[n]
                            rec = {"repo": repo, "number": n, "title": r["title"], "body": _short(r.get("body") or "", 4000),
                                   "author": (r.get("user") or {}).get("login", ""), "labels": [lb.get("name", "") for lb in r.get("labels", [])],
                                   "link": r.get("html_url", ""), "text": f"{repo} #{n}: {r['title']} (by {(r.get('user') or {}).get('login', '')})"}
                            for a, fn in items:
                                if to_str(a).strip() == repo:
                                    self._fire(fn, dict(rec), tr("New issue: {issue}", issue=f"{repo} #{n}"))
                    seen[repo] = seen.get(repo, set()) | set(now)
                except RunError as e:
                    print(tr("  (GitHub check failed: {e})", e=e), flush=True)
            await asyncio.sleep(self._poll(300))

    async def _listen_github_release(self, items):
        """New releases in each project named in a 'when a release is published in …' block."""
        seen = {}
        while True:
            for repo in dict.fromkeys(to_str(a).strip() for a, _ in items):
                try:
                    rows = [r for r in await self._gh(f"/repos/{self._gh_repo(repo)}/releases?per_page=10") if not r.get("draft")]
                    if repo in seen:
                        for i, r in enumerate(rows):
                            if r["id"] in seen[repo]:
                                continue
                            rec = {"repo": repo, "tag": r.get("tag_name", ""), "name": r.get("name") or r.get("tag_name", ""),
                                   "previous_tag": rows[i + 1].get("tag_name", "") if i + 1 < len(rows) else "",
                                   "notes": _short(r.get("body") or "", 4000), "link": r.get("html_url", ""),
                                   "text": f"{repo} {r.get('tag_name', '')}: {r.get('name') or r.get('tag_name', '')}"}
                            for a, fn in items:
                                if to_str(a).strip() == repo:
                                    self._fire(fn, dict(rec), tr("New release: {release}", release=f"{repo} {rec['tag']}"))
                    seen[repo] = seen.get(repo, set()) | {r["id"] for r in rows}
                except RunError as e:
                    print(tr("  (GitHub check failed: {e})", e=e), flush=True)
            await asyncio.sleep(self._poll(900))
