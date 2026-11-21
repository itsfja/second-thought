def proxmox_call(method, path):
    """"free" for a Proxmox call the runtime makes without asking, "asks" for a power action that needs a live yes,
    and None for anything else, which is never sent (#357)."""
    method, path = to_str(method).strip().upper(), to_str(path).strip()
    for kind in ("free", "asks"):
        if any(m == method and re.match(p, path) for m, p in SAFETY["proxmox_" + kind]):
            return kind
    return None
