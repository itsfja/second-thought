    # MQTT messages an agent can't publish without asking (matched in the topic and message, any case).
    "mqtt_unlock": r"\b(unlock|open|disarm)",
    # MQTT: MQTT_HOST is your broker (for example homeassistant.local, if it runs Mosquitto), with MQTT_USERNAME and
    # MQTT_PASSWORD if it needs them. MQTT_TLS = yes for an encrypted connection (port 8883). Needs  pip install paho-mqtt.
