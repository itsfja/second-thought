## UniFi

The teal **UniFi** blocks read your UniFi network through the Network API on a UniFi OS console (a Cloud Gateway or a Dream Machine). They only read: nothing is blocked, reconnected, restarted or reconfigured, and the firewall, VLANs and WiFi are never touched.

- **UniFi clients** lists who's connected: name, mac, ip, type (wired, wireless or vpn), connected (since when) and uplink (the UniFi device it comes through).
- **UniFi devices** lists your gateway, switches and access points: name, model, mac, ip, state, firmware, update (whether newer firmware is waiting), and for one that's online, uptime (hours), cpu and memory (%).

On the page they use a **sample network**, with an unnamed newcomer on the IoT network and an access point offline. The gallery program **Who's on the network?** reports what's new each morning.

**Using your own network.** In the Network app, open Settings, Control Plane, Integrations and create an API key. Then:

```
[unifi]
UNIFI_URL = https://192.168.1.1
UNIFI_API_KEY = …
UNIFI_CERT_SHA256 =
```

As with MikroTik, the console's certificate is its own: run `--doctor` once and it shows the fingerprint to pin. `UNIFI_SITE` picks a site other than the first. The key itself could do more than read (restart a device, block a client), but Second Thought only ever sends the reads in `unifi_free`; keep the key for this program alone.
