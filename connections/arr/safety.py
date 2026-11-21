    # Radarr and Sonarr's Servarr API (#398): the reads the runtime makes, and the one command it may send after a yes.
    # The command's name is in the body, checked separately against ARR_SEARCH; nothing else is ever sent: no adding or
    # deleting, no editing profiles or root folders, nothing in the indexer or download-client settings, no refresh.
    "arr_free": [["GET", r"^/api/v3/(queue|wanted/missing|diskspace|system/status)$"]],
    "arr_asks": [["POST", r"^/api/v3/command$"]],
    # Plex's HTTP API (the X-Plex-Token endpoints the apps use) and Tautulli's API (#402). The server, the libraries, the
    # sessions and the newest items are reads; scanning a library always asks, live. Tautulli's gate reads the query as
    # a whole, like NZBGeek's: the history is a read, and the one terminate (a stream stopped) always asks. Nothing else
    # is ever sent: no media or library is ever deleted, no sharing, no user access, no transcoding or remote-access
    # settings.
    "plex_free": [["GET", r"^/$"], ["GET", r"^/library/sections$"], ["GET", r"^/library/sections/[0-9]+/all$"],
                  ["GET", r"^/library/recentlyAdded$"], ["GET", r"^/status/sessions$"]],
    "plex_asks": [["GET", r"^/library/sections/[0-9]+/refresh$"]],
    "tautulli_free": [["GET", r"^(?!.*(^|&)cmd=terminate_session(&|$))cmd=get_history(&|$)"]],
    "tautulli_asks": [["GET", r"^(?!.*(^|&)cmd=get_history(&|$))cmd=terminate_session&.*session_key=[^&]+(&|$)"]],
