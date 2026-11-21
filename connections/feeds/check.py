        if has("feeds") and os.environ.get("RB_FEEDS", "").strip():
            async def feeds():
                items = await self.feed_items("", 3)
                return tr("read your feeds ({items} items)", items=len(items))
            out.append(("News feeds", feeds))
