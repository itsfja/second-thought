def docker_call(method, path):
    """"free" for a Docker call the runtime makes without asking, "asks" for restart, stop and start, which need a live
    yes, and None for anything else, which is never sent (#358)."""
    method, path = to_str(method).strip().upper(), to_str(path).strip()
    for kind in ("free", "asks"):
        if any(m == method and re.match(p, path) for m, p in SAFETY["docker_" + kind]):
            return kind
    return None



ARR_SEARCH = {"radarr": "MissingMovieSearch", "sonarr": "MissingEpisodeSearch"}
