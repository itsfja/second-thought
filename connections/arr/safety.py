    # Radarr and Sonarr's Servarr API (#398): the reads the runtime makes, and the one command it may send after a yes.
    # The command's name is in the body, checked separately against ARR_SEARCH; nothing else is ever sent: no adding or
    # deleting, no editing profiles or root folders, nothing in the indexer or download-client settings, no refresh.
    "arr_free": [["GET", r"^/api/v3/(queue|wanted/missing|diskspace|system/status)$"]],
    "arr_asks": [["POST", r"^/api/v3/command$"]],
