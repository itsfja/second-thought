      case "rb_mikrotik_ports": return mikrotikPorts();
      case "rb_mikrotik_sfp": return mikrotikSfp();
      case "rb_mikrotik_health": return mikrotikHealth();
      case "rb_mikrotik_log": return mikrotikLog(await input(b, tc, "N", 20));
