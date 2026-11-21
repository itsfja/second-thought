        case "rb_proxmox_nodes": return "(await R.proxmox_nodes())";
        case "rb_proxmox_guests": return "(await R.proxmox_guests())";
        case "rb_proxmox_storage": return "(await R.proxmox_storage())";
        case "rb_proxmox_tasks": return "(await R.proxmox_tasks(" + I("N", "24") + "))";
