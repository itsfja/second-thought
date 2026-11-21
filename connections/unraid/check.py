        if has("unraid_read", "unraid_control"):
            async def unraid():
                d = await self._unraid("query{vars{version}array{state}}")
                return tr("Unraid {version}", version=to_str((d.get("vars") or {}).get("version")) or "?") \
                    + ", " + tr("array {state}", state=to_str((d.get("array") or {}).get("state")) or "?")
            out.append(("Unraid", unraid))
