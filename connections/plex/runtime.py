    # Plex and Tautulli (#402)
    # Plex's HTTP API (the X-Plex-Token endpoints the apps use), PLEX_URL (like http://plex:32400) and PLEX_TOKEN (the
    # token the apps send, from a device's account details). The server, the libraries, the sessions and the newest
    # items are reads (plex_free); scanning a library (plex_asks) always asks, live, and never runs with nobody there.
    # Tautulli (TAUTULLI_URL and TAUTULLI_API_KEY, from Settings, API Keys) adds the history and the watch-time stats
    # (tautulli_free) and the one way to stop a stream (tautulli_asks), which always asks too. Nothing else is ever
    # sent: no media or library is ever deleted, no sharing, no user access, no transcoding or remote-access settings.
    # PLEX_CERT_SHA256 and TAUTULLI_CERT_SHA256 pin certificates this computer doesn't trust.
    async def _plex(self, method, path, query=None, approved=False):
        """One request to Plex's API, gated by plex_call: the server, the libraries, the sessions and the newest
        items go without asking, the one scan only after a live yes, and anything else is never sent."""
        kind = plex_call(method, path)
        if kind is None or (kind == "asks" and not approved):
            raise RunError(tr("Second Thought doesn't send {what} to {who}.", what=f"{method} {path}", who="Plex"))
        base = os.environ.get("PLEX_URL", "").strip().rstrip("/")
        token = os.environ.get("PLEX_TOKEN", "").strip()
        if not base or not token:
            raise RunError(tr("{who} needs {url_setting} and {key_setting} {where_keys}: its address (like http://plex:32400) and its token, the one the apps send (a device's account details show it).",
                              url_setting="PLEX_URL", key_setting="PLEX_TOKEN", where_keys=WHERE_KEYS))
        whole = path + (("?" + urllib.parse.urlencode(query)) if query else "")
        status, raw = await self._pinned("Plex", base, "PLEX_CERT_SHA256", method, whole,
                                         {"X-Plex-Token": token, "Accept": "application/json"})
        if status == 401:
            raise RunError(tr("The {who} refused its token.", who="Plex"))
        if status >= 400:
            raise RunError(tr("{who}: {why}.", who="Plex", why=self._said(status, raw)))
        answer = json.loads(raw) if raw.strip() else {}
        return answer.get("MediaContainer") or {} if isinstance(answer, dict) else {}

    async def plex_server(self):
        """One record for the server: name, version and up (it answered, so it's up)."""
        c = await self._plex("GET", "/")
        out = {"name": to_str(c.get("friendlyName")), "version": to_str(c.get("version")), "up": True}
        self.log(tr("Plex server"), tr("Plex {version}", version=out["version"]), tr("up"))
        return out

    async def plex_libraries(self):
        """The libraries: a list of records — name, type (movie, show or artist) and count (how many items)."""
        c = await self._plex("GET", "/library/sections")
        out = []
        for d in c.get("Directory") or []:
            if not isinstance(d, dict):
                continue
            key = to_str(d.get("key"))
            items = await self._plex("GET", f"/library/sections/{key}/all") if key.isdigit() else {}
            out.append({"name": to_str(d.get("title")), "type": to_str(d.get("type")), "count": num(items.get("size"))})
        lines = "\n".join(f"{r['name']}: {r['count']}" for r in out)
        self.log(tr("Plex libraries"), lines or tr("(nothing)"), tr("{n} libraries", n=len(out)))
        return out

    async def plex_sessions(self):
        """What's playing now: a list of records — id (the session's id), user, title, player, state (playing or
        paused) and transcode (whether the server is transcoding it)."""
        c = await self._plex("GET", "/status/sessions")
        out = []
        for v in (c.get("Video") or []) + (c.get("Metadata") or []):
            if not isinstance(v, dict) or not v.get("sessionKey"):
                continue
            title = to_str(v.get("title"))
            show = to_str(v.get("grandparentTitle"))
            out.append({"id": to_str(v.get("sessionKey")), "user": to_str((v.get("User") or {}).get("title")),
                        "title": f"{show} - {title}" if show else title,
                        "player": to_str((v.get("Player") or {}).get("title")),
                        "state": to_str((v.get("Player") or {}).get("state")),
                        "transcode": bool(v.get("TranscodeSession"))})
        lines = "\n".join(f"{r['user']}: {r['title']} ({r['state']})" for r in out)
        self.log(tr("Plex sessions"), lines or tr("(nothing)"), tr("{n} sessions", n=len(out)))
        return out

    async def plex_recent(self, days=7):
        """The newest items: a list of records — title, library and added (when it was added)."""
        n = max(1, min(365, int(num(days) or 7)))
        c = await self._plex("GET", "/library/recentlyAdded")
        cutoff = time.time() - n * 86400
        out = []
        for m in c.get("Metadata") or []:
            if not isinstance(m, dict):
                continue
            added = num(m.get("addedAt"))
            if added and added < cutoff:
                continue
            title = to_str(m.get("title"))
            show = to_str(m.get("grandparentTitle"))
            out.append({"title": f"{show} - {title}" if show else title,
                        "library": to_str(m.get("librarySectionTitle")),
                        "added": datetime.datetime.fromtimestamp(added).strftime("%Y-%m-%d %H:%M") if added else ""})
        lines = "\n".join(f"{r['title']} ({r['library']})" for r in out)
        self.log(tr("Plex new items"), lines or tr("(nothing)"), tr("{n} items", n=len(out)))
        return out

    async def plex_scan(self, library):
        """Scans one library for new files, after asking you, every time. Gives back True if it was done."""
        name = to_str(library).strip()
        if not name:
            raise RunError(tr("Which library? Give its name, from the libraries."))
        c = await self._plex("GET", "/library/sections")
        key, found = "", ""
        for d in c.get("Directory") or []:
            if isinstance(d, dict) and to_str(d.get("title")).strip().lower() == name.lower():
                key, found = to_str(d.get("key")), to_str(d.get("title"))
        if not key.isdigit():
            raise RunError(tr("Which library? Give its name, from the libraries."))
        what = tr("scan the {library} library on Plex", library=found)
        if self._skip_action(what):
            return False
        if not await self.confirm_live(what):
            return False
        await self._plex("GET", f"/library/sections/{key}/refresh", approved=True)
        self.log(tr("Plex"), what, tr("done"))
        return True

    async def _tautulli(self, cmd, params=None, approved=False):
        """One request to Tautulli's API, gated by tautulli_call on the query as a whole: the history goes without
        asking, the one terminate only after a live yes, and anything else is never sent."""
        gate = "cmd=" + cmd + (("&" + urllib.parse.urlencode(params)) if params else "")
        kind = tautulli_call("GET", gate)
        if kind is None or (kind == "asks" and not approved):
            raise RunError(tr("Second Thought doesn't send {what} to {who}.", what=gate, who="Tautulli"))
        base = os.environ.get("TAUTULLI_URL", "").strip().rstrip("/")
        api_key = os.environ.get("TAUTULLI_API_KEY", "").strip()
        if not base or not api_key:
            raise RunError(tr("Tautulli needs {url_setting} and {key_setting} {where_keys}: its address (like http://tautulli:8181) and its API key (Settings, API Keys).",
                              url_setting="TAUTULLI_URL", key_setting="TAUTULLI_API_KEY", where_keys=WHERE_KEYS))
        status, raw = await self._pinned("Tautulli", base, "TAUTULLI_CERT_SHA256", "GET", "/api/v2?" + gate + "&api_key=" + api_key, {})
        if status == 401:
            raise RunError(tr("The {who} refused its key.", who="Tautulli"))
        if status >= 400:
            raise RunError(tr("{who}: {why}.", who="Tautulli", why=self._said(status, raw)))
        answer = json.loads(raw) if raw.strip() else {}
        return ((answer or {}).get("response") or {}) if isinstance(answer, dict) else {}

    async def _tautulli_history(self, days):
        """Tautulli's history rows, newest first, as (columns, rows)."""
        n = max(1, min(365, int(num(days) or 7)))
        r = await self._tautulli("get_history", {"after": datetime.datetime.fromtimestamp(time.time() - n * 86400).strftime("%Y-%m-%d"),
                                                 "length": "100"})
        data = (r.get("data") or {}) if isinstance(r.get("data"), dict) else {}
        cols = [to_str(c) for c in (data.get("columns") or [])]
        rows = [row for row in (data.get("data") or []) if isinstance(row, list)]
        return cols, rows

    async def tautulli_history(self, days=7):
        """What was watched: a list of records — user, title, when and transcode (whether it was transcoded)."""
        cols, rows = await self._tautulli_history(days)
        at = lambda name: cols.index(name) if name in cols else -1  # noqa: E731
        def g(row, name):
            i = at(name)
            return row[i] if 0 <= i < len(row) else None
        out = []
        for row in rows:
            when = num(g(row, "date"))
            out.append({"user": to_str(g(row, "user")), "title": to_str(g(row, "full_title") or g(row, "title")),
                        "when": datetime.datetime.fromtimestamp(when).strftime("%Y-%m-%d %H:%M") if when else "",
                        "transcode": to_str(g(row, "transcode_decision")).lower() == "transcode"})
        lines = "\n".join(f"{r['user']}: {r['title']}" for r in out)
        self.log(tr("Tautulli history"), lines or tr("(nothing)"), tr("{n} plays", n=len(out)))
        return out

    async def tautulli_watchtime(self, days=7):
        """How long each person watched: a list of records — user and hours."""
        cols, rows = await self._tautulli_history(days)
        at = lambda name: cols.index(name) if name in cols else -1  # noqa: E731
        def g(row, name):
            i = at(name)
            return row[i] if 0 <= i < len(row) else None
        seen = {}
        for row in rows:
            user = to_str(g(row, "user"))
            seen[user] = seen.get(user, 0) + num(g(row, "duration"))
        out = [{"user": u, "hours": self._cents(s / 3600)} for u, s in sorted(seen.items(), key=lambda kv: -kv[1])]
        lines = "\n".join(f"{r['user']}: {r['hours']}" for r in out)
        self.log(tr("Tautulli watch time"), lines or tr("(nothing)"), tr("{n} users", n=len(out)))
        return out

    async def plex_stop(self, session):
        """Stops one stream (Tautulli's terminate), after asking you, every time. Gives back True if it was done."""
        key = to_str(session).strip()
        if not key:
            raise RunError(tr("Which stream? Give a session's id, from the sessions."))
        what = tr("stop the {id} stream on Plex", id=key)
        if self._skip_action(what):
            return False
        if not await self.confirm_live(what):
            return False
        r = await self._tautulli("terminate_session", {"session_key": key}, approved=True)
        if to_str(r.get("result")).lower() != "success":
            raise RunError(tr("{who}: {why}.", who="Tautulli", why=self._said(400, to_str(r.get("message") or ""))))
        self.log(tr("Plex"), what, tr("done"))
        return True
