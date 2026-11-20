        if has("nzbgeek_read", "nzbgeek_fetch"):
            async def nzbgeek():
                raw = await self._nzbgeek({"t": "caps", "o": "json"})
                caps = (json.loads(raw) if raw.strip() else {}).get("caps") or {}
                server = (caps.get("server") or {}).get("@attributes") or {}
                ret = caps.get("retention")
                days = num((ret or {}).get("@attributes", {}).get("days")) if isinstance(ret, dict) else num(ret)
                return tr("NZBGeek {version}", version=to_str(server.get("version")) or "?") \
                    + ", " + tr("{n} days of retention", n=days or "?")
            out.append(("NZBGeek", nzbgeek))
