def unraid_call(method, query):
    """"free" for a Unraid GraphQL query the runtime makes without asking (a query is a read), "asks" for the few
    mutations that need a live yes (starting or stopping one container or VM, a parity read-check), and None for
    anything else, which is never sent (#399)."""
    method, query = to_str(method).strip().upper(), to_str(query).strip()
    for kind in ("free", "asks"):
        if any(m == method and re.match(p, query) for m, p in SAFETY["unraid_" + kind]):
            return kind
    return None
