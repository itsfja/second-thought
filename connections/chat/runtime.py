    # Discord and Slack: the same shape for both. Only the channels in the settings are read or posted in.
    CHATS = {"discord": {"name": "Discord", "token": "DISCORD_BOT_TOKEN", "channels": "DISCORD_CHANNEL_ID", "limit": 2000,
                         "make": "a bot in the Discord Developer Portal (Applications, your app, Bot), with the Message Content intent on"},
             "slack": {"name": "Slack", "token": "SLACK_BOT_TOKEN", "channels": "SLACK_CHANNEL_ID", "limit": 3500,
                       "make": "a Slack app (api.slack.com/apps) with a bot token and the channels:history and chat:write scopes"}}

    def _chat_channels(self, service):
        return [c for c in re.split(r"[\s,]+", os.environ.get(self.CHATS[service]["channels"], "")) if c]

    async def _chat_api(self, service, method, path, body=None, query=None):
        c = self.CHATS[service]
        token = os.environ.get(c["token"], "").strip()
        if not token:
            raise RunError(tr("{name} needs {token} {where_keys}: make {make}.", name=c['name'], token=c['token'], where_keys=WHERE_KEYS, make=c['make']))
        base = DISCORD_API if service == "discord" else SLACK_API
        url = base + path + ("?" + urllib.parse.urlencode(query) if query else "")
        req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": ("Bot " if service == "discord" else "Bearer ") + token,
                                              "Content-Type": "application/json; charset=utf-8", "User-Agent": "SecondThought (+https://claude.ai)"})

        def go():
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = json.loads(r.read() or b"null")
            except urllib.error.HTTPError as e:
                why = {401: f"the bot token was refused. Check {c['token']}", 403: "the bot isn't allowed in that channel. Add it to the channel and give it permission to read and send messages",
                       404: "there's no such channel, or the bot can't see it", 429: "it's asking the program to slow down. Try again in a minute"}.get(e.code, f"it answered {e.code}")
                raise RunError(f"{c['name']}: {why}.") from None
            except urllib.error.URLError as e:
                raise RunError(tr("Couldn't reach {name} ({reason}).", name=c['name'], reason=e.reason)) from None
            if service == "slack" and isinstance(data, dict) and not data.get("ok"):
                err = to_str(data.get("error") or "it said no")
                why = {"not_in_channel": "the bot isn't in that channel. Invite it with /invite", "channel_not_found": "there's no such channel, or the bot can't see it",
                       "invalid_auth": f"the bot token was refused. Check {c['token']}", "missing_scope": "the app needs more scopes (channels:history and chat:write)"}.get(err, err)
                raise RunError(tr("Slack: {why}.", why=why))
            return data
        return await asyncio.to_thread(go)

    async def _chat_read(self, service, channel, after=None, limit=50):
        """(messages, newest id): messages in one channel, oldest first, as records (text, sender, channel, id), skipping
        bots, this one included. The newest id counts every message, bots too, so a listener knows where it got to."""
        out, newest = [], after
        if service == "discord":
            q = {"limit": limit, **({"after": after} if after else {})}
            raw = await self._chat_api("discord", "GET", f"/channels/{urllib.parse.quote(channel)}/messages", query=q) or []
            newest = max((m["id"] for m in raw), key=int, default=after)
            for m in sorted(raw, key=lambda x: int(x["id"])):
                a = m.get("author") or {}
                if a.get("bot") or not to_str(m.get("content")).strip():
                    continue
                out.append({"text": m["content"], "sender": a.get("global_name") or a.get("username", ""), "channel": channel, "id": m["id"],
                            "date": _parse_date(m.get("timestamp", "")) or datetime.datetime.now()})
        else:
            q = {"channel": channel, "limit": limit, **({"oldest": after} if after else {})}
            raw = [m for m in (await self._chat_api("slack", "GET", "/conversations.history", query=q) or {}).get("messages", []) if m.get("ts") != after]
            newest = max((m["ts"] for m in raw), key=float, default=after)
            for m in sorted(raw, key=lambda x: float(x["ts"])):
                if m.get("bot_id") or m.get("subtype") or not to_str(m.get("text")).strip():
                    continue
                out.append({"text": m["text"], "sender": m.get("user", ""), "channel": channel, "id": m["ts"],
                            "date": datetime.datetime.fromtimestamp(float(m["ts"]))})
        return out, newest

    def _chat_need_channels(self, service):
        chans = self._chat_channels(service)
        if not chans:
            c = self.CHATS[service]
            raise RunError(tr("{name} needs {channels} {where}: the channels it reads and posts in (anyone can post in a server, so only these count)." if service == "discord"
                              else "{name} needs {channels} {where}: the channels it reads and posts in (anyone can post in a workspace, so only these count).",
                              name=c["name"], channels=c["channels"], where=WHERE_KEYS))
        return chans

    async def chat_search(self, service, text="", limit=20):
        words, found = to_str(text).lower().split(), []
        for ch in self._chat_need_channels(service):
            found += [m for m in (await self._chat_read(service, ch, limit=100))[0] if all(w in m["text"].lower() for w in words)]
        found.sort(key=lambda m: m["date"], reverse=True)
        name = self.CHATS[service]["name"]
        return "\n".join(f"{_when(m['date'])} · {m['sender']} in {m['channel']}: {_short(m['text'], 300)}" for m in found[:max(1, min(50, round_js(num(limit)) or 20))]) \
            or (f"No {name} messages found" + (f" with “{text}”" if words else "") + f". Only the channels in {self.CHATS[service]['channels']} are read.")

    async def chat_send(self, service, text, channel="", approved=False):
        c = self.CHATS[service]
        text = to_str(text).strip()
        if not text:
            raise RunError(tr("A {name} message needs some text.", name=c['name']))
        mine = self._chat_need_channels(service)
        trig = MESSAGE_VALUE.get()
        channel = to_str(channel).strip() or (trig.get("channel") if isinstance(trig, dict) and trig.get("service") == service else "") or mine[0]
        if channel not in mine:
            raise RunError(tr("{name}: channel {channel} isn't in {channels}, so nothing is sent there.", name=c['name'], channel=channel, channels=c['channels']))
        if (not approved or self.dry_run()) and not await self._allowed(["messages"], f"send a {c['name']} message: {_short(text, 120)}"):
            return False
        for i in range(0, len(text), c["limit"]):
            part = text[i:i + c["limit"]]
            if service == "discord":
                await self._chat_api("discord", "POST", f"/channels/{urllib.parse.quote(channel)}/messages", {"content": part, "allowed_mentions": {"parse": []}})
            else:
                await self._chat_api("slack", "POST", "/chat.postMessage", {"channel": channel, "text": markdown_to_slack(part)})
        self.log(tr("{name} message sent", name=c['name']), text, tr("sent"))
        return True

    async def _listen_chat(self, service, items):
        """'when a Discord/Slack message arrives': checks each channel every 10 seconds. Messages already there at the start don't count."""
        chans = self._chat_need_channels(service)
        last = {ch: (await self._chat_read(service, ch, limit=1))[1] for ch in chans}
        if service == "slack":  # Slack's 'oldest' is a time; start from now if the channel was empty
            last = {ch: v or f"{time.time():.6f}" for ch, v in last.items()}
        print(tr("Listening for {name} messages in {x}.", name=self.CHATS[service]['name'], x=", ".join(chans)), flush=True)
        while True:
            await asyncio.sleep(self._poll(10))
            for ch in chans:
                try:
                    new, last[ch] = await self._chat_read(service, ch, after=last[ch])
                except RunError as e:
                    print(tr("  ({name} check failed: {e})", name=self.CHATS[service]['name'], e=e), flush=True)
                    continue
                for m in new:
                    rec = {"service": service, "text": m["text"], "sender": m["sender"], "channel": ch, "id": m["id"]}
                    for contains, fn in items:
                        want = to_str(contains).strip().lower()
                        if want in ("", "anything") or want in m["text"].lower():
                            self._fire(fn, dict(rec), tr("{name} message", name=self.CHATS[service]['name']))

    async def _listen_discord(self, items):
        await self._listen_chat("discord", items)

    async def _listen_slack(self, items):
        await self._listen_chat("slack", items)
