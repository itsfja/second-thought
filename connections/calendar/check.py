        if has("calendar"):
            async def cal():
                lines = await self.calendar_text("today", 7)
                return tr("read the next 7 days ({x} lines)", x=len(to_str(lines).splitlines()))
            out.append(("Calendar", cal))
