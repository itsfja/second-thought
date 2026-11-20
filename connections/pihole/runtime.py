    # Pi-hole (#401)
    # Pi-hole's REST API (v6 and later): PIHOLE_URL (like http://pi.hole) and PIHOLE_PASSWORD (the web interface's
    # password). Each run signs in once (POST /api/auth) and carries the session id; the stats and the blocking
    # status are reads (pihole_free); disabling or enabling blocking, and adding or removing a domain on the allow
    # or deny list (pihole_asks) always ask, live, and never run with nobody there. Nothing else is ever sent: no
    # upstream DNS, no DHCP, no web password, no network settings. PIHOLE_CERT_SHA256 pins a certificate this
    # computer doesn't trust.
    async def _pihole_auth(self):
        """Signs in once and keeps the session id for the run."""
        if getattr(self, "_pihole_sid", None):
            return self._pihole_sid
        url = os.environ.get("PIHOLE_URL", "").strip()
        password = os.environ.get("PIHOLE_PASSWORD", "").strip()
        if not url or not password:
            raise RunError(tr("{who} needs {url_setting} and {key_setting} {where_keys}: its address (like http://pi.hole) and its web interface's password.",
                              who="Pi-hole", url_setting="PIHOLE_URL", key_setting="PIHOLE_PASSWORD", where_keys=WHERE_KEYS))
        status, raw = await self._pinned("Pi-hole", url, "PIHOLE_CERT_SHA256", "POST", "/api/auth",
                                         {"Content-Type": "application/json"}, {"password": password})
        answer = json.loads(raw) if raw.strip() else {}
        session = (answer.get("session") or {}) if isinstance(answer, dict) else {}
        if status >= 400 or not session.get("sid"):
            raise RunError(tr("The {who} refused its password.", who="Pi-hole"))
        self._pihole_sid = session["sid"]
        return self._pihole_sid

    async def _pihole(self, method, path, body=None, approved=False, reauth=True, query=None):
        """One request to Pi-hole's API, signed in and gated by pihole_call: the stats and the blocking status go
        without asking, the few changes only after a live yes, and anything else is never sent. The query string is
        kept out of the gate: it only ever narrows a read."""
        kind = pihole_call(method, path)
        if kind is None or (kind == "asks" and not approved):
            raise RunError(tr("Second Thought doesn't send {what} to {who}.", what=f"{method} {path}", who="Pi-hole"))
        sid = await self._pihole_auth()
        whole = path + (("?" + urllib.parse.urlencode(query)) if query else "")
        status, raw = await self._pinned("Pi-hole", os.environ.get("PIHOLE_URL", "").strip(), "PIHOLE_CERT_SHA256",
                                        method, whole, {"X-FTL-SID": sid}, body)
        if status == 401 and reauth:  # the session ran out: sign in again and try once more
            self._pihole_sid = None
            return await self._pihole(method, path, body, approved, reauth=False, query=query)
        if status >= 400:
            raise RunError(tr("{who}: {why}.", who="Pi-hole", why=self._said(status, raw)))
        answer = json.loads(raw) if raw.strip() else {}
        if isinstance(answer, dict) and answer.get("error"):
            raise RunError(tr("{who}: {why}.", who="Pi-hole", why=_short(to_str((answer["error"] or {}).get("message") or ""), 120)))
        return answer

    async def pihole_summary(self):
        """One record for today: queries (how many DNS queries), blocked (how many were blocked), blocked_pct (the
        blocked share), gravity (how many domains the lists have), clients (how many devices asked) and blocking
        (whether blocking is on)."""
        s = await self._pihole("GET", "/api/stats/summary")
        blocking = await self._pihole("GET", "/api/dns/blocking")
        q = (s.get("queries") or {})
        out = {"queries": num(q.get("total")), "blocked": num(q.get("blocked")),
               "blocked_pct": num(q.get("percent")),
               "gravity": num((s.get("gravity") or {}).get("domains")),
               "clients": num((s.get("clients") or {}).get("total")),
               "blocking": bool((blocking or {}).get("blocking"))}
        on = out["blocking"]
        self.log(tr("Pi-hole summary"),
                 tr("{queries} queries, {blocked} blocked ({blocked_pct} %)", **out) + ", "
                 + (tr("blocking on") if on else tr("blocking off")))
        return out

    async def pihole_top_domains(self, count=5):
        """The most-blocked domains: a list of records — domain and count (how many times it was blocked)."""
        d = await self._pihole("GET", "/api/stats/top_domains", query={"blocked": "true", "count": str(num(count) or 5)})
        rows = d.get("domains") or []
        out = [{"domain": to_str(r.get("domain")), "count": num(r.get("count"))} for r in rows if isinstance(r, dict)]
        lines = "\n".join(f"{r['domain']}: {r['count']}" for r in out)
        self.log(tr("Pi-hole top blocked domains"), lines or tr("(nothing)"), tr("{n} domains", n=len(out)))
        return out

    async def pihole_top_clients(self, count=5):
        """The devices that asked the most: a list of records — name, ip and count (how many queries)."""
        c = await self._pihole("GET", "/api/stats/top_clients", query={"count": str(num(count) or 5)})
        rows = c.get("clients") or []
        out = [{"name": to_str(r.get("name") or r.get("ip")), "ip": to_str(r.get("ip")), "count": num(r.get("count"))}
               for r in rows if isinstance(r, dict)]
        lines = "\n".join(f"{r['name']}: {r['count']}" for r in out)
        self.log(tr("Pi-hole top clients"), lines or tr("(nothing)"), tr("{n} clients", n=len(out)))
        return out

    async def pihole_blocking(self, seconds):
        """Disables blocking for that many seconds, after asking you, every time. Gives back True if it was done."""
        n = num(seconds)
        if not n or n <= 0:
            raise RunError(tr("For how long? Give the seconds blocking should be off, like 60."))
        what = tr("disable Pi-hole's blocking for {n} seconds", n=n)
        if self._skip_action(what):
            return False
        if not await self.confirm_live(what):
            return False
        await self._pihole("POST", "/api/dns/blocking", {"blocking": False, "timer": n}, approved=True)
        self.log(tr("Pi-hole"), what, tr("done"))
        return True

    async def pihole_enable(self):
        """Turns blocking back on, after asking you, every time. Gives back True if it was done."""
        what = tr("enable Pi-hole's blocking")
        if self._skip_action(what):
            return False
        if not await self.confirm_live(what):
            return False
        await self._pihole("POST", "/api/dns/blocking", {"blocking": True}, approved=True)
        self.log(tr("Pi-hole"), what, tr("done"))
        return True

    async def pihole_list(self, which, action, domain):
        """Puts a domain on Pi-hole's allow or deny list, or takes it off, after asking you, every time. Gives back
        True if it was done."""
        w, a, d = to_str(which).strip().lower(), to_str(action).strip().lower(), to_str(domain).strip().lower()
        if w not in ("allow", "deny") or a not in ("add", "remove") or not d:
            raise RunError(tr("Which list (allow or deny), add or remove, and which domain?"))
        what = tr("{action} {domain} on Pi-hole's {which} list", action=a, domain=d, which=w)
        if self._skip_action(what):
            return False
        if not await self.confirm_live(what):
            return False
        path = f"/api/domains/{w}list/exact"
        if a == "add":
            await self._pihole("POST", path, {"domain": d, "comment": tr("added by Second Thought")}, approved=True)
        else:
            await self._pihole("DELETE", path, {"domain": [d]}, approved=True)
        self.log(tr("Pi-hole"), what, tr("done"))
        return True
