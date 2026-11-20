    # NZBGeek (#400)
    # NZBGeek's Newznab API: NZBGEEK_API_KEY (My Account, API key) and, if it ever moves, NZBGEEK_URL (the default is
    # https://api.nzbgeek.info). The searches and t=caps are reads (nzbgeek_free); the one fetch (t=get, an NZB file,
    # with a paid account's key) always asks, live, and never runs with nobody there. Nothing else is ever sent: no
    # account changes, no VIP time, no payments, and a search that smuggles t=get is refused.
    NZBGEEK_URL = "https://api.nzbgeek.info"

    async def _nzbgeek(self, params, approved=False):
        """One GET to NZBGeek's /api, gated by nzbgeek_call: a search or t=caps goes without asking, the one fetch
        only after a live yes, and anything else is never sent."""
        kind = nzbgeek_call("GET", urllib.parse.urlencode(params))
        if kind is None or (kind == "asks" and not approved):
            raise RunError(tr("Second Thought doesn't send {what} to {who}.",
                              what="GET /api?" + urllib.parse.urlencode({k: v for k, v in params.items() if k != "apikey"}), who="NZBGeek"))
        key = os.environ.get("NZBGEEK_API_KEY", "").strip()
        if not key:
            raise RunError(tr("{who} needs {url_setting} and {key_setting} {where_keys}: its API key, in NZBGeek under My Account, API key.",
                              who="NZBGeek", url_setting="NZBGEEK_URL", key_setting="NZBGEEK_API_KEY", where_keys=WHERE_KEYS))
        url = (os.environ.get("NZBGEEK_URL", "").strip() or self.NZBGEEK_URL).rstrip("/")
        status, raw = await self._pinned("NZBGeek", url, "NZBGEEK_CERT_SHA256", "GET",
                                        "/api?" + urllib.parse.urlencode(dict(params, apikey=key)), {})
        if status == 401:
            raise RunError(tr("The {who} refused its API key.", who="NZBGeek"))
        if status >= 400:
            raise RunError(tr("{who}: {why}.", who="NZBGeek", why=self._said(status, raw)))
        return raw

    @staticmethod
    def _nzbgeek_attrs(item):
        """A release's Newznab attributes, whatever shape the answer gives them: name to value."""
        out = {}
        for a in (item.get("newznab:attr") or []) if isinstance(item, dict) else []:
            a = a.get("@attributes") if isinstance(a, dict) and "@attributes" in a else a
            if isinstance(a, dict) and a.get("name") is not None:
                out[to_str(a.get("name"))] = to_str(a.get("value"))
        return out

    async def nzbgeek_search(self, query):
        """What the indexer has for these words: a list of records — title, id, size_mb, grabs, posted (when it was
        posted) and group. It only reads: nothing is ever downloaded."""
        q = to_str(query).strip()
        raw = await self._nzbgeek({"t": "search", "q": q, "o": "json"})
        answer = json.loads(raw) if raw.strip() else {}
        items = ((answer.get("channel") or {}).get("item")) or []
        if isinstance(items, dict):
            items = [items]
        out = []
        for item in items:
            if not isinstance(item, dict):
                continue
            a = self._nzbgeek_attrs(item)
            out.append({"title": to_str(item.get("title")),
                        "id": to_str(item.get("guid")).rsplit("/", 1)[-1] if item.get("guid") else "",
                        "size_mb": self._cents(num(a.get("size")) / 1048576) if a.get("size") else "",
                        "grabs": num(a.get("grabs")) if a.get("grabs") else "",
                        "posted": (a.get("usenetdate") or to_str(item.get("pubDate")))[:16],
                        "group": a.get("group", "")})
        lines = "\n".join(f"{r['title']} ({r['size_mb']} MB)" if r["size_mb"] else r["title"] for r in out)
        self.log(tr("NZBGeek search for {q}", q=q), lines or tr("(nothing)"), tr("{n} found", n=len(out)))
        return out

    async def nzbgeek_fetch(self, ident):
        """Fetches one NZB file and saves it as <id>.nzb, after asking you, every time. Gives back True if it was
        done. It never hands anything to a downloader: the file is saved, that's all."""
        n = to_str(ident).strip().rsplit("/", 1)[-1]
        if not n:
            raise RunError(tr("Which one? Give a release's id, from the search."))
        what = tr("fetch the NZB for {id} from NZBGeek", id=n)
        if self._skip_action(what):
            return False
        if not await self.confirm_live(what):
            return False
        raw = await self._nzbgeek({"t": "get", "id": n}, approved=True)
        await self.save_file(raw, n, "nzb")
        self.log(tr("NZBGeek"), what, tr("done"))
        return True
