        if has("proxmox_read", "proxmox_control"):
            async def proxmox():
                base = os.environ.get("PROXMOX_URL", "").strip()
                if base and not os.environ.get("PROXMOX_CERT_SHA256", "").strip():
                    seen = await asyncio.to_thread(self._mt_fingerprint, base if "://" in base else "https://" + base)
                    if seen:
                        raise RunError(tr("the router's certificate is its own, so pin it: if {url} is your {who}, put {setting} = {seen} in second-thought.ini.", url=base, who="Proxmox", setting="PROXMOX_CERT_SHA256", seen=seen))
                version = to_str((await self._proxmox("GET", "/api2/json/version") or {}).get("version"))
                privs = {p for v in (await self._proxmox("GET", "/api2/json/access/permissions") or {}).values() if isinstance(v, dict) for p, on in v.items() if on}
                said = tr("Proxmox VE {version}", version=version or "?")
                if "proxmox_control" in can and "VM.PowerMgmt" not in privs:
                    raise RunError(said + "; " + tr("the token can't start or stop guests (it needs VM.PowerMgmt), so this program's power blocks would be refused."))
                more = sorted(p for p in privs if not p.endswith(".Audit") and p != "VM.PowerMgmt") + (["VM.PowerMgmt"] if "proxmox_control" not in can and "VM.PowerMgmt" in privs else [])
                if more:
                    return "NOTE", said + "; " + tr("the token can also {what}. Second Thought doesn't need that: the PVEAuditor role is safer.", what=", ".join(more[:6]))
                return said
            out.append(("Proxmox", proxmox))
