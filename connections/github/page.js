  const GH = () => { connNote("GitHub"); return CONN.github || { repos:[], pulls:[], issues:[] }; };
  function ghRepo(repo){
    repo = str(repo).trim().replace(/^https:\/\/github\.com\//, "").replace(/^\/+|\/+$/g, "");
    if (!/^[\w.-]+\/[\w.-]+$/.test(repo)) fail(tr("“{repo}” isn't a GitHub project. Use owner/name, like octocat/hello-world.", { repo }));
    return repo;
  }
  const ghLine = (r, kind) => r.repo + " #" + r.number + " " + r.title + " · " + kind + " by " + r.user + " · " + (r.state || "open") + " · updated " + agoText(r.days_ago);
  function ghForMe(){
    const g = GH(), me = g.login;
    const review = g.pulls.filter(p => p.review_requested).map(p => ghLine(p, "pull request"));
    const mine = g.pulls.filter(p => p.user === me).map(p => ghLine(p, "pull request"));
    return "Waiting for your review:\n" + (review.join("\n") || "(none)") + "\n\nYour open pull requests:\n" + (mine.join("\n") || "(none)");
  }
  function ghPulls(repo){
    repo = ghRepo(repo);
    const rows = GH().pulls.filter(p => p.repo === repo);
    return rows.map(p => "#" + p.number + " " + p.title + " · by " + p.user + " · updated " + agoText(p.days_ago) + (p.draft ? " · draft" : "")).join("\n") || "No open pull requests in " + repo + ".";
  }
  function ghReadPr(repo, number){
    repo = ghRepo(repo); const n = Math.floor(num(number) + 0.5);
    const p = GH().pulls.find(x => x.repo === repo && x.number === n);
    if (!p) fail(tr("GitHub: not found, or the token can't see it."));
    const lines = [repo + " #" + n + ": " + p.title, "By " + p.user + " · open" + (p.draft ? " · draft" : "") + " · " + p.head + " → " + p.base + " · updated " + agoText(p.days_ago),
                   "", short(p.body || "(no description)", 2000), "", "Files changed (" + p.files.length + "):"];
    p.files.forEach(f => { lines.push("- " + f.filename + " (+" + f.additions + " −" + f.deletions + ")"); if (f.patch) lines.push(f.patch.slice(0, 1500)); });
    if (p.comments.length) lines.push("", "Comments:", ...p.comments.map(c => "- " + c.user + ": " + short(c.body, 400)));
    return lines.join("\n");
  }
  function ghRepos(owner){
    const g = GH(); owner = str(owner).trim();
    const rows = g.repos.filter(r => !owner || r.full_name.split("/")[0].toLowerCase() === owner.toLowerCase());
    return rows.map(r => r.full_name + ": " + r.description + " · " + r.language + " · ★" + r.stars + " · " + r.open_issues + " open issues and pull requests · pushed " + agoText(r.days_ago)).join("\n") || "No projects.";
  }
  function ghSearch(query){
    query = str(query).trim(); if (!query) fail(tr("search_github needs something to search for."));
    const g = GH(), words = query.toLowerCase().split(/\s+/).filter(w => !w.includes(":"));
    const all = g.pulls.map(p => [p, "pull request"]).concat(g.issues.map(i => [i, "issue"]));
    return all.filter(([r]) => words.every(w => (r.title + " " + r.repo).toLowerCase().includes(w))).map(([r, k]) => ghLine(r, k)).join("\n") || "Nothing found for “" + query + "”.";
  }
  /* Branches, commits, files, new issues and labels, on the sample projects. Match the runtime's gh_branches, gh_commits,
     gh_read_file, gh_open_issue and gh_add_labels wording. */
  function ghBranches(repo){
    repo = ghRepo(repo); const g = GH();
    const rows = (g.branches || []).filter(b => b.repo === repo).sort((a, b) => b.days_ago - a.days_ago);
    return rows.map(b => { const pr = g.pulls.find(p => p.repo === repo && p.head === b.name);
      return b.name + " · last commit " + agoText(b.days_ago) + " by " + b.author + (b.name === (g.default_branch || "main") ? " · default branch" : "") + (pr ? " · open pull request #" + pr.number : ""); }).join("\n")
      || "No branches in " + repo + ".";
  }
  function ghSince(since){
    const s = str(since).trim().toLowerCase();
    if (["", "week", "last week"].includes(s)) return 7;
    if (s === "today") return 0;
    if (s === "yesterday") return 1;
    if (/^\d+( days?)?$/.test(s)) return parseInt(s, 10);
    if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return Math.max(0, (Date.now() - new Date(s + "T00:00:00Z").getTime()) / 86400000);
    return null;
  }
  function ghCommits(repo, author, since){
    repo = ghRepo(repo); const g = GH(); author = str(author).trim();
    if (["me", "@me"].includes(author.toLowerCase())) author = g.login;
    const days = ghSince(since);
    if (days === null) return "“" + str(since) + "” isn't a time to start from. Use today, yesterday, a number of days, or a date like 2026-10-01.";
    const rows = (g.commits || []).filter(c => c.repo === repo && (!author || c.author.toLowerCase() === author.toLowerCase()) && c.days_ago <= days + 1).sort((a, b) => a.days_ago - b.days_ago);
    return rows.map(c => c.sha.slice(0, 7) + " · " + agoText(c.days_ago) + " · " + c.author + ": " + short(c.message.split("\n")[0], 200)).join("\n")
      || "No commits in " + repo + (author ? " by " + author : "") + " in that time.";
  }
  function ghReadFile(repo, path, ref){
    repo = ghRepo(repo); path = str(path).trim().replace(/^\/+|\/+$/g, ""); ref = str(ref).trim();
    const files = (GH().files || {})[repo];
    if (!files) fail(tr("GitHub: not found, or the token can't see it."));
    const where = repo + "/" + path + (ref ? " at " + ref : "");
    if (files[path] !== undefined) {
      const text = files[path];
      return where + ":\n" + text.slice(0, MAX_FILE_CHARS) + (text.length > MAX_FILE_CHARS ? "\n\n(Only the first " + MAX_FILE_CHARS.toLocaleString("en") + " of " + text.length.toLocaleString("en") + " characters.)" : "");
    }
    const inside = [...new Set(Object.keys(files).filter(f => !path || f.startsWith(path + "/")).map(f => { const rest = path ? f.slice(path.length + 1) : f;
      return rest.includes("/") ? rest.split("/")[0] + "/" : rest; }))].sort();
    if (!inside.length) fail(tr("GitHub: not found, or the token can't see it."));
    return (path ? where : repo) + " is a folder:\n" + inside.join("\n");
  }
  async function ghOpenIssue(repo, title, body, approved){
    repo = ghRepo(repo); title = str(title).trim(); body = str(body).trim();
    if (!title) return "Not opened: an issue needs a title.";
    if (!approved && !(await allowed(["messages"], "open an issue in " + repo + ": " + short(title, 120)))) return "Not opened: the person said no.";
    const g = GH(), n = Math.max(0, ...g.pulls.concat(g.issues).filter(x => x.repo === repo).map(x => x.number)) + 1;
    g.issues.push({ repo, number:n, title, user:g.login, days_ago:0, state:"open", labels:[] });
    addStep(tr("GitHub issue opened in {repo}: #{n}", { repo, n }), { text:title + (body ? "\n\n" + body : "") }).done("sample", "ok");
    return "Opened " + repo + " #" + n + ": https://github.com/" + repo + "/issues/" + n;
  }
  async function ghAddLabels(repo, number, labels, approved){
    repo = ghRepo(repo); const n = Math.floor(num(number) + 0.5), g = GH();
    const want = (Array.isArray(labels) ? labels : str(labels).split(/\s*,\s*/)).map(x => str(x).trim()).filter(Boolean);
    if (!want.length) return "Not labelled: give at least one label.";
    const have = (g.labels || {})[repo] || [], lower = new Map(have.map(x => [x.toLowerCase(), x]));
    const unknown = want.filter(x => !lower.has(x.toLowerCase()));
    if (unknown.length) return "Not labelled: " + repo + " has no label " + unknown.join(", ") + ". Use only its own labels: " + (have.slice().sort().join(", ") || "(it has none)") + ".";
    const names = want.map(x => lower.get(x.toLowerCase()));
    if (!approved && !(await allowed(["messages"], "label " + repo + " #" + n + ": " + names.join(", ")))) return "Not labelled: the person said no.";
    const it = g.issues.concat(g.pulls).find(x => x.repo === repo && x.number === n);
    if (it) it.labels = [...new Set((it.labels || []).concat(names))];
    addStep(tr("GitHub labels on {repo} #{n}", { repo, n }), { text:names.join(", ") }).done("sample", "ok");
    return "Labelled " + repo + " #" + n + ": " + names.join(", ") + ".";
  }
  async function ghComment(repo, number, text, approved){
    repo = ghRepo(repo); const n = Math.floor(num(number) + 0.5); text = str(text).trim();
    if (!text) fail(tr("A comment needs some text."));
    if (!approved && !(await allowed(["messages"], "comment on " + repo + " #" + n + ": " + short(text, 120)))) return false;
    GH(); addStep(tr("GitHub comment on {repo} #{n}", { repo, n }), { text }).done("sample", "ok");
    return true;
  }
