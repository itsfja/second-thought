        if has("sabnzbd_read", "sabnzbd_control"):
            async def sabnzbd():
                q = (await self._sabnzbd("queue")).get("queue") or {}
                return tr("SABnzbd {version}", version=to_str(q.get("version")) or "?") + ", " + tr("{n} in the queue", n=len(q.get("slots") or []))
            out.append(("SABnzbd", sabnzbd))
