        if has("github_read", "github_comment"):
            async def gh():
                await self.gh_for_me()
                return tr("read your pull requests")
            out.append(("GitHub", gh))
