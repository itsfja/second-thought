    # MikroTik (#360)
    # RouterOS 7's REST API (the www-ssl service), read only: MIKROTIK_URL, MIKROTIK_USER and MIKROTIK_PASSWORD, for a
    # user in a group with just the read, api and rest-api policies. Only the calls in SAFETY["mikrotik_free"] are ever
    # made. A router's certificate is usually its own (self-signed), so MIKROTIK_CERT_SHA256 pins it: the connection
    # goes ahead only if the certificate's SHA-256 fingerprint matches. --doctor shows the fingerprint it sees.

    async def _mikrotik(self, method, path, body=None):
        if not mikrotik_allowed(method, path):
            raise RunError(tr("Second Thought only reads from MikroTik, so it doesn't send {what}.", what=f"{method} {path}"))
        base = os.environ.get("MIKROTIK_URL", "").strip().rstrip("/")
        user, password = os.environ.get("MIKROTIK_USER", "").strip(), os.environ.get("MIKROTIK_PASSWORD", "")
        if not base or not user:
            raise RunError(tr("MikroTik needs MIKROTIK_URL, MIKROTIK_USER and MIKROTIK_PASSWORD {where_keys}: the router's address (like https://192.168.88.1) and a user in a group with only the read, api and rest-api policies.", where_keys=WHERE_KEYS))
        headers = {"Authorization": "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()}
        status, raw = await self._pinned("MikroTik", base, "MIKROTIK_CERT_SHA256", method, path, headers, body)
        if status == 401:
            raise RunError(tr("The MikroTik refused MIKROTIK_USER and MIKROTIK_PASSWORD."))
        if status >= 400:
            raise RunError(tr("MikroTik: {why}.", why=self._said(status, raw)))
        return json.loads(raw) if raw.strip() else []

    @staticmethod
    def _said(status, raw):
        """"it answered 404 (what it said)", for an error from a device's API."""
        try:
            said = json.loads(raw)
            said = to_str(said.get("detail") or said.get("message") or "") if isinstance(said, dict) else ""
        except ValueError:
            said = ""
        return tr("it answered {code}", code=status) + (f" ({_short(said, 120)})" if said else "")

    async def _pinned(self, who, base, setting, method, path, headers, body=None):
        """One HTTPS request to a device on your network (a router, a switch, a gateway), whose certificate is usually
        its own. With a pin in the setting named, the certificate's SHA-256 fingerprint must match it, checked before
        anything (a password included) is sent; without one, the certificate must be one this computer trusts. Gives
        back (status, body)."""
        if "://" not in base:
            base = "https://" + base
        u = urllib.parse.urlparse(base)
        pin = re.sub(r"[^0-9a-f]", "", os.environ.get(setting, "").lower())
        headers = dict(headers, Accept="application/json")
        data = None
        if body is not None:
            data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"

        def go():
            if u.scheme == "https":
                import ssl
                ctx = ssl.create_default_context()
                if pin:  # the pin is the check: a self-signed certificate wouldn't pass the usual one
                    ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
                conn = http.client.HTTPSConnection(u.hostname, u.port or 443, timeout=15, context=ctx)
            else:
                conn = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=15)
            try:
                conn.connect()
                if u.scheme == "https" and pin:
                    seen = hashlib.sha256(conn.sock.getpeercert(binary_form=True)).hexdigest()
                    if seen != pin:
                        raise RunError(tr("The {who}'s certificate isn't the one {setting} pins (it's {seen}). If you replaced the certificate, update the pin; if not, something is in the way.", who=who, setting=setting, seen=seen))
                conn.request(method, (u.path or "") + path, body=data, headers=headers)
                r = conn.getresponse()
                return r.status, r.read()
            except RunError:
                raise
            except Exception as e:  # noqa: BLE001 - certificate, refused, timed out: say which
                text = str(e)
                if "CERTIFICATE_VERIFY_FAILED" in text:
                    raise RunError(tr("The {who}'s certificate isn't one this computer trusts (routers usually make their own). Run --doctor to see its fingerprint, and put it in {setting}.", who=who, setting=setting)) from None
                raise RunError(tr("Couldn't reach the {who} at {url} ({reason}).", who=who, url=base, reason=_short(text, 120))) from None
            finally:
                conn.close()
        return await asyncio.to_thread(go)

    @staticmethod
    def _mt_num(v):
        """RouterOS gives numbers as text, some with a unit on the end (38C, -3.979dBm): just the number, or ""."""
        m = re.search(r"-?\d+(?:\.\d+)?", to_str(v))
        return _clean_num(float(m.group())) if m else ""

    async def _mt_monitor(self, ports):
        names = [p for p in ports if p]
        if not names:
            return {}
        got = await self._mikrotik("POST", "/rest/interface/ethernet/monitor", {"numbers": ",".join(names), "once": ""})
        return {to_str(m.get("name")): m for m in got if isinstance(m, dict)}

    async def mikrotik_ports(self):
        """Every port: port, running (yes/no), speed (as RouterOS says it, like 10Gbps; "" when down), errors and drops
        since the switch started, link downs and comment."""
        ifs = [i for i in await self._mikrotik("GET", "/rest/interface") if isinstance(i, dict) and to_str(i.get("disabled")) != "true"]
        mon = await self._mt_monitor([to_str(i.get("name")) for i in ifs if to_str(i.get("type")) == "ether"])
        n = lambda i, *ks: _clean_num(sum(float(self._mt_num(i.get(k)) or 0) for k in ks))  # noqa: E731
        out = [{"port": to_str(i.get("name")), "running": to_str(i.get("running")) == "true",
                "speed": to_str((mon.get(to_str(i.get("name"))) or {}).get("rate")) if to_str(i.get("running")) == "true" else "",
                "errors": n(i, "rx-error", "tx-error"), "drops": n(i, "rx-drop", "tx-drop"), "link_downs": n(i, "link-downs"),
                "comment": to_str(i.get("comment"))} for i in ifs if to_str(i.get("type")) in ("ether", "bridge", "vlan", "bond")]
        lines = "\n".join(f"{p['port']}: {p['speed'] or '-'}" for p in out)
        self.log(tr("MikroTik ports"), lines or tr("(nothing)"), tr("{n} ports", n=len(out)))
        return out

    async def mikrotik_sfp(self):
        """Each SFP module in the switch: port, module (maker and part), temperature (°C), rx_power and tx_power (dBm)."""
        ifs = [i for i in await self._mikrotik("GET", "/rest/interface") if isinstance(i, dict) and to_str(i.get("type")) == "ether"]
        mon = await self._mt_monitor([to_str(i.get("name")) for i in ifs if to_str(i.get("disabled")) != "true"])
        return [{"port": name, "module": " ".join(x for x in (to_str(m.get("sfp-vendor-name")).strip(), to_str(m.get("sfp-vendor-part-number")).strip()) if x),
                 "temperature": self._mt_num(m.get("sfp-temperature")), "rx_power": self._mt_num(m.get("sfp-rx-power")),
                 "tx_power": self._mt_num(m.get("sfp-tx-power"))}
                for name, m in mon.items() if to_str(m.get("sfp-module-present")) == "true"]

    async def mikrotik_health(self):
        """The switch itself: board, version, uptime, cpu_load (%), free_memory (MB) and temperature (°C), with any other
        sensor it has (cpu_temperature, fan1_speed and so on)."""
        res = await self._mikrotik("GET", "/rest/system/resource")
        res = res[0] if isinstance(res, list) and res else res if isinstance(res, dict) else {}
        out = {"board": to_str(res.get("board-name")), "version": to_str(res.get("version")), "uptime": to_str(res.get("uptime")),
               "cpu_load": self._mt_num(res.get("cpu-load")), "free_memory": _clean_num(math.floor(float(self._mt_num(res.get("free-memory")) or 0) / 1048576 * 10 + 0.5) / 10),
               "temperature": ""}
        for s in await self._mikrotik("GET", "/rest/system/health"):
            if isinstance(s, dict) and s.get("name"):
                v = to_str(s.get("value"))
                out[re.sub(r"\W+", "_", to_str(s.get("name"))).strip("_")] = self._mt_num(v) if self._mt_num(v) != "" and re.fullmatch(r"-?[\d.]+\w?", v) else v
        return out

    async def mikrotik_log(self, count=20):
        """The log's last few lines, oldest first: "time topics: message"."""
        n = max(1, min(500, int(num(count) or 20)))
        rows = [r for r in await self._mikrotik("GET", "/rest/log") if isinstance(r, dict)][-n:]
        return [f"{to_str(r.get('time'))} {to_str(r.get('topics'))}: {to_str(r.get('message'))}" for r in rows]
