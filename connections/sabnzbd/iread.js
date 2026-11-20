      case "rb_sabnzbd_queue": return sabnzbdQueue();
      case "rb_sabnzbd_history": return sabnzbdHistory(await input(b, tc, "N", 24));
      case "rb_sabnzbd_diskspace": return sabnzbdDiskspace();
