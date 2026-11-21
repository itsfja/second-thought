      case "rb_proxmox_nodes": return proxmoxNodes();
      case "rb_proxmox_guests": return proxmoxGuests();
      case "rb_proxmox_storage": return proxmoxStorage();
      case "rb_proxmox_tasks": return proxmoxTasks(await input(b, tc, "N", 24));
