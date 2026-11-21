      case "rb_plex_scan": await plexAsking("scan the " + (await input(b, tc, "LIBRARY")) + " library on Plex"); break;
      case "rb_plex_stop": await plexAsking("stop the " + (await input(b, tc, "ID")) + " stream on Plex"); break;
