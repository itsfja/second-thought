    # Pi-hole's REST API, v6 and later (#401): the reads the runtime makes, signing in first, and the few changes it
    # may make after a live yes. Nothing else is ever sent: no upstream DNS, no DHCP, no web password, no network
    # settings.
    "pihole_free": [["GET", r"^/api/(stats/summary|stats/top_domains|stats/top_clients|dns/blocking)$"],
                    ["POST", r"^/api/auth$"]],
    "pihole_asks": [["POST", r"^/api/dns/blocking$"],
                    ["POST", r"^/api/domains/(allowlist|denylist)/exact$"],
                    ["DELETE", r"^/api/domains/(allowlist|denylist)/exact$"]],
