        if has("ha_read", "ha_act"):
            async def ha():
                await self._ha("GET", "/api/")
                cfg = await self._ha("GET", "/api/config")
                return f"reached Home Assistant {cfg.get('version', '')}".strip() if isinstance(cfg, dict) else tr("reached")
            out.append(("Home Assistant", ha))
