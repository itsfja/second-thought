      case "rb_plex_server": return plexServer();
      case "rb_plex_libraries": return plexLibraries();
      case "rb_plex_sessions": return plexSessions();
      case "rb_plex_recent": return plexRecent(await input(b, tc, "N"));
      case "rb_tautulli_history": return tautulliHistory(await input(b, tc, "N"));
      case "rb_tautulli_watchtime": return tautulliWatchtime(await input(b, tc, "N"));
