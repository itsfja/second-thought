    # UniFi's Network API (#359), the Integration API on a UniFi OS console: the only calls made. Reading clients and
    # devices; nothing that blocks, reconnects or restarts, and nothing near the firewall, VLANs or WiFi.
    "unifi_free": [["GET", r"^/proxy/network/integration/v1/(info|sites|sites/[A-Za-z0-9-]+/(clients|devices|devices/[A-Za-z0-9-]+/statistics/latest))$"]],
