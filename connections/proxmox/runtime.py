    # Proxmox (#357)
    # Proxmox VE's REST API, with an API token: PROXMOX_URL (https://pve:8006), PROXMOX_TOKEN_ID (user@pam!name) and
    # PROXMOX_TOKEN_SECRET. Give the token the PVEAuditor role unless the program starts or stops guests. Reads are the
    # calls in SAFETY["proxmox_free"]; start, shut down and reboot (proxmox_asks) always ask, live, and never run with
    # nobody there; nothing else is ever sent. PROXMOX_PROTECT lists VMIDs never started, stopped or rebooted at all.
    # PROXMOX_CERT_SHA256 pins the node's own certificate, as for MikroTik and UniFi.
    PROXMOX_POWER = {"start": "start", "shutdown": "shut down", "reboot": "reboot"}

    async def _proxmox(self, method, path, query=None, approved=False):
        kind = proxmox_call(method, path)
        if kind is None or (kind == "asks" and not approved):
            raise RunError(tr("Second Thought doesn't send {what} to Proxmox.", what=f"{method} {path}"))
        base = os.environ.get("PROXMOX_URL", "").strip().rstrip("/")
        tid, secret = os.environ.get("PROXMOX_TOKEN_ID", "").strip(), os.environ.get("PROXMOX_TOKEN_SECRET", "").strip()
        if not base or not tid or not secret:
            raise RunError(tr("Proxmox needs PROXMOX_URL, PROXMOX_TOKEN_ID and PROXMOX_TOKEN_SECRET {where_keys}: the address (like https://pve.local:8006) and an API token, from Datacenter, Permissions, API Tokens. Give it the PVEAuditor role unless the program starts or stops guests.", where_keys=WHERE_KEYS))
        status, raw = await self._pinned("Proxmox", base, "PROXMOX_CERT_SHA256", method, path + ("?" + urllib.parse.urlencode(query) if query else ""),
                                         {"Authorization": f"PVEAPIToken={tid}={secret}"})
        if status == 401:
            raise RunError(tr("Proxmox refused PROXMOX_TOKEN_ID and PROXMOX_TOKEN_SECRET."))
        if status == 403:
            raise RunError(tr("Proxmox: {why}.", why=tr("the token isn't allowed to do that")))
        if status >= 400:
            raise RunError(tr("Proxmox: {why}.", why=self._said(status, raw)))
        got = json.loads(raw) if raw.strip() else {}
        return got.get("data") if isinstance(got, dict) else got

    @staticmethod
    def _pct(used, size):
        return _clean_num(math.floor(num(used) / num(size) * 1000 + 0.5) / 10) if num(size) else ""

    async def proxmox_nodes(self):
        """Each node: node, status (online or offline), cpu and memory (%), uptime (hours)."""
        out = [{"node": to_str(n.get("node")), "status": to_str(n.get("status")), "cpu": _clean_num(math.floor(num(n.get("cpu")) * 1000 + 0.5) / 10),
                "memory": self._pct(n.get("mem"), n.get("maxmem")), "uptime": self._cents(num(n.get("uptime")) / 3600)}
               for n in await self._proxmox("GET", "/api2/json/nodes") or [] if isinstance(n, dict)]
        return sorted(out, key=lambda n: n["node"])

    async def proxmox_guests(self):
        """Each VM and container: vmid, name, node, type (vm or container), status, cpu and memory (%), uptime (hours),
        and for one that's stopped, onboot (whether it should start when the node does)."""
        out = []
        for g in await self._proxmox("GET", "/api2/json/cluster/resources", {"type": "vm"}) or []:
            if not isinstance(g, dict) or g.get("template"):
                continue
            rec = {"vmid": int(num(g.get("vmid"))), "name": to_str(g.get("name")), "node": to_str(g.get("node")),
                   "type": "container" if g.get("type") == "lxc" else "vm", "status": to_str(g.get("status")),
                   "cpu": _clean_num(math.floor(num(g.get("cpu")) * 1000 + 0.5) / 10), "memory": self._pct(g.get("mem"), g.get("maxmem")),
                   "uptime": self._cents(num(g.get("uptime")) / 3600), "onboot": ""}
            if rec["status"] == "stopped" and re.fullmatch(r"[A-Za-z0-9.-]+", rec["node"]):
                cfg = await self._proxmox("GET", f"/api2/json/nodes/{rec['node']}/{g.get('type')}/{rec['vmid']}/config") or {}
                rec["onboot"] = to_str(cfg.get("onboot")) == "1"
            out.append(rec)
        out.sort(key=lambda g: g["vmid"])
        lines = "\n".join(f"{g['vmid']} {g['name']}: {g['status']}" for g in out)
        self.log(tr("Proxmox guests"), lines or tr("(nothing)"), tr("{n} guests", n=len(out)))
        return out

    async def proxmox_storage(self):
        """Each storage on each node: storage, node, used (%), used_gb, size_gb and status."""
        out = [{"storage": to_str(s.get("storage")), "node": to_str(s.get("node")), "used": self._pct(s.get("disk"), s.get("maxdisk")),
                "used_gb": self._cents(num(s.get("disk")) / 1073741824), "size_gb": self._cents(num(s.get("maxdisk")) / 1073741824),
                "status": to_str(s.get("status"))}
               for s in await self._proxmox("GET", "/api2/json/cluster/resources", {"type": "storage"}) or [] if isinstance(s, dict)]
        return sorted(out, key=lambda s: (s["node"], s["storage"]))

    async def proxmox_tasks(self, hours=24):
        """The cluster's tasks from the last few hours, newest first: started, node, type (vzdump is a backup), id (the
        guest, if any), status (OK, or what went wrong; running if it hasn't finished) and user."""
        since = time.time() - max(1, min(24 * 31, num(hours) or 24)) * 3600
        out = []
        for t in await self._proxmox("GET", "/api2/json/cluster/tasks") or []:
            if isinstance(t, dict) and num(t.get("starttime")) >= since:
                out.append({"started": datetime.datetime.fromtimestamp(num(t.get("starttime"))).strftime("%Y-%m-%d %H:%M"), "node": to_str(t.get("node")),
                            "type": to_str(t.get("type")), "id": to_str(t.get("id")), "status": to_str(t.get("status")) or "running", "user": to_str(t.get("user"))})
        return sorted(out, key=lambda t: t["started"], reverse=True)

    async def proxmox_power(self, action, vmid):
        """Starts, shuts down or reboots one guest, by its VMID, after asking you, every time. Never one in
        PROXMOX_PROTECT. Gives back True if it was done."""
        action = to_str(action).strip().lower().replace(" ", "")
        if action not in self.PROXMOX_POWER:
            raise RunError(tr("A Proxmox guest can be started, shut down or rebooted."))
        if not _num_like(vmid) or num(vmid) != int(num(vmid)) or num(vmid) < 100:
            raise RunError(tr("Which Proxmox guest? Give its VMID, like 101."))
        vmid = int(num(vmid))
        protected = {int(x) for x in re.findall(r"\d+", os.environ.get("PROXMOX_PROTECT", ""))}
        if vmid in protected:
            self.log(tr("Not done"), tr("Guest {vmid} is in PROXMOX_PROTECT, so Second Thought never starts, stops or reboots it.", vmid=vmid), tr("refused"))
            return False
        g = next((g for g in await self._proxmox("GET", "/api2/json/cluster/resources", {"type": "vm"}) or []
                  if isinstance(g, dict) and int(num(g.get("vmid"))) == vmid), None)
        if not g or not re.fullmatch(r"[A-Za-z0-9.-]+", to_str(g.get("node"))) or g.get("type") not in ("qemu", "lxc"):
            raise RunError(tr("Proxmox: {why}.", why=tr("not found")))
        what = f"{self.PROXMOX_POWER[action]} the Proxmox guest {vmid} ({to_str(g.get('name'))}, on {to_str(g.get('node'))}, now {to_str(g.get('status'))})"
        if self._skip_action(what):
            return False
        if not await self.confirm_live(what):
            return False
        await self._proxmox("POST", f"/api2/json/nodes/{g['node']}/{g['type']}/{vmid}/status/{action}", approved=True)
        self.log(tr("Proxmox"), what, tr("done"))
        return True
