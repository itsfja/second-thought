    # UniFi (#359)
    # The Network API on a UniFi OS console (a Cloud Gateway, a Dream Machine): UNIFI_URL and UNIFI_API_KEY, a key made
    # in the Network app under Settings, Control Plane, Integrations. Only the reads in SAFETY["unifi_free"] are ever
    # sent, so nothing is blocked, restarted or reconfigured, whatever the key itself could do. UNIFI_CERT_SHA256 pins
    # the console's own certificate, as for MikroTik; UNIFI_SITE picks a site other than the first.
    UNIFI_API = "/proxy/network/integration/v1"

    async def _unifi(self, path, query=None):
        full = self.UNIFI_API + path
        if not unifi_allowed("GET", full):
            raise RunError(tr("Second Thought only reads from UniFi, so it doesn't send {what}.", what=f"GET {full}"))
        base, key = os.environ.get("UNIFI_URL", "").strip().rstrip("/"), os.environ.get("UNIFI_API_KEY", "").strip()
        if not base or not key:
            raise RunError(tr("UniFi needs UNIFI_URL and UNIFI_API_KEY {where_keys}: the console's address (like https://192.168.1.1) and an API key from the Network app (Settings, Control Plane, Integrations).", where_keys=WHERE_KEYS))
        status, raw = await self._pinned("UniFi", base, "UNIFI_CERT_SHA256", "GET",
                                         full + ("?" + urllib.parse.urlencode(query) if query else ""), {"X-API-KEY": key})
        if status == 401:
            raise RunError(tr("The UniFi console refused UNIFI_API_KEY."))
        if status >= 400:
            raise RunError(tr("UniFi: {why}.", why=self._said(status, raw)))
        return json.loads(raw) if raw.strip() else {}

    async def _unifi_all(self, path):
        out, offset = [], 0
        while True:
            page = await self._unifi(path, {"offset": offset, "limit": 200})
            data = page.get("data") or [] if isinstance(page, dict) else []
            out += [x for x in data if isinstance(x, dict)]
            offset += len(data)
            if not data or offset >= int(num(page.get("totalCount")) or 0) or offset >= 5000:
                return out

    async def _unifi_site(self):
        sites = await self._unifi_all("/sites")
        want = os.environ.get("UNIFI_SITE", "").strip().lower()
        site = next((s for s in sites if want and want in (to_str(s.get("name")).lower(), to_str(s.get("internalReference")).lower())), None) or \
            next(iter(sites), None)
        if not site or not re.fullmatch(r"[A-Za-z0-9-]+", to_str(site.get("id"))):
            raise RunError(tr("UniFi: {why}.", why=tr("not found")))
        return to_str(site["id"])

    @staticmethod
    def _unifi_when(t):
        try:
            return datetime.datetime.fromisoformat(to_str(t).replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return to_str(t)

    async def unifi_clients(self):
        """Everyone connected: name, mac, ip, type (wired, wireless, vpn), connected (since when) and uplink (the UniFi
        device it's connected through)."""
        site = await self._unifi_site()
        names = {to_str(d.get("id")): to_str(d.get("name")) for d in await self._unifi_all(f"/sites/{site}/devices")}
        out = [{"name": to_str(c.get("name") or c.get("hostname") or c.get("macAddress")), "mac": to_str(c.get("macAddress")).lower(),
                "ip": to_str(c.get("ipAddress")), "type": to_str(c.get("type")).lower(), "connected": self._unifi_when(c.get("connectedAt")),
                "uplink": names.get(to_str(c.get("uplinkDeviceId")), "")} for c in await self._unifi_all(f"/sites/{site}/clients")]
        lines = "\n".join(f"{c['name']} ({c['ip'] or c['mac']})" for c in out)
        self.log(tr("UniFi clients"), lines or tr("(nothing)"), tr("{n} clients", n=len(out)))
        return out

    async def unifi_devices(self):
        """Each UniFi device: name, model, mac, ip, state (online, offline, ...), firmware, update (whether newer
        firmware is waiting), and for one that's online, uptime (hours), cpu and memory (%)."""
        site = await self._unifi_site()
        out = []
        for d in await self._unifi_all(f"/sites/{site}/devices"):
            rec = {"name": to_str(d.get("name")), "model": to_str(d.get("model")), "mac": to_str(d.get("macAddress")).lower(),
                   "ip": to_str(d.get("ipAddress")), "state": to_str(d.get("state")).lower(), "firmware": to_str(d.get("firmwareVersion")),
                   "update": bool(d.get("firmwareUpdatable")), "uptime": "", "cpu": "", "memory": ""}
            did = to_str(d.get("id"))
            if rec["state"] == "online" and re.fullmatch(r"[A-Za-z0-9-]+", did):
                st = await self._unifi(f"/sites/{site}/devices/{did}/statistics/latest")
                rec.update(uptime=self._cents(num(st.get("uptimeSec")) / 3600) if _num_like(st.get("uptimeSec")) else "",
                           cpu=num(st.get("cpuUtilizationPct")) if _num_like(st.get("cpuUtilizationPct")) else "",
                           memory=num(st.get("memoryUtilizationPct")) if _num_like(st.get("memoryUtilizationPct")) else "")
            out.append(rec)
        return out
