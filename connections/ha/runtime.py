    # ----- Home Assistant -----
    def _ha_request(self, method, path, body=None, raw=False):
        if not HA_TOKEN:
            raise RunError(tr("This program uses Home Assistant. Put HA_URL (for example http://homeassistant.local:8123) and HA_TOKEN (a long-lived access token from your Home Assistant profile, Security tab) {where_keys}.", where_keys=WHERE_KEYS))
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(HA_URL + path, data=data, method=method,
                                     headers={"Authorization": "Bearer " + HA_TOKEN, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                payload = r.read()
                return (payload, r.headers.get("Content-Type", "")) if raw else (json.loads(payload or b"null"))
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise RunError(tr("Home Assistant refused the token (401). Check HA_TOKEN."))
            if e.code == 404:
                raise RunError(tr("Home Assistant has nothing at {path} (404). Check the entity or service name.", path=path))
            raise Retryable(tr("Home Assistant answered {code} for {path}.", code=e.code, path=path))
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise Retryable(tr("Couldn't reach Home Assistant at {ha_url} ({x}).", ha_url=HA_URL, x=getattr(e, 'reason', e)))

    async def _ha(self, method, path, body=None, raw=False):
        return await asyncio.to_thread(self._ha_request, method, path, body, raw)

    @staticmethod
    def _ha_val(v):
        return num(v) if _num_like(v) else v

    async def _ha_entity(self, entity):
        entity = to_str(entity).strip()
        if not re.match(r"^[a-z_]+\.[a-z0-9_]+$", entity):
            raise RunError(tr("“{entity}” isn't an entity id. Use something like light.kitchen.", entity=entity))
        return await self._ha("GET", "/api/states/" + entity)

    async def ha_state(self, entity):
        return self._ha_val((await self._ha_entity(entity))["state"])

    async def ha_attr(self, attr, entity):
        e = await self._ha_entity(entity)
        attr = to_str(attr).strip()
        if attr == "state":
            return self._ha_val(e["state"])
        v = e.get("attributes", {}).get(attr, "")
        return self._ha_val(v) if not isinstance(v, (list, dict)) else json.dumps(v)

    async def _ha_match(self, text):
        words = [w for w in re.split(r"[\s,]+", to_str(text).lower()) if w]
        out = []
        for e in await self._ha("GET", "/api/states"):
            a = e.get("attributes", {})
            hay = " ".join(to_str(x) for x in (e["entity_id"], a.get("friendly_name"), a.get("area"), e["state"],
                                                a.get("device_class"), a.get("unit_of_measurement"))).lower()
            if not words or "*" in words or all(w in hay for w in words):
                out.append(e)
        return out[:150]

    async def ha_find(self, text):
        return [{"entity": e["entity_id"], "name": e.get("attributes", {}).get("friendly_name", e["entity_id"]),
                 "state": self._ha_val(e["state"]), "unit": e.get("attributes", {}).get("unit_of_measurement", ""),
                 "area": e.get("attributes", {}).get("area", "")} for e in await self._ha_match(text)]

    async def ha_summary(self, text):
        lines = []
        for e in await self._ha_match(text):
            a = e.get("attributes", {})
            extra = "".join(f"; {k.replace('_', ' ')}: {v}" for k, v in a.items()
                            if k not in ("friendly_name", "area", "unit_of_measurement", "device_class", "icon", "entity_picture",
                                         "supported_features", "attribution", "state_class") and not isinstance(v, (list, dict)))
            unit = " " + a["unit_of_measurement"] if a.get("unit_of_measurement") else ""
            area = f" [{a['area']}]" if a.get("area") else ""
            lines.append(f"{a.get('friendly_name', e['entity_id'])} ({e['entity_id']}): {e['state']}{unit}{area}{extra}")
        return "\n".join(lines) or "(no matching entities)"

    async def ha_history(self, entity, hours):
        entity = to_str(entity).strip()
        hours = max(1, min(168, num(hours) or 24))
        start = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)).isoformat()
        q = urllib.parse.urlencode({"filter_entity_id": entity, "minimal_response": "", "no_attributes": ""})
        data = await self._ha("GET", "/api/history/period/" + urllib.parse.quote(start) + "?" + q)
        rows = data[0] if data else []
        if len(rows) > 48:
            step = len(rows) / 48
            rows = [rows[int(i * step)] for i in range(48)] + [rows[-1]]
        out = []
        for r in rows:
            try:
                t = datetime.datetime.fromisoformat(r.get("last_changed", "").replace("Z", "+00:00")).astimezone()
                label = t.strftime("%a %H:%M")
            except ValueError:
                label = r.get("last_changed", "")
            out.append({"time": label, "state": self._ha_val(r.get("state", ""))})
        return out

    async def ha_snapshot(self, camera):
        camera = to_str(camera).strip()
        data, ctype = await self._ha("GET", "/api/camera_proxy/" + camera, raw=True)
        pic = Picture(data, (ctype or "image/jpeg").split(";")[0], camera.replace("camera.", "") + "-snapshot")
        self.log(tr("Snapshot: {camera}", camera=camera), tr("Saved to {x}", x=self._picture_path(pic)), tr("done"))
        return pic

    async def _ha_call_live(self, service, entity, data_text=""):
        service, entity = to_str(service).strip(), to_str(entity).strip()
        if not re.match(r"^[a-z_]+\.[a-z0-9_]+$", service):
            raise RunError(tr("“{service}” isn't a service name. Use domain.service, for example light.turn_off.", service=service))
        body = {}
        if to_str(data_text).strip():
            try:
                body = json.loads(to_str(data_text))
            except ValueError:
                raise RunError(tr("The data for {service} isn't valid JSON. Use something like {\"temperature\": 20}.", service=service))
        if entity:
            body["entity_id"] = entity
        sensitive = ha_sensitive(service, entity, body)
        if (not sensitive or self.dry_run()) and not await self._allowed(["ha"], f"{service} on {entity or 'Home Assistant'}"):
            return False
        if sensitive:
            if self.nobody_here():
                self.log(tr("Not done"), tr("{service} on {entity} needs your approval, and nobody is at the keyboard.", service=service, entity=entity or "Home Assistant"), tr("refused"))
                return False
            if not await self.approve(f"Allow {service} on {entity or 'Home Assistant'}? (unlocking, opening and disarming always ask)"):
                self.log(tr("Not done"), tr("{service} on {entity} was refused, so nothing happened.", service=service, entity=entity or "Home Assistant"), tr("refused"))
                return False
            self._receipt(f"{service} on {entity or 'Home Assistant'}", tr("yes at the keyboard"), kinds=["ha"])
        domain, action = service.split(".", 1)
        await self._ha("POST", f"/api/services/{domain}/{action}", body)
        self.log(tr("Home Assistant: {service}", service=service), entity + (" " + tr("with {data}", data=to_str(data_text).strip()) if to_str(data_text).strip() else ""), tr("done"))
        return True

    async def _ha_notify_live(self, target, text):
        target, text = to_str(target).strip() or "persistent_notification", to_str(text)
        if not text.strip():
            raise RunError(tr("The 'notify' block has no message."))
        if not await self._allowed(["ha", "messages"], f"send a notification to {target}: {_short(text, 120)}"):
            return
        if target in ("persistent_notification", "persistent_notification.create"):
            await self._ha("POST", "/api/services/persistent_notification/create", {"message": text, "title": "Second Thought"})
        else:
            svc = target.split(".", 1)[1] if target.startswith("notify.") else target
            await self._ha("POST", f"/api/services/notify/{svc}", {"message": text, "title": "Second Thought"})
        self.log(tr("Notification → {target}", target=target), text, tr("sent"))

    async def _ha_speak_live(self, text, player):
        text, player = to_str(text), to_str(player).strip()
        if not text.strip():
            raise RunError(tr("The 'say' block has nothing to say."))
        if not await self._allowed(["ha", "messages"], f"say on {player or 'a speaker'}: {_short(text, 120)}"):
            return
        await self._ha("POST", "/api/services/tts/speak", {"entity_id": HA_TTS_ENTITY, "media_player_entity_id": player, "message": text})
        self.log(tr("Spoken on {player}", player=player), text, tr("sent"))

    @staticmethod
    def ha_trigger():
        v = MESSAGE_VALUE.get()
        return v if isinstance(v, dict) else {"entity": "", "name": "", "from": "", "to": ""}

    async def _listen_ha_event(self, items):
        """'when Home Assistant event … happens': subscribes to Home Assistant's events over its WebSocket API, so a button press,
        an automation firing or a custom event starts the script at once. Reconnects (after a minute) if the connection drops."""
        if not HA_TOKEN:
            raise RunError(tr("Home Assistant events need HA_URL and HA_TOKEN {where_keys}.", where_keys=WHERE_KEYS))
        wants = []
        for arg, fn in items:
            kind, _, words = to_str(arg).partition("|")
            kind = kind.strip()
            wants.append(("" if kind.lower() in ("", "anything") else kind, words.lower().split(), fn))
        url = re.sub(r"^http", "ws", HA_URL) + "/api/websocket"
        try:
            ws = await _WebSocket.connect(url, timeout=10)
        except asyncio.TimeoutError:
            raise RunError(tr("Home Assistant didn't answer at {url} within 10 seconds.", url=url)) from None
        try:
            # Home Assistant answers these at once; a stalled sign-in becomes an error, so the listener tries again.
            try:
                hello = await asyncio.wait_for(ws.recv_json(), 10)
                if hello.get("type") == "auth_required":
                    await ws.send_json({"type": "auth", "access_token": HA_TOKEN})
                    hello = await asyncio.wait_for(ws.recv_json(), 10)
            except asyncio.TimeoutError:
                raise RunError(tr("Home Assistant didn't finish signing in for events within 10 seconds.")) from None
            if hello.get("type") != "auth_ok":
                raise RunError(tr("Home Assistant refused the token for events (auth_invalid). Check HA_TOKEN."))
            kinds = [None] if any(k == "" for k, _, _ in wants) else sorted({k for k, _, _ in wants})
            for n, kind in enumerate(kinds, 1):
                await ws.send_json(dict({"id": n, "type": "subscribe_events"}, **({"event_type": kind} if kind else {})))
            print(tr("Listening for Home Assistant events: {x}.", x=", ".join(k or tr("everything") for k in kinds)), flush=True)
            while True:
                msg = await ws.recv_json()
                if msg.get("type") == "result" and not msg.get("success", True):
                    raise RunError(tr("Home Assistant wouldn't send those events: {x}", x=to_str((msg.get("error") or {}).get("message"))))
                if msg.get("type") != "event":
                    continue
                ev = msg.get("event") or {}
                kind, data = to_str(ev.get("event_type")), ev.get("data") or {}
                blob = json.dumps(data, ensure_ascii=False, default=str)
                rec = {"event_type": kind, "entity": to_str(data.get("entity_id", "")), "data": blob, "time": to_str(ev.get("time_fired", "")),
                       "text": f"{kind}: {_short(blob, 400)}"}
                for k, v in data.items():
                    rec.setdefault(str(k), json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
                for want, words, fn in wants:
                    if (not want or want == kind) and all(w in blob.lower() for w in words):
                        self._fire(fn, dict(rec), tr("Home Assistant: {x}", x=kind))
        finally:
            ws.close()
