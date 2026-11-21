    # Telegram
    def _tg_chats(self):
        return [c for c in re.split(r"[\s,]+", os.environ.get("TELEGRAM_CHAT_ID", "")) if c]

    async def _tg(self, method, params=None, wait=0):
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        if not token:
            raise RunError(tr("Telegram needs a bot: set TELEGRAM_BOT_TOKEN {where_keys} (message @BotFather in Telegram to make one).", where_keys=WHERE_KEYS))
        req = urllib.request.Request(f"{TELEGRAM_API}/bot{token}/{method}", data=json.dumps(params or {}).encode(),
                                     headers={"Content-Type": "application/json"})

        def go():
            try:
                with urllib.request.urlopen(req, timeout=wait + 20) as r:
                    data = json.loads(r.read())
            except urllib.error.HTTPError as e:
                try:
                    data = json.loads(e.read())
                except ValueError:
                    data = {"description": f"Telegram answered {e.code}"}
            except urllib.error.URLError as e:
                raise RunError(tr("Couldn't reach Telegram ({reason}).", reason=e.reason)) from None
            if not data.get("ok"):
                raise RunError(tr("Telegram: {x}.", x=to_str(data.get("description") or tr("it said no"))))
            return data.get("result")
        return await asyncio.to_thread(go)

    def _tg_load(self):
        try:
            with open(TELEGRAM_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {"offset": 0, "messages": []}

    async def tg_fetch(self, wait=0):
        """Collects new messages to the bot, keeps those from your chats (TELEGRAM_CHAT_ID), and gives back the new ones.
        One at a time: two scripts fetching at once would read the same messages twice, or lose one."""
        async with self._lock("telegram"):  # one Telegram fetch at a time
            return await self._tg_fetch(wait)

    async def _tg_fetch(self, wait):
        offset = self._tg_load().get("offset", 0)
        updates = await self._tg("getUpdates", {"offset": offset, "timeout": wait,
                                                "allowed_updates": ["message", "channel_post"]}, wait)
        mine, new, top = self._tg_chats(), [], offset
        for u in updates or []:
            top = max(top, u["update_id"] + 1)
            m = u.get("message") or u.get("channel_post") or {}
            if "text" not in m and "caption" not in m:
                continue
            chat = m.get("chat", {})
            if str(chat.get("id")) not in mine:
                print(tr("  (A Telegram message from chat {x} was ignored. To let this program use that chat, set TELEGRAM_CHAT_ID = {x} {where_keys}.)", x=chat.get('id'), where_keys=WHERE_KEYS), flush=True)
                continue
            who = m.get("from", {})
            new.append({"text": m.get("text") or m.get("caption", ""), "sender": " ".join(x for x in (who.get("first_name"), who.get("last_name")) if x)
                        or chat.get("title", ""), "chat": str(chat.get("id")), "chat_name": chat.get("title") or chat.get("first_name", ""),
                        "date": m.get("date", 0), "update_id": u["update_id"]})
        # Another program sharing this bot may have saved messages while this one waited on Telegram. Read the file again
        # under the lock and add to what's there, skipping any message it already has, instead of writing over it.
        try:
            with _locked(TELEGRAM_FILE):
                store = self._tg_load()
                have = {m.get("update_id") for m in store.get("messages", []) if m.get("update_id") is not None}
                fresh = [m for m in new if m["update_id"] not in have]
                store["offset"] = max(store.get("offset", 0), top)
                store["messages"] = (store.get("messages", []) + fresh)[-2000:]
                _write_json(TELEGRAM_FILE, store)
            new = fresh
        except OSError:
            pass
        return new

    async def tg_search(self, text="", limit=20):
        if not getattr(self, "_tg_polling", False):
            await self.tg_fetch()
        words = to_str(text).lower().split()
        found = [m for m in sorted(self._tg_load().get("messages", []), key=lambda m: -m.get("date", 0)) if all(w in m["text"].lower() for w in words)][:max(1, min(50, round_js(num(limit)) or 20))]
        return "\n".join(f"{_when(datetime.datetime.fromtimestamp(m['date']))} · {m['sender']}: {_short(m['text'], 300)}" for m in found) \
            or ("No messages found" + (f" with “{text}”" if words else "") + ". The bot only sees messages sent to it, from the chats in TELEGRAM_CHAT_ID.")

    async def tg_send(self, text, chat="", approved=False):
        text = to_str(text).strip()
        if not text:
            raise RunError(tr("A Telegram message needs some text."))
        trig = MESSAGE_VALUE.get()
        chat = to_str(chat).strip() or (trig.get("chat") if isinstance(trig, dict) and trig.get("chat") else "") or next(iter(self._tg_chats()), "")
        if not chat:
            raise RunError(tr("Telegram needs a chat to send to: set TELEGRAM_CHAT_ID {where_keys}. Send your bot a message first; the program then says which chat it came from.", where_keys=WHERE_KEYS))
        if (not approved or self.dry_run()) and not await self._allowed(["messages"], f"send a Telegram message: {_short(text, 120)}"):
            return False
        for i in range(0, len(text), 4000):
            part = text[i:i + 4000]
            try:
                await self._tg("sendMessage", {"chat_id": chat, "text": markdown_to_telegram(part), "parse_mode": "HTML"})
            except RunError as e:
                if "parse" not in str(e).lower():  # only formatting Telegram can't read: then it goes as plain text
                    raise
                await self._tg("sendMessage", {"chat_id": chat, "text": part})
        self.log(tr("Telegram message sent"), text, tr("sent"))
        return True

    @staticmethod
    def telegram_message(part="text"):
        v = MESSAGE_VALUE.get()
        if not isinstance(v, dict) or "text" not in v:
            return ""
        return {"text": v["text"], "sender": v.get("sender", ""), "chat": v.get("chat_name") or v.get("chat", "")}.get(part, v["text"])

    async def _tg_watch(self, watches):
        """Long-polls Telegram and starts 'when a Telegram message arrives' scripts."""
        self._tg_polling = True
        started, busy = time.time() - 60, None
        while True:
            try:
                new = await self.tg_fetch(wait=25)
            except RunError as e:
                print(tr("  (Telegram check failed: {e})", e=str(e)), flush=True)
                await asyncio.sleep(15)
                continue
            for m in new:
                if m["date"] < started:
                    continue  # sent while the program wasn't running: kept for searching, not acted on
                for contains, fn in watches:
                    if contains.strip().lower() not in ("", "anything") and contains.strip().lower() not in m["text"].lower():
                        continue
                    if busy and not busy.done():
                        self.start_script(fn, m)
                    else:
                        busy = asyncio.ensure_future(self.run([(fn, m)], tr("Telegram message")))
