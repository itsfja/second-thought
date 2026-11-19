    # Tesla's Powerwall gateway (#362): the reads the runtime makes, and the one thing it may change after a yes. Nothing
    # else is ever sent: no firmware, no storm watch, no operation mode, no grid charging or export setting.
    "powerwall_free": [["GET", r"^/api/(meters/aggregates|system_status/soe|system_status/grid_status|operation)$"]],
    "powerwall_asks": [["POST", r"^/api/operation$"]],
