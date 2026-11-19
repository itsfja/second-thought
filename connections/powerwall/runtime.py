    # Powerwall (#362)
    # Tesla's local gateway API (the one the gateway's web portal uses), for a Powerwall, Powerwall 2 or Powerwall+ on
    # your network: POWERWALL_URL (the gateway's address, like https://192.168.1.50) and POWERWALL_PASSWORD, the
    # customer password (the last five characters of the one on the gateway's QR sticker, unless you changed it).
    # Login happens once and the token it gives is kept. Only the reads in SAFETY["powerwall_free"] are ever sent, so
    # no firmware, storm watch or operation mode is ever touched; setting the backup reserve (powerwall_asks) always
    # asks, live, and never runs with nobody there to say yes: it changes how long the house lasts in a power cut.
    # The Powerwall 3 has no local web API: use Home Assistant or Teslemetry for one of those. POWERWALL_CERT_SHA256
    # pins the gateway's own certificate, as for MikroTik.
    POWERWALL_GRID = {"SystemGridConnected": "connected", "SystemConnectedToGrid": "connected",
                      "SystemIslandedActive": "islanded (power cut)", "SystemTransitionToIsland": "transitioning"}

    async def _powerwall(self, method, path, body=None, approved=False, again=True):
        """One call to the gateway, logged in as the customer. Only the calls in SAFETY are ever made."""
        if not powerwall_allowed(method, path, approved):
            raise RunError(tr("Second Thought only reads from the Powerwall, so it doesn't send {what}.", what=f"{method} {path}"))
        base = os.environ.get("POWERWALL_URL", "").strip().rstrip("/")
        password = os.environ.get("POWERWALL_PASSWORD", "")
        if not base or not password:
            raise RunError(tr("Powerwall needs POWERWALL_URL and POWERWALL_PASSWORD {where_keys}: the gateway's address (like https://192.168.1.50) and the customer password (the last five characters of the one on its QR sticker, unless you changed it).", where_keys=WHERE_KEYS))
        if not self.__dict__.get("_powerwall_token"):
            lock = self.__dict__.setdefault("_powerwall_lock", asyncio.Lock())
            async with lock:  # four reads at once, one login
                if not self.__dict__.get("_powerwall_token"):
                    status, raw = await self._pinned("Powerwall gateway", base, "POWERWALL_CERT_SHA256", "POST", "/api/login/Basic", {},
                                                    {"username": "customer", "password": password,
                                                     "email": os.environ.get("POWERWALL_EMAIL", "").strip() or "customer@example.com",
                                                     "force_sm_off": False})
                    if status == 401:
                        raise RunError(tr("The Powerwall gateway refused POWERWALL_PASSWORD: check the customer password (the last five characters of the one on its QR sticker)."))
                    if status >= 400:
                        raise RunError(tr("Powerwall: {why}.", why=self._said(status, raw)))
                    try:
                        self.__dict__["_powerwall_token"] = to_str(json.loads(raw).get("token"))
                    except (ValueError, AttributeError):
                        self.__dict__["_powerwall_token"] = ""
                    if not self.__dict__["_powerwall_token"]:
                        raise RunError(tr("The Powerwall gateway's login gave no token."))
        headers = {"Authorization": "Bearer " + self.__dict__["_powerwall_token"]}
        status, raw = await self._pinned("Powerwall gateway", base, "POWERWALL_CERT_SHA256", method, path, headers, body)
        if status == 401 and again:  # the token has expired: log in again, once
            self.__dict__["_powerwall_token"] = ""
            return await self._powerwall(method, path, body, approved, again=False)
        if status >= 400:
            raise RunError(tr("Powerwall: {why}.", why=self._said(status, raw)))
        return json.loads(raw) if raw.strip() else {}

    @staticmethod
    def _pw_num(v):
        m = re.search(r"-?\d+(?:\.\d+)?", to_str(v))
        return _clean_num(float(m.group())) if m else ""

    async def powerwall_now(self):
        """The Powerwall's figures: battery_soc_pct (its charge), solar_power_w (making now), battery_power_w (positive
        is charging), grid_power_w (positive is importing), load_power_w (the house), reserve_pct (the backup reserve
        it keeps), mode (self_consumption, backup, ...), grid (connected, or islanded in a power cut)."""
        meters, soe, grid, op = (await asyncio.gather(
            self._powerwall("GET", "/api/meters/aggregates"), self._powerwall("GET", "/api/system_status/soe"),
            self._powerwall("GET", "/api/system_status/grid_status"), self._powerwall("GET", "/api/operation")))
        meter = lambda name: self._pw_num((meters.get(name) or {}).get("instant_power")) if isinstance(meters, dict) else ""  # noqa: E731
        out = {"battery_soc_pct": self._pw_num(soe.get("percentage") if isinstance(soe, dict) else ""),
               "solar_power_w": meter("solar"), "battery_power_w": meter("battery"),
               "grid_power_w": meter("site"), "load_power_w": meter("load"),
               "reserve_pct": self._pw_num(op.get("backup_reserve_percent") if isinstance(op, dict) else ""),
               "mode": to_str((op or {}).get("real_mode") or (op or {}).get("mode") or "") if isinstance(op, dict) else "",
               "grid": self.POWERWALL_GRID.get(to_str(grid.get("grid_status") if isinstance(grid, dict) else ""),
                                                to_str(grid.get("grid_status") if isinstance(grid, dict) else ""))}
        self.log(tr("Powerwall figures"), "\n".join(f"{k}: {v}" for k, v in out.items() if v != ""),
                 tr("battery at {pct}%", pct=out["battery_soc_pct"]))
        return out

    async def powerwall_reserve(self, percent):
        """Sets the backup reserve, after asking: it changes how much of the battery the house keeps for a power cut.
        Always asks, live, and never runs with nobody there to say yes."""
        n = max(0, min(100, int(round(num(percent) or 0))))
        op = await self._powerwall("GET", "/api/operation")
        what = tr("set the Powerwall backup reserve to {n}% (now {old}%)", n=n, old=self._pw_num(op.get("backup_reserve_percent")))
        if self._skip_action(what):
            return False
        if not await self.confirm_live(what):
            return False
        await self._powerwall("POST", "/api/operation", {"backup_reserve_percent": n}, approved=True)
        self.log(tr("Powerwall"), what, tr("done"))
        return True
