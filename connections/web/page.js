  /* 'when the web page … changes': the part to watch, and what changed. Match the runtime's page_part and page_changes. */
  function pagePart(text, words){
    const ws = str(words).toLowerCase().split(/\s+/).filter(Boolean);
    if (!ws.length) return text;
    const lines = String(text).split(/\r?\n/), keep = new Set();
    lines.forEach((l, i) => { if (ws.every(w => l.toLowerCase().includes(w))) for (let k = i; k < Math.min(lines.length, i + 3); k++) keep.add(k); });
    return [...keep].sort((a, b) => a - b).map(i => lines[i]).join("\n");
  }
  function pageChanges(before, after, limit){
    limit = limit || 20;
    const a = String(before).split("\n"), c = String(after).split("\n"), n = a.length, m = c.length;
    const L = Array.from({ length:n + 1 }, () => new Array(m + 1).fill(0));  // longest common lines, then walk it
    for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) L[i][j] = a[i] === c[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
    const out = []; let i = 0, j = 0, gone = [], fresh = [];
    const flush = () => {  // lines replaced together are paired: - old, + new
      for (let k = 0; k < Math.max(gone.length, fresh.length); k++) {
        if (k < gone.length && gone[k].trim()) out.push("- " + short(gone[k], 200));
        if (k < fresh.length && fresh[k].trim()) out.push("+ " + short(fresh[k], 200));
      }
      gone = []; fresh = [];
    };
    while (i < n || j < m) {
      if (i < n && j < m && a[i] === c[j]) { flush(); i++; j++; }
      else if (i < n && (j >= m || L[i + 1][j] >= L[i][j + 1])) gone.push(a[i++]);
      else fresh.push(c[j++]);
    }
    flush();
    return out.slice(0, limit).join("\n") + (out.length > limit ? "\n\u2026 and " + (out.length - limit) + " more changed lines" : "");
  }
