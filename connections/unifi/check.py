        if has("unifi_read"):
            async def unifi():
                base = os.environ.get("UNIFI_URL", "").strip()
                if base and not os.environ.get("UNIFI_CERT_SHA256", "").strip():
                    seen = await asyncio.to_thread(self._mt_fingerprint, base)
                    if seen:
                        raise RunError(tr("the router's certificate is its own, so pin it: if {url} is your {who}, put {setting} = {seen} in second-thought.ini.", url=base, who="UniFi console", setting="UNIFI_CERT_SHA256", seen=seen))
                info = await self._unifi("/info")
                site = await self._unifi_site()
                devices = await self._unifi_all(f"/sites/{site}/devices")
                return tr("UniFi Network {version}, {n} devices", version=to_str(info.get("applicationVersion")) or "?", n=len(devices))
            out.append(("UniFi", unifi))
