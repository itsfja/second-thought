    # Homey
    # Homey Pro's local Web API: HOMEY_URL is its address on your network (a Homey Self-Hosted Server serves the same
    # API on port 4859, so add :4859; devices on a Homey Bridge show up through it), HOMEY_API_KEY a key from the Homey Web App
    # (Settings, API Keys). Give the key the permissions your program needs: devices (view, and control to switch
    # things), flows (view and start), Logic (view, and edit to set variables).
    HOMEY_SENSITIVE = {tuple(x) for x in SAFETY["homey_sensitive"]}  # unlocking, opening and disarming: SAFETY in core.py

    async def _homey(self, method, path, body=None):
        url, key = os.environ.get("HOMEY_URL", "").strip().rstrip("/"), os.environ.get("HOMEY_API_KEY", "").strip()
        if not url or not key:
            raise RunError(tr("Homey needs HOMEY_URL and HOMEY_API_KEY {where_keys}. Make a key in the Homey Web App: Settings, API Keys.", where_keys=WHERE_KEYS))
        if not re.match(r"^https?://", url):
            url = "http://" + url
        req = urllib.request.Request(url + "/api/manager" + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})

        def go():
            try:
                with urllib.request.urlopen(req, timeout=20) as r:
                    raw = r.read()
                    return json.loads(raw) if raw.strip() else None
            except urllib.error.HTTPError as e:
                why = {401: "the API key was refused. Check HOMEY_API_KEY", 403: "the API key isn't allowed to do that. Give it more permissions in the Homey Web App",
                       404: "not found"}.get(e.code, f"Homey answered {e.code}")
                raise RunError(tr("Homey: {why}.", why=why)) from None
            except urllib.error.URLError as e:
                hint = "" if urllib.parse.urlparse(url).port else " For a Homey Self-Hosted Server, add its port: :4859."
                raise RunError(tr("Couldn't reach Homey at {url} ({reason}).{hint}", url=url, reason=e.reason, hint=hint)) from None
        return await asyncio.to_thread(go)

    async def _homey_home(self):
        """Every device, with its zone's name."""
        devices = await self._homey("GET", "/devices/device/")
        try:
            zones = {k: v.get("name", "") for k, v in (await self._homey("GET", "/zones/zone/")).items()}
        except RunError:
            zones = {}
        out = []
        for d in (devices or {}).values():
            caps = {k: c.get("value") for k, c in (d.get("capabilitiesObj") or {}).items()}
            zone = d.get("zone")
            zone = zones.get(zone if isinstance(zone, str) else (zone or {}).get("id"), "") or (zone.get("name", "") if isinstance(zone, dict) else "")
            out.append({"id": d.get("id"), "name": d.get("name", ""), "zone": zone, "class": d.get("class", ""), "caps": caps})
        out.sort(key=lambda x: (x["zone"], x["name"]))
        return out

    @staticmethod
    def _homey_show(v):
        return "on" if v is True else "off" if v is False else "-" if v is None else to_str(v)

    def _homey_line(self, d):
        return f"{d['name']} ({d['zone'] or 'no zone'}, {d['class']}): " + ", ".join(f"{k}={self._homey_show(v)}" for k, v in d["caps"].items())

    async def _homey_device(self, name):
        """A device by its name (or id). An exact name wins; otherwise one device whose name contains the words."""
        name = to_str(name).strip()
        if not name:
            raise RunError(tr("Which Homey device? Give its name, like Kitchen light."))
        home = await self._homey_home()
        exact = [d for d in home if d["name"].lower() == name.lower() or d["id"] == name]
        if exact:
            return exact[0]
        some = [d for d in home if all(w in d["name"].lower() for w in name.lower().split())]
        if len(some) == 1:
            return some[0]
        raise RunError(tr("There's no Homey device called “{name}”.", name=name) + (" " + tr("Did you mean: {names}?", names=", ".join(d["name"] for d in some[:6])) if some else ""))

    async def homey_find(self, text="*"):
        """Records (name, zone, class, and each capability) for devices whose name, zone or class contain every word."""
        words = [w for w in to_str(text).lower().split() if w != "*"]
        found = [d for d in await self._homey_home() if all(w in f"{d['name']} {d['zone']} {d['class']}".lower() for w in words)]
        return [dict({"name": d["name"], "zone": d["zone"], "class": d["class"]}, **{k: self._homey_show(v) if isinstance(v, bool) else v for k, v in d["caps"].items()})
                for d in found]

    async def homey_find_text(self, text="*"):
        words = [w for w in to_str(text).lower().split() if w != "*"]
        found = [d for d in await self._homey_home() if all(w in f"{d['name']} {d['zone']} {d['class']}".lower() for w in words)]
        return "\n".join(self._homey_line(d) for d in found) or f"No Homey devices match “{to_str(text).strip()}”."

    async def homey_value(self, capability, device):
        d = await self._homey_device(device)
        cap = to_str(capability).strip()
        if cap not in d["caps"]:
            raise RunError(tr("{name} has no “{cap}”. It has: {x}.", name=d['name'], cap=cap, x=', '.join(d['caps']) or tr('nothing')))
        v = d["caps"][cap]
        return self._homey_show(v) if isinstance(v, bool) else v

    @staticmethod
    def _homey_value_for(old, value):
        """Turns 'on', 'yes', '50' and so on into the kind of value the capability holds."""
        v = value
        if isinstance(old, bool) or (isinstance(v, str) and v.strip().lower() in ("on", "off", "true", "false", "yes", "no")):
            if isinstance(v, str):
                t = v.strip().lower()
                if t not in ("on", "off", "true", "false", "yes", "no", "1", "0"):
                    raise RunError(tr("“{value}” isn't on or off.", value=value))
                return t in ("on", "true", "yes", "1")
            return bool(v)
        if isinstance(old, (int, float)):
            if not _num_like(v):
                raise RunError(tr("“{value}” isn't a number.", value=value))
            return num(v)
        return to_str(v) if not isinstance(v, (int, float, bool)) else v

    async def homey_set(self, device, capability, value, approved=False):
        d = await self._homey_device(device)
        cap = to_str(capability).strip()
        if cap not in d["caps"]:
            raise RunError(tr("{name} has no “{cap}”. It has: {x}.", name=d['name'], cap=cap, x=', '.join(d['caps']) or tr('nothing')))
        v = self._homey_value_for(d["caps"][cap], value)
        what = f"set {d['name']} {cap} to {self._homey_show(v)}"
        if (cap, v) in self.HOMEY_SENSITIVE and not self.dry_run():  # unlocking, opening and disarming always ask, unless you've just said yes to this very change
            if not approved and not await self.confirm(what + " (a safety check: unlocking, opening and disarming always ask)"):
                return False
        elif (not approved or self.dry_run()) and not await self._allowed(["ha"], what):
            return False
        await self._homey("PUT", f"/devices/device/{urllib.parse.quote(d['id'])}/capability/{urllib.parse.quote(cap)}", {"value": v})
        self.log(tr("Homey: {name}", name=d["name"]), f"{cap}: {self._homey_show(d['caps'][cap])} → {self._homey_show(v)}", tr("done"))
        return True

    async def _homey_flows(self):
        flows = []
        for path, adv in (("/flow/flow/", False), ("/flow/advancedflow/", True)):
            try:
                for f in (await self._homey("GET", path) or {}).values():
                    flows.append({"id": f.get("id"), "name": f.get("name", ""), "advanced": adv, "enabled": f.get("enabled", True),
                                  "triggerable": f.get("triggerable", True)})
            except RunError:
                if not adv:
                    raise
        return flows

    async def homey_flows_text(self):
        return "\n".join(f"{f['name']}" + (" (advanced)" if f["advanced"] else "") + ("" if f["enabled"] else " (turned off)")
                         for f in sorted(await self._homey_flows(), key=lambda f: f["name"].lower())) or "No flows."

    async def homey_run_flow(self, name, approved=False):
        name = to_str(name).strip()
        flows = await self._homey_flows()
        f = next((x for x in flows if x["name"].lower() == name.lower()), None) or \
            (lambda c: c[0] if len(c) == 1 else None)([x for x in flows if name.lower() in x["name"].lower()])
        if not f:
            raise RunError(tr("There's no Homey flow called “{name}”.", name=name))
        if (not approved or self.dry_run()) and not await self._allowed(["ha"], f"start the Homey flow “{f['name']}”"):
            return False
        await self._homey("POST", ("/flow/advancedflow/" if f["advanced"] else "/flow/flow/") + urllib.parse.quote(f["id"]) + "/trigger", {})
        self.log(tr("Homey flow started"), f["name"], tr("started"))
        return True

    async def _homey_var(self, name):
        name = to_str(name).strip()
        vs = list((await self._homey("GET", "/logic/variable/") or {}).values())
        v = next((x for x in vs if x.get("name", "").lower() == name.lower()), None)
        if not v:
            raise RunError(tr("There's no Homey variable called “{name}”.", name=name) + (" " + tr("Its variables are: {names}", names=", ".join(x.get("name", "") for x in vs[:12])) if vs else ""))
        return v

    async def homey_variable(self, name):
        return (await self._homey_var(name)).get("value", "")

    async def homey_set_variable(self, name, value, approved=False):
        v = await self._homey_var(name)
        old = v.get("value")
        new = self._homey_value_for(old, value) if v.get("type") in ("boolean", "number") else to_str(value)
        if (not approved or self.dry_run()) and not await self._allowed(["ha"], f"set the Homey variable “{v['name']}” to {self._homey_show(new)}"):
            return False
        await self._homey("PUT", "/logic/variable/" + urllib.parse.quote(v["id"]), {"value": new})
        self.log(tr("Homey variable {name}", name=v["name"]), f"{self._homey_show(old)} → {self._homey_show(new)}", tr("set"))
        return True

    async def _listen_homey(self, items):
        """'when Homey device … changes': checks every 10 seconds and starts the script when a value changes."""
        before = None
        print(tr("Watching Homey devices for changes."), flush=True)
        while True:
            try:
                home = await self._homey_home()
                now = {(d["name"], k): (v, d) for d in home for k, v in d["caps"].items()}
                if before is not None:
                    for (dname, cap), (v, d) in now.items():
                        if (dname, cap) not in before or before[(dname, cap)][0] == v:
                            continue
                        old = before[(dname, cap)][0]
                        for arg, fn in items:
                            want_dev, _, want_cap = to_str(arg).partition("|")
                            want_cap = want_cap.strip().lower()
                            if want_dev.strip().lower() not in (dname.lower(), d["id"]) or want_cap not in ("", "anything", cap.lower()):
                                continue
                            rec = {"device": dname, "zone": d["zone"], "capability": cap, "from": self._homey_show(old) if isinstance(old, bool) else old,
                                   "to": self._homey_show(v) if isinstance(v, bool) else v,
                                   "text": f"{dname} {cap}: {self._homey_show(old)} → {self._homey_show(v)}"}
                            self._fire(fn, rec, f"Homey: {dname} {cap}")
                before = now
            except RunError as e:
                print(tr("  (Homey check failed: {e})", e=e), flush=True)
            await asyncio.sleep(self._poll(10))
