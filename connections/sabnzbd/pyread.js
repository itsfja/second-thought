        case "rb_sabnzbd_queue": return "(await R.sabnzbd_queue())";
        case "rb_sabnzbd_history": return "(await R.sabnzbd_history(" + I("N", "24") + "))";
        case "rb_sabnzbd_diskspace": return "(await R.sabnzbd_diskspace())";
