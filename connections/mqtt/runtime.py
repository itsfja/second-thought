    # MQTT
    def _mqtt_new(self, on_message=None, topics=()):
        """A connected MQTT client, running in the background. Subscribes (again after a reconnect) to these topics."""
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            raise RunError(tr("MQTT needs the paho-mqtt package: pip install paho-mqtt")) from None
        host = os.environ.get("MQTT_HOST", "").strip()
        if not host:
            raise RunError(tr("MQTT needs MQTT_HOST {where_keys}: your broker's address, like homeassistant.local.", where_keys=WHERE_KEYS))
        tls = os.environ.get("MQTT_TLS", "").strip().lower() in ("1", "yes", "true", "on")
        port = int(os.environ.get("MQTT_PORT") or (8883 if tls else 1883))
        c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if os.environ.get("MQTT_USERNAME"):
            c.username_pw_set(os.environ["MQTT_USERNAME"], os.environ.get("MQTT_PASSWORD") or None)
        if tls:
            c.tls_set()
        ready, result = threading.Event(), {}

        def on_connect(client, userdata, flags, reason_code, properties):
            result["rc"] = reason_code
            if not reason_code.is_failure:
                for t in topics:
                    client.subscribe(t, qos=0)
            ready.set()
        c.on_connect = on_connect
        if on_message:
            c.on_message = on_message
        try:
            c.connect(host, port, keepalive=60)
        except OSError as e:
            raise RunError(tr("Couldn't reach the MQTT broker at {host}:{port} ({e}).", host=host, port=port, e=e)) from None
        c.loop_start()
        if not ready.wait(10) or result["rc"].is_failure:
            c.loop_stop()
            raise RunError(tr("The MQTT broker at {host}:{port} refused the connection ({rc}). Check MQTT_USERNAME and MQTT_PASSWORD.", host=host, port=port, rc=result["rc"])
                           if "rc" in result else tr("The MQTT broker at {host}:{port} didn't answer.", host=host, port=port))
        return c

    @staticmethod
    def _mqtt_payload(topic, raw):
        """An MQTT message as a record: its topic and text, plus the fields of a JSON message (like zigbee2mqtt's)."""
        text = raw.decode("utf-8", "replace") if isinstance(raw, (bytes, bytearray)) else to_str(raw)
        rec = {"topic": topic, "text": text}
        try:
            j = json.loads(text)
        except ValueError:
            j = None
        if isinstance(j, dict):
            for k, v in j.items():
                rec.setdefault(str(k), json.dumps(v) if isinstance(v, (dict, list)) else v)
        return rec

    @staticmethod
    def _mqtt_topic(topic, publishing=False):
        topic = to_str(topic).strip()
        if not topic:
            raise RunError(tr("MQTT needs a topic, like home/kitchen/temperature."))
        if publishing and ("+" in topic or "#" in topic):
            raise RunError(tr("You can't publish to a topic with + or # in it: those only work for listening."))
        return topic

    async def mqtt_read(self, topic, wait=2.0):
        """The latest messages on a topic (+ and # allowed): {topic: text}. Retained messages arrive straight away."""
        topic, got = self._mqtt_topic(topic), {}

        def on_message(client, userdata, msg):
            if len(got) < 200:
                got[msg.topic] = self._mqtt_payload(msg.topic, msg.payload)["text"]
        c = await asyncio.to_thread(self._mqtt_new, on_message, [topic])
        try:
            await asyncio.sleep(wait)
        finally:
            c.loop_stop()
            c.disconnect()
        return got

    async def mqtt_value(self, topic):
        """For the 'latest MQTT message' block: the text, or a record of topic -> text for a topic with + or #."""
        got = await self.mqtt_read(topic)
        topic = to_str(topic).strip()
        if "+" not in topic and "#" not in topic:
            v = got.get(topic, "")
            self.log(tr("MQTT {topic}", topic=topic), v or tr("(no message yet: only messages the broker keeps show up straight away)"), tr("read"))
            return v
        self.log(tr("MQTT {topic}", topic=topic), "\n".join(f"{k}: {_short(v, 80)}" for k, v in sorted(got.items())) or tr("(nothing)"), tr("{got} topics", got=len(got)))
        return got

    async def mqtt_publish(self, topic, text, retain=False, approved=False):
        topic, text = self._mqtt_topic(topic, True), to_str(text)
        if (not approved or self.dry_run()) and not await self._allowed(["ha", "messages"], f"publish to MQTT {topic}: {_short(text, 120)}"):
            return False
        c = await asyncio.to_thread(self._mqtt_new)
        try:
            info = c.publish(topic, text, qos=1, retain=bool(retain))
            await asyncio.to_thread(info.wait_for_publish, 10)
        finally:
            c.loop_stop()
            c.disconnect()
        self.log(tr("MQTT → {topic}", topic=topic), text + ("  " + tr("(kept by the broker)") if retain else ""), tr("published"))
        return True

    async def _listen_mqtt(self, items):
        import paho.mqtt.client as mqtt
        loop = asyncio.get_running_loop()

        def on_message(client, userdata, msg):
            if msg.retain:
                return  # a kept message is an old value, not something that has just arrived
            payload = self._mqtt_payload(msg.topic, msg.payload)
            for sub_, fn in items:
                if mqtt.topic_matches_sub(sub_, msg.topic):
                    loop.call_soon_threadsafe(self._fire, fn, dict(payload), "MQTT " + msg.topic)
        await asyncio.to_thread(self._mqtt_new, on_message, sorted({self._mqtt_topic(t) for t, _ in items}))
        print(tr("Listening for MQTT messages on {x}.", x=", ".join(sorted({t for t, _ in items}))), flush=True)
        while True:
            await asyncio.sleep(3600)
