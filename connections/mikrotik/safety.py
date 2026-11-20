    # MikroTik's RouterOS REST API (#360): the only calls made, [method, path]. Reading, and the monitor command, which
    # only reads but is a POST. Nothing else is ever sent: no changes, no reboot. A switch that loses its config takes
    # the network with it, and nothing here is worth that.
    "mikrotik_free": [["GET", r"^/rest/(interface|system/resource|system/health|log|user|user/group)$"],
                      ["POST", r"^/rest/interface/ethernet/monitor$"]],
