def powerwall_allowed(method, path, approved=False):
    """True for one of the few Tesla gateway calls the runtime makes (#362): the reads in powerwall_free, and the
    backup reserve change in powerwall_asks, only after the person's yes."""
    method, path = to_str(method).strip().upper(), to_str(path).strip()
    return any(m == method and re.match(p, path) for m, p in SAFETY["powerwall_free"]) \
        or (approved and any(m == method and re.match(p, path) for m, p in SAFETY["powerwall_asks"]))
