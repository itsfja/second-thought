        if has("docker_read", "docker_control"):
            async def docker():
                version = to_str((await self._docker("GET", "/version")).get("Version"))
                n = len(await self._docker("GET", "/containers/json", {"all": "1"}))
                return tr("Docker {version}", version=version or "?") + ", " + tr("{n} containers", n=n)
            out.append(("Docker", docker))
