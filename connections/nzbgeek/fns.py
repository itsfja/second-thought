def nzbgeek_call(method, query):
    """"free" for one of NZBGeek's Newznab reads (a search, or t=caps), "asks" for the one fetch (t=get, an NZB
    file, with a paid account's key), and None for anything else, which is never sent (#400). The query is read as
    a whole: a search that smuggles t=get is refused, and so is a fetch that smuggles a search."""
    method, query = to_str(method).strip().upper(), to_str(query).strip()
    for kind in ("free", "asks"):
        if any(m == method and re.match(p, query) for m, p in SAFETY["nzbgeek_" + kind]):
            return kind
    return None
