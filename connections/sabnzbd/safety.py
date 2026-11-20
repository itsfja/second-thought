    # SABnzbd's API (#397): one endpoint whose mode says what's asked for, so the gate matches the mode. The reads the
    # runtime makes, and pause and resume, which need a live yes. Nothing else is ever sent: no adding or deleting jobs,
    # no retry, no speedlimit, no config, no shutdown, and nothing that touches servers or categories.
    "sabnzbd_free": [["GET", r"^(queue|history|diskspace)$"]],
    "sabnzbd_asks": [["GET", r"^(pause|resume)$"]],
