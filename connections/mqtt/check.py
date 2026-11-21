        if has("mqtt_read", "mqtt_publish"):
            async def mqtt():
                await self.mqtt_read("second-thought/doctor", 1.0)
                return tr("connected to the broker")
            out.append(("MQTT", mqtt))
