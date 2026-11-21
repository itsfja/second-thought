    async def _doctor_mikrotik(self):
        """The MikroTik check (#360): reachable, the certificate pinned, and an account that can only read."""
        base = os.environ.get("MIKROTIK_URL", "").strip()
        pinned = os.environ.get("MIKROTIK_CERT_SHA256", "").strip()
        if base and not base.lower().startswith("http://") and not pinned:
            seen = await asyncio.to_thread(self._mt_fingerprint, base)
            if seen:
                raise RunError(tr("the router's certificate is its own, so pin it: if {url} is your {who}, put {setting} = {seen} in second-thought.ini.", url=base, who="MikroTik", setting="MIKROTIK_CERT_SHA256", seen=seen))
        res = await self.mikrotik_health()
        user = os.environ.get("MIKROTIK_USER", "").strip()
        group = next((to_str(u.get("group")) for u in await self._mikrotik("GET", "/rest/user") if isinstance(u, dict) and u.get("name") == user), "")
        policy = next((to_str(g.get("policy")) for g in await self._mikrotik("GET", "/rest/user/group") if isinstance(g, dict) and g.get("name") == group), "")
        extra = sorted({p for p in policy.split(",") if p and not p.startswith("!")} - {"read", "api", "rest-api"})
        said = tr("{board}, RouterOS {version}", board=res.get("board") or "MikroTik", version=res.get("version") or "?")
        if base.lower().startswith("http://"):
            return "NOTE", said + "; " + tr("the password goes unencrypted over http://. Use the www-ssl service and https:// instead.")
        if extra:
            return "NOTE", said + "; " + tr("the account's group ({group}) can also {what}. Second Thought only reads, so a group with just read, api and rest-api is safer.", group=group, what=", ".join(extra))
        return said
