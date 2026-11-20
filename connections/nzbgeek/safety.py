    # NZBGeek's Newznab API (#400): one GET to /api, so the gate reads the query. The searches and t=caps are reads;
    # the one fetch (t=get, an NZB file, with a paid account's key) always asks, live. Nothing else is ever sent:
    # no account changes, no VIP time, no payments, and a search that smuggles t=get is refused.
    "nzbgeek_free": [["GET", r"^(?!.*(^|&)t=get(&|$))t=(search|tvsearch|movie|caps)(&|$)"]],
    "nzbgeek_asks": [["GET", r"^(?!.*(^|&)t=(search|tvsearch|movie|caps)(&|$))t=get&id=[^&]+$"]],
