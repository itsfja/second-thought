        if has("arr_read", "arr_control"):
            async def arr(which):
                status = await self._arr(which, "GET", "/api/v3/system/status")
                q = await self._arr(which, "GET", "/api/v3/queue", {"page": "1", "pageSize": "1"})
                return tr("{who} {version}", who=which.capitalize(), version=to_str(status.get("version")) or "?") \
                    + ", " + tr("{n} in the queue", n=num(q.get("totalRecords") or 0))
            out.append(("Radarr", lambda: arr("radarr")))
            out.append(("Sonarr", lambda: arr("sonarr")))
