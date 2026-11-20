def sabnzbd_call(method, mode):
    """"free" for a SABnzbd call the runtime makes without asking, "asks" for pause and resume, which need a live yes,
    and None for anything else, which is never sent (#397)."""
    method, mode = to_str(method).strip().upper(), to_str(mode).strip()
    for kind in ("free", "asks"):
        if any(m == method and re.match(p, mode) for m, p in SAFETY["sabnzbd_" + kind]):
            return kind
    return None
