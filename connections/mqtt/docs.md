## MQTT

The **MQTT** blocks read your broker's topics and publish to them (asking first), and a listener runs a script when a message arrives:

- **when an MQTT message arrives on …**, for a sensor or switch. `+` stands for one level of the topic and `#` for everything below, like `zigbee2mqtt/#`. **what arrived** gives the topic and the text, plus the fields of a JSON message (like zigbee2mqtt's).
- **latest MQTT message on …** reads a topic. Only messages the broker keeps (retained) show up straight away; with `+` or `#` in the topic, a record of each topic's latest message.
- **publish MQTT … to topic …** sends one; **keep it** asks the broker to remember it for anyone who listens later. With **ask me before any smart home action** or **sending messages and announcements**, publishing asks you first — and a message that could unlock something always asks, even then.

On the page these blocks use **sample topics** and nothing is sent: try the **Proofer too warm? (MQTT)** listener example, or **Agent: check the sensors (MQTT)**, with something you type.

**Settings:** `[mqtt]` in `second-thought.ini` — `MQTT_HOST`, your broker's address (for Mosquitto in Home Assistant, that's your Home Assistant), plus `MQTT_USERNAME` and `MQTT_PASSWORD` if it needs them. `MQTT_TLS = yes` makes it encrypted (and the port 8883 unless you set one). It needs the paho-mqtt library, which run.bat and run.sh install. `--doctor` reads a topic when the program can.
