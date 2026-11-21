    # Proxmox VE's REST API (#357): the reads the runtime makes, and the power actions it may make after a yes. Nothing
    # else is ever sent: no destroying, no snapshots rolled back, no commands run in a guest, no storage, permissions or
    # firewall changes. A power action always asks, live, and never runs with nobody there; PROXMOX_PROTECT lists
    # guests it never touches at all.
    "proxmox_free": [["GET", r"^/api2/json/(version|nodes|cluster/resources|cluster/tasks|access/permissions|nodes/[A-Za-z0-9.-]+/(qemu|lxc)/\d+/config)$"]],
    "proxmox_asks": [["POST", r"^/api2/json/nodes/[A-Za-z0-9.-]+/(qemu|lxc)/\d+/status/(start|shutdown|reboot)$"]],
