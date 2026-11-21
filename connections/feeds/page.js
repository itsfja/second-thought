  function sampleFeedItems(url, limit){
    url = str(url).trim(); limit = Math.max(1, Math.min(50, Math.floor(num(limit) + 0.5) || 10));
    const feeds = CONN.feeds || {}, urls = url ? [url] : Object.keys(feeds);
    connNote("News feeds");
    const out = [];
    urls.forEach(u => {
      const f = feeds[u];
      if (!f) fail(tr("This page can't open {u}, so it only has its sample feeds: {feeds}. Exported Python reads any feed.", { u:short(u, 80), feeds:Object.keys(feeds).join(", ") }));
      f.items.slice().sort((a, b) => a.hours_ago - b.hours_ago).slice(0, limit).forEach(it => out.push({ feed:f.title, title:it.title, link:it.link, date:hoursAgo(it.hours_ago), summary:it.summary }));
    });
    return out;
  }
  function feedText(items){
    const lines = []; let feed = null;
    items.forEach(i => {
      if (i.feed !== feed) { feed = i.feed; lines.push((lines.length ? "\n" : "") + feed); }
      lines.push("- " + whenText(i.date) + "  " + i.title + (i.link ? "\n  " + i.link : "") + (i.summary ? "\n  " + i.summary : ""));
    });
    return lines.join("\n") || "The feed has no items.";
  }
