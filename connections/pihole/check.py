        if has("pihole_read", "pihole_control"):
            async def pihole():
                s = await self._pihole("GET", "/api/stats/summary")
                q = (s.get("queries") or {})
                return tr("{n} queries, {blocked} blocked", n=num(q.get("total")), blocked=num(q.get("blocked")))
            out.append(("Pi-hole", pihole))
