    /* UniFi (#359): read only */
    V("rb_unifi_clients", "UniFi clients", [], "Array", { style:"unifi",
      tooltip:"A list of records, one for each device connected to your UniFi network: name, mac, ip, type (wired, wireless or vpn), connected (since when) and uplink (the UniFi device it's connected through). It only reads: nothing is blocked or changed. On this page it uses a sample network." }),
    V("rb_unifi_devices", "UniFi devices", [], "Array", { style:"unifi",
      tooltip:"A list of records, one for each UniFi device (gateway, switches, access points): name, model, mac, ip, state, firmware, update (whether newer firmware is waiting), and for one that's online, uptime (hours), cpu and memory (%)." }),
