        if has("plex_read", "plex_control"):
            async def plex():
                home = await self._plex("GET", "/")
                libs = await self._plex("GET", "/library/sections")
                return tr("Plex {version}", version=to_str(home.get("version")) or "?") \
                    + ", " + tr("{n} libraries", n=len([d for d in (libs.get("Directory") or []) if isinstance(d, dict)]))
            out.append(("Plex", plex))
            async def tautulli():
                r = await self._tautulli("get_history", {"length": "1"})
                data = (r.get("data") or {}) if isinstance(r.get("data"), dict) else {}
                return tr("Tautulli") + ", " + tr("{n} plays", n=num(data.get("recordsFiltered")))
            out.append(("Tautulli", tautulli))
