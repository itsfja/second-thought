        if has("powerwall_read", "powerwall_control"):
            async def powerwall():
                base = os.environ.get("POWERWALL_URL", "").strip()
                if base and not base.lower().startswith("http://") and not os.environ.get("POWERWALL_CERT_SHA256", "").strip():
                    seen = await asyncio.to_thread(self._mt_fingerprint, base)
                    if seen:
                        raise RunError(tr("the router's certificate is its own, so pin it: if {url} is your {who}, put {setting} = {seen} in second-thought.ini.", url=base, who="Powerwall gateway", setting="POWERWALL_CERT_SHA256", seen=seen))
                got = await self.powerwall_now()
                return tr("battery at {pct}%, reserve {reserve}%, grid {grid}", pct=got.get("battery_soc_pct") or "?",
                          reserve=got.get("reserve_pct") or "?", grid=got.get("grid") or "?")
            out.append(("Powerwall", powerwall))
