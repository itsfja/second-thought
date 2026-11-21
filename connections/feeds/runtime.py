    MAX_FEED_ITEMS = 10

    async def feed_items(self, url="", limit=10, trusted=False):
        """Items from one feed, or from every feed in your settings (feeds = ...) when url is empty."""
        url = to_str(url).strip()
        mine = [u for u in re.split(r"[\s,]+", os.environ.get("RB_FEEDS", "")) if u]
        urls = [url] if url else mine
        if not urls:
            raise RunError(tr("No feed given, and no feeds in your settings. Add  feeds = <addresses>  {where_keys}.", where_keys=WHERE_KEYS))
        limit = max(1, min(50, round_js(num(limit)) or self.MAX_FEED_ITEMS))
        out = []
        for u in urls:
            ctype, data = await asyncio.to_thread(get_url, u, trusted or u in mine, "read_feed", 5_000_000)
            title, items = parse_feed(data)
            for it in items[:limit]:
                out.append(dict(it, feed=title or u))
        return out

    async def feed_records(self, url):
        """For the 'news from feed' block: a list of records (feed, title, link, date, summary)."""
        items = await self.feed_items(url)
        recs = [{"feed": i["feed"], "title": i["title"], "link": i["link"], "date": _when(i["date"]) if i["date"] else "",
                 "summary": i["summary"]} for i in items]
        self.log(tr("News: {x}", x=_short(url, 60) or tr("your feeds")), "\n".join(f"{r['date']}  {r['title']}" for r in recs[:12]) or tr("(nothing)"),
                 tr("{recs} items", recs=len(recs)))
        return recs

    @staticmethod
    def feed_text(items):
        lines, feed = [], None
        for i in items:
            if i["feed"] != feed:
                feed = i["feed"]
                lines.append(("\n" if lines else "") + feed)
            lines.append(f"- {_when(i['date']) if i['date'] else '(no date)'}  {i['title']}" + (f"\n  {i['link']}" if i["link"] else "")
                         + (f"\n  {i['summary']}" if i["summary"] else ""))
        return "\n".join(lines) or "The feed has no items."

    async def _listen_feed(self, items):
        seen = {}
        while True:
            for url, fn in items:
                try:
                    got = await self.feed_items(url, 30, trusted=True)
                except RunError as e:
                    print(tr("  (Feed check failed: {e})", e=e), flush=True)
                    continue
                keys = {i["link"] or i["title"] for i in got}
                if url in seen:
                    for i in reversed(got):  # oldest first
                        if (i["link"] or i["title"]) not in seen[url]:
                            rec = {"feed": i["feed"], "title": i["title"], "link": i["link"], "date": _when(i["date"]) if i["date"] else "",
                                   "summary": i["summary"], "text": f"{i['title']}\n{i['summary']}\n{i['link']}".strip()}
                            self._fire(fn, rec, tr("New in {feed}", feed=_short(i["feed"], 40)))
                    seen[url] |= keys
                else:
                    seen[url] = keys
            await asyncio.sleep(self._poll(900))
