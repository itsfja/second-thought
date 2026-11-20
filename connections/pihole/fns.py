def pihole_call(method, path):
    """"free" for one of the Pi-hole calls the runtime makes without asking (the stats, the blocking status, and
    signing in), "asks" for the few changes that need a live yes (blocking on and off, a domain on the allow or
    deny list), and None for anything else, which is never sent (#401)."""
    method, path = to_str(method).strip().upper(), to_str(path).strip()
    for kind in ("free", "asks"):
        if any(m == method and re.match(p, path) for m, p in SAFETY["pihole_" + kind]):
            return kind
    return None
