        if has("telegram_read", "telegram_send"):
            async def tg():
                me = await self._tg("getMe")
                chat = "" if os.environ.get("TELEGRAM_CHAT_ID") else (" (no TELEGRAM_CHAT_ID yet: message your bot, then run a "
                                                                      "Telegram program to see your chat number)")
                return tr("the bot is @{x}{chat}", x=to_str((me or {}).get("username")), chat=chat)
            out.append(("Telegram", tg))
