        case "rb_plex_server": return "(await R.plex_server())";
        case "rb_plex_libraries": return "(await R.plex_libraries())";
        case "rb_plex_sessions": return "(await R.plex_sessions())";
        case "rb_plex_recent": return "(await R.plex_recent(" + I("N", "7") + "))";
        case "rb_tautulli_history": return "(await R.tautulli_history(" + I("N", "7") + "))";
        case "rb_tautulli_watchtime": return "(await R.tautulli_watchtime(" + I("N", "7") + "))";
