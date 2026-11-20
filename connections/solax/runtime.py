    # Solax (#361)
    # SolaxCloud's end-user API (https://www.solaxcloud.com:9443/proxy/api/), read only: SOLAX_TOKEN_ID, free from the
    # API page of SolaxCloud, and SOLAX_SN, the Registration No. of the inverter's wifi dongle. The cloud's figures
    # update about every five minutes and it allows 10 calls a minute, so one read is kept for five minutes and reused:
    # a program that asks twice gets the same figures without a second call. SOLAX_API_URL points at another region's
    # cloud (https://www.eu.solaxcloud.com:9443/proxy/api/getRealtimeInfo.do, say). The inverter's own local API is
    # gone from newer firmware, so the cloud is what there is; Modbus control is out of scope: it can charge from the
    # grid, which costs money, so it belongs behind the ask-first rules of a later version.
    SOLAX_API = "https://www.solaxcloud.com:9443/proxy/api/getRealtimeInfo.do"
    SOLAX_SECONDS = 300

    @staticmethod
    def _solax_num(v):
        """The API gives numbers as text: just the number, or "" (no battery says -1)."""
        m = re.search(r"-?\d+(?:\.\d+)?", to_str(v))
        return _clean_num(float(m.group())) if m else ""

    @staticmethod
    def _solax_status(code):
        """The inverter's status code, as SolaxCloud's table names it (102 Normal Mode, 103 Fault Mode, ...)."""
        names = {100: "Wait Mode", 101: "Check Mode", 102: "Normal Mode", 103: "Fault Mode", 104: "Permanent Fault Mode",
                 105: "Update Mode", 106: "EPS Check Mode", 107: "EPS Mode", 108: "Self-Test Mode", 109: "Idle Mode",
                 110: "Standby Mode", 111: "Pv Wake Up Bat Mode", 112: "Gen Check Mode", 113: "Gen Run Mode"}
        try:
            return names.get(int(to_str(code).strip() or 0), to_str(code))
        except ValueError:
            return to_str(code)

    def _solax_request(self):
        """One call to SolaxCloud, or the figures from the last five minutes."""
        token, sn = os.environ.get("SOLAX_TOKEN_ID", "").strip(), os.environ.get("SOLAX_SN", "").strip()
        if not token or not sn:
            raise RunError(tr("Solax needs SOLAX_TOKEN_ID and SOLAX_SN {where_keys}: the token from the API page of SolaxCloud (free) and the Registration No. of the inverter's wifi dongle (on its label, or in the app).", where_keys=WHERE_KEYS))
        cached = self.__dict__.get("_solax_cache") or (0, None)
        if time.monotonic() - cached[0] < self.SOLAX_SECONDS and cached[1]:
            return cached[1]
        url = (os.environ.get("SOLAX_API_URL", "").strip() or self.SOLAX_API)
        req = urllib.request.Request(url + (("&" if "?" in url else "?") + urllib.parse.urlencode({"tokenId": token, "sn": sn})))
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                got = json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            raise RunError(tr("SolaxCloud answered {code}: check SOLAX_TOKEN_ID and SOLAX_SN.", code=e.code)) from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise Retryable(tr("Couldn't reach SolaxCloud at {url} ({x}).", url=url, x=getattr(e, 'reason', e))) from None
        got = got if isinstance(got, dict) else {}
        if not got.get("success"):
            raise RunError(tr("SolaxCloud refused the token or the Registration No.: {x}.", x=_short(to_str(got.get("exception")) or "?", 160)))
        res = got.get("result") if isinstance(got.get("result"), dict) else {}
        soc = self._solax_num(res.get("soc"))
        out = {"ac_power_w": self._solax_num(res.get("acpower")),
               "yield_today_kwh": _clean_num(round((self._solax_num(res.get("yieldtoday")) or 0) / 10, 1)) if self._solax_num(res.get("yieldtoday")) != "" else "",
               "yield_total_kwh": _clean_num(round((self._solax_num(res.get("yieldtotal")) or 0) / 10, 1)) if self._solax_num(res.get("yieldtotal")) != "" else "",
               "feedin_power_w": self._solax_num(res.get("feedinpower")),
               "feedin_energy_kwh": _clean_num(round((self._solax_num(res.get("feedinenergy")) or 0) / 100, 2)) if self._solax_num(res.get("feedinenergy")) != "" else "",
               "import_energy_kwh": _clean_num(round((self._solax_num(res.get("consumeenergy")) or 0) / 100, 2)) if self._solax_num(res.get("consumeenergy")) != "" else "",
               "battery_soc_pct": "" if soc == -1 else soc,
               "status": self._solax_status(res.get("inverterStatus")),
               "upload_time": to_str(res.get("uploadTime"))}
        self.__dict__["_solax_cache"] = (time.monotonic(), out)
        return out

    async def solax_now(self):
        """The inverter's figures as SolaxCloud last had them (about every five minutes): ac_power_w (what it's making
        now), yield_today_kwh and yield_total_kwh (solar generated), feedin_power_w and feedin_energy_kwh (to the
        grid), import_energy_kwh (from the grid), battery_soc_pct, status and upload_time."""
        out = await asyncio.to_thread(self._solax_request)
        self.log(tr("Solax figures"), "\n".join(f"{k}: {v}" for k, v in out.items() if v != ""),
                 tr("from {time}", time=out.get("upload_time") or "?"))
        return out
