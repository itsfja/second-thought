        for svc, name in (("discord", "Discord"), ("slack", "Slack")):
            if has(svc + "_read", svc + "_send"):
                async def chat(svc=svc):
                    await self.chat_search(svc, "", 5)
                    return tr("read your channels")
                out.append((name, chat))
