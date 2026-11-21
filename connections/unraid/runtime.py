    # Unraid (#399)
    # Unraid's own GraphQL API: UNRAID_URL (the server's address, like https://unraid) and UNRAID_API_KEY (Settings,
    # Management Access, API Keys; built into Unraid 7.2 and later, the Unraid Connect plugin before that). Reads are
    # the queries in SAFETY["unraid_free"]; starting or stopping one container or VM, and a parity read-check
    # (unraid_asks) always ask, live, and never run with nobody there. Nothing else is ever sent: the array is never
    # stopped, no disk is added or removed, no container is updated or removed, no plugin is installed, nothing runs
    # in a terminal. UNRAID_CERT_SHA256 pins a certificate this computer doesn't trust.
    UNRAID_STATE = {"STARTED": "STARTED", "STOPPED": "STOPPED"}

    async def _unraid(self, query, approved=False):
        """One GraphQL request to the server, gated by unraid_call: a query goes without asking, one of the few
        allowed mutations only after a live yes, and anything else is never sent."""
        kind = unraid_call("POST", query)
        if kind is None or (kind == "asks" and not approved):
            raise RunError(tr("Second Thought doesn't send {what} to {who}.", what=query[:80], who="Unraid"))
        url = os.environ.get("UNRAID_URL", "").strip()
        key = os.environ.get("UNRAID_API_KEY", "").strip()
        if not url or not key:
            raise RunError(tr("{who} needs {url_setting} and {key_setting} {where_keys}: its address (like https://unraid) and an API key, under Settings, Management Access, API Keys.",
                              who="Unraid", url_setting="UNRAID_URL", key_setting="UNRAID_API_KEY", where_keys=WHERE_KEYS))
        base = url if url.endswith("/graphql") else url.rstrip("/") + "/graphql"
        status, raw = await self._pinned("Unraid", base, "UNRAID_CERT_SHA256", "POST", "", {"x-api-key": key}, {"query": query})
        if status == 401:
            raise RunError(tr("The {who} refused its API key.", who="Unraid"))
        if status >= 400:
            raise RunError(tr("{who}: {why}.", who="Unraid", why=self._said(status, raw)))
        answer = json.loads(raw) if raw.strip() else {}
        if isinstance(answer, dict) and answer.get("errors"):
            raise RunError(tr("{who}: {why}.", who="Unraid", why=_short(to_str(answer["errors"][0].get("message") if answer["errors"] else ""), 120)))
        return (answer or {}).get("data") or {}

    async def unraid_array(self):
        """One record for the array: state (STARTED, STOPPED, ...), started (whether it's started), free_gb,
        total_gb and uptime."""
        d = await self._unraid("query{array{state capacity{kilobytes{free total}}}info{os{uptime}}}")
        a = d.get("array") or {}
        kb = ((a.get("capacity") or {}).get("kilobytes") or {})
        out = {"state": to_str(a.get("state")), "started": to_str(a.get("state")) == "STARTED",
               "free_gb": self._cents(num(kb.get("free")) / 1048576) if kb.get("free") else "",
               "total_gb": self._cents(num(kb.get("total")) / 1048576) if kb.get("total") else "",
               "uptime": to_str(((d.get("info") or {}).get("os") or {}).get("uptime"))}
        line = tr("{state}, {free_gb} GB free of {total_gb} GB", **out) if out["free_gb"] else out["state"]
        self.log(tr("Unraid array"), line)
        return out

    async def unraid_disks(self):
        """A list of records, one for each disk in the array, parity first then data then cache: name, type (Parity,
        Data, Cache), status (DISK_OK, DISK_NP, ...), temp_c, errors, size_gb and free_gb."""
        d = await self._unraid("query{array{parities{name type status temp numErrors fsSize fsFree}disks{name type status"
                               " temp numErrors fsSize fsFree}caches{name type status temp numErrors fsSize fsFree}}}")
        a = d.get("array") or {}
        rows = [r for kind in ("parities", "disks", "caches") for r in (a.get(kind) or []) if isinstance(r, dict)]
        out = [{"name": to_str(r.get("name")), "type": to_str(r.get("type")).capitalize(), "status": to_str(r.get("status")),
                "temp_c": num(r.get("temp")) if r.get("temp") is not None else "",
                "errors": num(r.get("numErrors")) if r.get("numErrors") is not None else "",
                "size_gb": self._cents(num(r.get("fsSize")) / 1048576) if r.get("fsSize") else "",
                "free_gb": self._cents(num(r.get("fsFree")) / 1048576) if r.get("fsFree") else ""} for r in rows]
        lines = "\n".join(f"{r['name']} ({r['type']})" + (f": {r['temp_c']} °C" if r["temp_c"] != "" else "") for r in out)
        self.log(tr("Unraid disks"), lines or tr("(nothing)"), tr("{n} disks", n=len(out)))
        return out

    async def unraid_shares(self):
        """A list of records, one for each user share: name, free_gb, used_gb and total_gb."""
        rows = (await self._unraid("query{shares{name free used size}}")).get("shares") or []
        out = [{"name": to_str(r.get("name")),
                "free_gb": self._cents(num(r.get("free")) / 1048576) if r.get("free") else "",
                "used_gb": self._cents(num(r.get("used")) / 1048576) if r.get("used") else "",
                "total_gb": self._cents(num(r.get("size")) / 1048576) if r.get("size") else ""} for r in rows if isinstance(r, dict)]
        lines = "\n".join(f"{r['name']}: {r['free_gb']} GB free" for r in out)
        self.log(tr("Unraid shares"), lines or tr("(nothing)"), tr("{n} shares", n=len(out)))
        return out

    async def unraid_containers(self):
        """A list of records, one for each Docker container: name, state (running, exited, ...), status and
        auto_start (whether Unraid starts it with the array)."""
        rows = (await self._unraid("query{dockerContainers{id names state status autoStart}}")).get("dockerContainers") or []
        out = [{"name": to_str((r.get("names") or [""])[0]), "state": to_str(r.get("state")), "status": to_str(r.get("status")),
                "auto_start": bool(r.get("autoStart"))} for r in rows if isinstance(r, dict)]
        lines = "\n".join(f"{r['name']}: {r['state']}" for r in out)
        self.log(tr("Unraid containers"), lines or tr("(nothing)"), tr("{n} containers", n=len(out)))
        return out

    async def unraid_vms(self):
        """A list of records, one for each VM: name and state (RUNNING, SHUTOFF, ...)."""
        rows = ((await self._unraid("query{vms{domains{id name state}}}")).get("vms") or {}).get("domains") or []
        out = [{"name": to_str(r.get("name")), "state": to_str(r.get("state"))} for r in rows if isinstance(r, dict)]
        lines = "\n".join(f"{r['name']}: {r['state']}" for r in out)
        self.log(tr("Unraid VMs"), lines or tr("(nothing)"), tr("{n} VMs", n=len(out)))
        return out

    async def unraid_power(self, kind, action, name):
        """Starts or stops one container or VM, after asking you, every time. Gives back True if it was done."""
        k, a, n = to_str(kind).strip().lower(), to_str(action).strip().lower(), to_str(name).strip()
        if k not in ("container", "vm") or a not in ("start", "stop") or not n:
            raise RunError(tr("Which one, and start or stop?"))
        who = tr("container") if k == "container" else tr("VM")
        what = tr("{action} the Unraid {who} {name}", action=a, who=who, name=n)
        if self._skip_action(what):
            return False
        if not await self.confirm_live(what):
            return False
        query = 'mutation{docker{' + a + '(id:"container:' + n + '"){id}}}' if k == "container" \
            else 'mutation{vm{' + a + '(id:"vm:' + n + '")}'
        await self._unraid(query, approved=True)
        self.log(tr("Unraid"), what, tr("done"))
        return True

    async def unraid_parity(self):
        """Checks the parity disks by reading them (a read-check, no corrections written), after asking you, every
        time. Gives back True if it was started."""
        what = tr("check Unraid's parity")
        if self._skip_action(what):
            return False
        if not await self.confirm_live(what):
            return False
        await self._unraid("mutation{parity{start(correct:false)}}", approved=True)
        self.log(tr("Unraid"), what, tr("done"))
        return True
