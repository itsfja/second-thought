def plex_call(method, path):
    """"free" for one of the Plex calls the runtime makes without asking (the server, the libraries, the sessions and
    the newest items), "asks" for the one change that needs a live yes (scanning a library), and None for anything
    else, which is never sent (#402)."""
    method, path = to_str(method).strip().upper(), to_str(path).strip()
    for kind in ("free", "asks"):
        if any(m == method and re.match(p, path) for m, p in SAFETY["plex_" + kind]):
            return kind
    return None


def tautulli_call(method, query):
    """"free" for Tautulli's history read, "asks" for the one terminate (a stream stopped), and None for anything
    else, which is never sent (#402). The query is read as a whole, like NZBGeek's, so a history that smuggles a
    terminate is refused."""
    method, query = to_str(method).strip().upper(), to_str(query).strip()
    for kind in ("free", "asks"):
        if any(m == method and re.match(p, query) for m, p in SAFETY["tautulli_" + kind]):
            return kind
    return None
