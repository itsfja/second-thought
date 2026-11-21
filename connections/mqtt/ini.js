    if (need.mqtt) out.push("", "[mqtt]",
      "; Your MQTT broker, for example Mosquitto in Home Assistant (Settings, Add-ons). Add a username and password if it needs them.",
      "MQTT_HOST = homeassistant.local", "; MQTT_PORT = 1883", "; MQTT_USERNAME = ", "; MQTT_PASSWORD = ", "; MQTT_TLS = yes   for an encrypted connection (port 8883)");
