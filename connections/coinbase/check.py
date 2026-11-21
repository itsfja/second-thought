        if has("coinbase_read", "coinbase_trade"):
            async def coinbase():
                perms = await self._coinbase("GET", "/api/v3/brokerage/key_permissions")
                await self._coinbase("GET", "/api/v3/brokerage/accounts", {"limit": "1"})
                if perms.get("can_transfer"):
                    return "NOTE", tr("the key works, but it can also transfer money. This program never transfers: make a key without Transfer permission.")
                if "coinbase_trade" in can and not perms.get("can_trade"):
                    raise RunError(tr("the key works, but it's View only, so this program's orders would be refused. Make a key with Trade permission, limited to one portfolio."))
                if "coinbase_trade" not in can and perms.get("can_trade"):
                    return "NOTE", tr("the key works and can trade, but this program only reads: a View-only key is safer.")
                return tr("the key works: it can trade (every order asks you first)") if perms.get("can_trade") else tr("the key works, View only")
            out.append(("Coinbase", coinbase))
