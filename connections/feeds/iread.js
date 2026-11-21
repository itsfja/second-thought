      case "rb_feed_news": {
        const url = str(await input(b, tc, "URL")).trim();
        const items = sampleFeedItems(url, 10);
        const recs = items.map(i => ({ feed:i.feed, title:i.title, link:i.link, date:whenText(i.date), summary:i.summary }));
        addStep(tr("News: {feed}", { feed:short(url, 60) || tr("your feeds") }), { mono:true, text:recs.slice(0, 12).map(r => r.date + "  " + r.title).join("\n") || tr("(nothing)") }).done(tr("{n} items", { n:recs.length }), "ok");
        return recs;
      }
