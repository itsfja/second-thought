    # Radarr and Sonarr (#398)
    # The Servarr REST API, the same one both speak: RADARR_URL and RADARR_API_KEY, SONARR_URL and SONARR_API_KEY
    # (Settings, General, API Key in each). Reads are the paths in SAFETY["arr_free"]; the one search command
    # (arr_asks, its name checked against ARR_SEARCH) always asks, live, and never runs with nobody there; nothing
    # else is ever sent: no adding or deleting, no editing profiles or root folders, nothing in the indexer or
    # download-client settings. RADARR_CERT_SHA256 and SONARR_CERT_SHA256 pin a certificate this computer doesn't trust.
    ARR_URLS = {"radarr": ("RADARR_URL", "RADARR_API_KEY", "RADARR_CERT_SHA256", "Radarr"),
                "sonarr": ("SONARR_URL", "SONARR_API_KEY", "SONARR_CERT_SHA256", "Sonarr")}

    @staticmethod
    def _arr_which(which):
        w = to_str(which).strip().lower()
        if w not in Connections.ARR_URLS:
            raise RunError(tr("Which one? Radarr or Sonarr."))
        return w

    async def _arr(self, which, method, path, query=None, body=None, approved=False):
        w = self._arr_which(which)
        kind = arr_call(method, path)
        if kind is None or (kind == "asks" and not approved):
            raise RunError(tr("Second Thought doesn't send {what} to {who}.", what=f"{method} {path}", who=w.capitalize()))
        url, key, pin = (os.environ.get(n, "").strip() for n in self.ARR_URLS[w][:3])
        who = self.ARR_URLS[w][3]
        if not url or not key:
            raise RunError(tr("{who} needs {url_setting} and {key_setting} {where_keys}: its address (like http://radarr:7878) and its API key, under Settings, General, API Key.",
                              who=w.capitalize(), url_setting=self.ARR_URLS[w][0], key_setting=self.ARR_URLS[w][1], where_keys=WHERE_KEYS))
        full = path + ("?" + urllib.parse.urlencode(query) if query else "")
        status, raw = await self._pinned(w.capitalize(), url, pin, method, full, {"X-Api-Key": key}, body)
        if status == 401:
            raise RunError(tr("The {who} refused its API key.", who=who))
        if status >= 400:
            raise RunError(tr("{who}: {why}.", who=who, why=self._said(status, raw)))
        return json.loads(raw) if raw.strip() else {}

    async def arr_queue(self, which):
        """What's on its way: a list of records, one for each download in the queue — title, status (Downloading,
        Importing, Delaying, Failed, ...), size_mb, left_mb, quality and eta (time left, like 0:12:34)."""
        w = self._arr_which(which)
        q = (await self._arr(w, "GET", "/api/v3/queue", {"page": "1", "pageSize": "100"})).get("records") or []
        out = [{"title": to_str(r.get("title")), "status": to_str(r.get("status")),
                "size_mb": self._cents(num(r.get("size")) / 1048576) if r.get("size") else "",
                "left_mb": self._cents(num(r.get("sizeleft")) / 1048576) if r.get("sizeleft") is not None else "",
                "quality": to_str(((r.get("quality") or {}).get("quality") or {}).get("name") or ""),
                "eta": to_str(r.get("timeleft"))} for r in q if isinstance(r, dict)]
        lines = "\n".join(f"{r['title']}: {r['status']}" for r in out)
        self.log(tr("{who} queue", who=w.capitalize()), lines or tr("(nothing)"), tr("{n} downloading", n=len(out)))
        return out

    async def arr_missing(self, which):
        """What's still missing: a list of records, one for each movie or episode with no file — title, added (when it
        was added) and id."""
        w = self._arr_which(which)
        m = (await self._arr(w, "GET", "/api/v3/wanted/missing", {"page": "1", "pageSize": "100", "sortKey": "added", "sortDir": "desc"})).get("records") or []
        out = [{"title": to_str(r.get("title")), "added": to_str(r.get("added"))[:10], "id": num(r.get("id"))} for r in m if isinstance(r, dict)]
        lines = "\n".join(f"{r['title']} (added {r['added']})" for r in out)
        self.log(tr("{who} wanted list", who=w.capitalize()), lines or tr("(nothing)"), tr("{n} missing", n=len(out)))
        return out

    async def arr_diskspace(self, which):
        """Each of its folders: path, label, free_gb and total_gb."""
        w = self._arr_which(which)
        rows = await self._arr(w, "GET", "/api/v3/diskspace")
        out = [{"path": to_str(r.get("path")), "label": to_str(r.get("label")),
                "free_gb": self._cents(num(r.get("freeSpace")) / 1073741824) if r.get("freeSpace") else "",
                "total_gb": self._cents(num(r.get("totalSpace")) / 1073741824) if r.get("totalSpace") else ""}
               for r in rows if isinstance(r, dict)]
        lines = "\n".join(f"{d['label']}: {d['free_gb']} GB free" for d in out)
        self.log(tr("{who} diskspace", who=w.capitalize()), lines or tr("(nothing)"), tr("{n} folders", n=len(out)))
        return out

    async def arr_search(self, which):
        """Searches for everything on the wanted list with no file, after asking you, every time. Gives back True if it
        was done."""
        w = self._arr_which(which)
        what = tr("search {who}'s wanted list for what's missing", who=w.capitalize())
        if self._skip_action(what):
            return False
        if not await self.confirm_live(what):
            return False
        await self._arr(w, "POST", "/api/v3/command", body={"name": ARR_SEARCH[w]}, approved=True)
        self.log(w.capitalize(), what, tr("done"))
        return True
