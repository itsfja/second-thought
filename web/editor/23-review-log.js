  // 23-review-log.js: the run log's second thought (#449) — the review loop's rounds as a strip, what each revision
  // changed as a +/− diff, and results rendered as Markdown, safely.
  /* ---------- Markdown in results, rendered safely ----------
     markdownHtml turns model text into HTML where every character of the model's text is escaped before anything
     else, so the only tags in the output are the ones this function emits; links keep only http(s) addresses. The
     tests feed it script and link injection. */
  function escapeHtml(s){ return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
  function markdownInline(raw){
    let s = String(raw == null ? "" : raw);
    const stash = [];
    const keep = html => { stash.push(html); return "\u0000" + (stash.length - 1) + "\u0000"; };
    // links [text](url): only http/https addresses become anchors; anything else is shown as written
    s = s.replace(/\[([^\]]*)\]\(([^)\s]*)(?:\s+["'][^"']*["'])?\)/g, (m, text, url) => {
      if (!/^https?:\/\//i.test(url)) return escapeHtml(m);
      return keep('<a href="' + escapeHtml(url) + '" target="_blank" rel="noopener noreferrer">' + markdownInline(text) + "</a>");
    });
    // code spans `...` (no inline markdown inside them)
    s = s.replace(/`([^`]+)`/g, (m, c) => keep("<code>" + escapeHtml(c) + "</code>"));
    s = escapeHtml(s);
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/\*([^*\n]+)\*/g, "<em>$1</em>");
    s = s.replace(/__([^_]+)__/g, "<strong>$1</strong>");
    // stashed html survives escaping (\u0000 is not escaped) and goes back in last
    s = s.replace(/\u0000(\d+)\u0000/g, (m, i) => stash[+i]);
    return s;
  }
  function markdownHtml(text){
    const lines = String(text == null ? "" : text).replace(/\r\n?/g, "\n").split("\n");
    const out = [];
    let para = [], i = 0;
    // the "\n" after <br>/<p> is a text node: it collapses in rendering (white-space:normal) but keeps textContent
    // identical to the raw Markdown, so Copy-as-text and the tests see the same text either way
    const flushPara = () => { if (para.length) { out.push("<p>" + para.map(markdownInline).join("<br>\n") + "</p>"); para = []; } };
    while (i < lines.length) {
      const line = lines[i];
      if (/^\s*```/.test(line)) {  // fenced code block
        flushPara();
        const buf = []; i++;
        while (i < lines.length && !/^\s*```/.test(lines[i])) { buf.push(lines[i]); i++; }
        i++;
        out.push("<pre><code>" + escapeHtml(buf.join("\n")) + "</code></pre>");
        continue;
      }
      const h = /^(#{1,6})\s+(.*)$/.exec(line);
      if (h) { flushPara(); out.push("<h" + h[1].length + ">" + markdownInline(h[2]) + "</h" + h[1].length + ">"); i++; continue; }
      if (/^\s*>\s?/.test(line)) {  // blockquote
        flushPara();
        const buf = [];
        while (i < lines.length && /^\s*>\s?/.test(lines[i])) { buf.push(lines[i].replace(/^\s*>\s?/, "")); i++; }
        out.push("<blockquote>" + markdownHtml(buf.join("\n")) + "</blockquote>");
        continue;
      }
      if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1])) {  // table
        flushPara();
        const cells = l => l.trim().replace(/^\||\|$/g, "").split("|");
        const head = cells(line);
        i += 2;
        const rows = [];
        while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) { rows.push(cells(lines[i])); i++; }
        out.push("<table><thead><tr>" + head.map(c => "<th>" + markdownInline(c.trim()) + "</th>").join("") + "</tr></thead><tbody>" +
          rows.map(r => "<tr>" + r.map(c => "<td>" + markdownInline(c.trim()) + "</td>").join("") + "</tr>").join("") + "</tbody></table>");
        continue;
      }
      if (/^\s*(?:[-*+]|\d+\.)\s+/.test(line)) {  // list
        flushPara();
        const ol = /^\s*\d+\./.test(line);
        const items = [];
        while (i < lines.length && /^\s*(?:[-*+]|\d+\.)\s+/.test(lines[i])) { items.push(lines[i].replace(/^\s*(?:[-*+]|\d+\.)\s+/, "")); i++; }
        out.push("<" + (ol ? "ol" : "ul") + ">" + items.map(x => "<li>" + markdownInline(x) + "</li>").join("") + "</" + (ol ? "ol" : "ul") + ">");
        continue;
      }
      if (/^\s*$/.test(line)) { flushPara(); i++; continue; }
      para.push(line); i++;
    }
    flushPara();
    return out.join("\n\n");  // blank line between blocks, so textContent keeps the raw newlines
  }
  function renderMarkdownInto(el, text){ el.innerHTML = markdownHtml(text); }  // safe: all model text was escaped
  window.__markdownHtml = markdownHtml;

  /* ---------- What each revision changed: a line diff (#449) ---------- */
  function diffLines(a, b){
    const split = s => { const l = String(s == null ? "" : s).split("\n"); return l.length === 1 && l[0] === "" ? [] : l; };
    const A = split(a), B = split(b);
    const n = A.length, m = B.length;
    if (n * m > 250000)  // too big for the table: show it as removed then added
      return A.map(t => ({ type:"del", text:t })).concat(B.map(t => ({ type:"add", text:t })));
    const dp = Array.from({ length:n + 1 }, () => new Uint32Array(m + 1));
    for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--)
      dp[i][j] = A[i] === B[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    const out = [];
    let i = 0, j = 0;
    while (i < n && j < m) {
      if (A[i] === B[j]) { out.push({ type:"same", text:A[i] }); i++; j++; }
      else if (dp[i + 1][j] >= dp[i][j + 1]) { out.push({ type:"del", text:A[i] }); i++; }
      else { out.push({ type:"add", text:B[j] }); j++; }
    }
    while (i < n) out.push({ type:"del", text:A[i++] });
    while (j < m) out.push({ type:"add", text:B[j++] });
    return out;
  }
  window.__diffLines = diffLines;

  /* ---------- The review loop's rounds as a strip (#449) ---------- */
  function renderRoundsStrip(el, loop){
    el.innerHTML = "";
    (loop.rounds || []).forEach(r => {
      const total = r.verdicts.length, met = r.verdicts.filter(v => v.met).length;
      const chip = document.createElement("span");
      chip.className = "round-chip " + (met === total ? "ok" : "warn");
      chip.textContent = tr("Round {n}", { n:r.round }) + " · " + (met === total ? tr("approved") : tr("{n} problems", { n:total - met }));
      el.appendChild(chip);
    });
  }
