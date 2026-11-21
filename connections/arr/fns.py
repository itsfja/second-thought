ARR_SEARCH = {"radarr": "MissingMovieSearch", "sonarr": "MissingEpisodeSearch"}
def arr_call(method, path):
    """"free" for a Radarr or Sonarr call the runtime makes without asking, "asks" for the one search command, which
    needs a live yes, and None for anything else, which is never sent (#398)."""
    method, path = to_str(method).strip().upper(), to_str(path).strip()
    for kind in ("free", "asks"):
        if any(m == method and re.match(p, path) for m, p in SAFETY["arr_" + kind]):
            return kind
    return None
