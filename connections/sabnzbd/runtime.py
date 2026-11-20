    # SABnzbd (#397)
    # SABnzbd's API: SABNZBD_URL (like http://sabnzbd:8080) and SABNZBD_API_KEY, the full API key (Config, General,
    # API Key), not the NZB key. Reads are the modes in SAFETY["sabnzbd_free"]; pause and resume (sabnzbd_asks) always
    # ask, live, and never run with nobody there; nothing else is ever sent: no adding, deleting or retrying jobs, no
    # speedlimit, no config, no shutdown. SABNZBD_CERT_SHA256 pins a certificate this computer doesn't trust, as for
    # MikroTik and UniFi.
    SABNZBD_PAUSE = ("pause", "resume")

    async def _sabnzbd(self, mode, extra=None, approved=False):
        kind = sabnzbd_call("GET", mode)
        if kind is None or (kind == "asks" and not approved):
            raise RunError(tr("Second Thought doesn't send {what} to SABnzbd.", what=mode))
        base, key = os.environ.get("SABNZBD_URL", "").strip().rstrip("/"), os.environ.get("SABNZBD_API_KEY", "").strip()
        if not base or not key:
            raise RunError(tr("SABnzbd needs SABNZBD_URL and SABNZBD_API_KEY {where_keys}: its address (like http://sabnzbd:8080) and the full API key, in SABnzbd under Config, General, API Key.", where_keys=WHERE_KEYS))
        query = {"mode": mode, "output": "json", "apikey": key, **(extra or {})}
        status, raw = await self._pinned("SABnzbd", base, "SABNZBD_CERT_SHA256", "GET", "/api?" + urllib.parse.urlencode(query), {})
        said = json.loads(raw) if raw.strip() else {}
        if status >= 400 or (isinstance(said, dict) and said.get("status") is False):
            why = to_str(said.get("error")) if isinstance(said, dict) else ""
            raise RunError(tr("SABnzbd: {why}.", why=why or self._said(status, raw)))
        return said

    async def sabnzbd_queue(self):
        """What's in the queue now: a list of records, one for each job — name, size_mb, left_mb, percent, eta (time
        left, like 0:12:34) and status (Downloading, Queued, Paused). The log step says whether the whole queue is
        paused and how fast it's going."""
        q = (await self._sabnzbd("queue")).get("queue") or {}
        out = [{"name": to_str(s.get("filename")), "size_mb": self._cents(num(s.get("mb"))), "left_mb": self._cents(num(s.get("mbleft"))),
                "percent": self._cents(num(s.get("percentage"))), "eta": to_str(s.get("timeleft")) or "0:00:00",
                "status": to_str(s.get("status"))} for s in q.get("slots") or [] if isinstance(s, dict)]
        state = tr("Paused") if to_str(q.get("paused")).lower() == "true" or q.get("paused") is True else tr("Downloading")
        lines = "\n".join(f"{s['name']}: {s['left_mb']} MB left ({s['percent']}%)" for s in out)
        self.log(tr("SABnzbd queue"), (state + ", " + tr("{n} MB left", n=self._cents(num(q.get("mbleft"))))) + ("\n" + lines if lines else ""),
                 tr("{n} in the queue", n=len(out)))
        return out

    async def sabnzbd_history(self, hours=24):
        """What finished recently: a list of records, one for each job in the history — name, status (Completed or
        Failed), size_mb, when it finished and, for a failure, why it failed."""
        n = max(1, min(500, int(num(hours) or 24)))
        h = (await self._sabnzbd("history", {"limit": str(n * 10)})).get("history") or {}
        cutoff = time.time() - n * 3600
        out = []
        for s in h.get("slots") or []:
            if not isinstance(s, dict):
                continue
            when = num(s.get("completed"))
            if when and when < cutoff:
                continue
            out.append({"name": to_str(s.get("name")), "status": to_str(s.get("status")), "size_mb": self._cents(num(s.get("bytes")) / 1048576) if s.get("bytes") else "",
                        "when": datetime.datetime.fromtimestamp(when).strftime("%Y-%m-%d %H:%M") if when else "",
                        "why": to_str(s.get("fail_message")) if to_str(s.get("status")).lower() == "failed" else ""})
        out.reverse()  # oldest first, like the queue
        lines = "\n".join(f"{s['name']}: {s['status']}" for s in out)
        self.log(tr("SABnzbd history"), lines or tr("(nothing)"), tr("{n} finished", n=len(out)))
        return out

    async def sabnzbd_diskspace(self):
        """Each of SABnzbd's folders (the download folder first) and its free space in GB."""
        rows = (await self._sabnzbd("diskspace")).get("diskspace") or []
        out = [{"folder": to_str(r[0]), "free_gb": self._cents(num(r[1]))} for r in rows if isinstance(r, list) and len(r) >= 2]
        lines = "\n".join(f"{d['folder']}: {d['free_gb']} GB free" for d in out)
        self.log(tr("SABnzbd diskspace"), lines or tr("(nothing)"), tr("{n} folders", n=len(out)))
        return out

    async def sabnzbd_pause(self, action):
        """Pauses or resumes the whole queue, after asking you, every time. Gives back True if it was done."""
        action = to_str(action).strip().lower()
        if action not in self.SABNZBD_PAUSE:
            raise RunError(tr("SABnzbd can be paused or resumed."))
        q = (await self._sabnzbd("queue")).get("queue") or {}
        what = (tr("pause SABnzbd's queue") if action == "pause" else tr("resume SABnzbd's queue")) + \
            (f" ({self._cents(num(q.get('mbleft')))} MB left, {len(q.get('slots') or [])} in the queue)")
        if self._skip_action(what):
            return False
        if not await self.confirm_live(what):
            return False
        await self._sabnzbd("pause" if action == "pause" else "resume", approved=True)
        self.log(tr("SABnzbd"), what, tr("done"))
        return True
