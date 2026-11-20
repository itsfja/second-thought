def mikrotik_allowed(method, path):
    """True for one of the few RouterOS REST calls the runtime makes (#360): reading, never changing."""
    method, path = to_str(method).strip().upper(), to_str(path).strip()
    return any(m == method and re.match(p, path) for m, p in SAFETY["mikrotik_free"])
