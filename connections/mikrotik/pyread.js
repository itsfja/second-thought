        case "rb_mikrotik_ports": return "(await R.mikrotik_ports())";
        case "rb_mikrotik_sfp": return "(await R.mikrotik_sfp())";
        case "rb_mikrotik_health": return "(await R.mikrotik_health())";
        case "rb_mikrotik_log": return "(await R.mikrotik_log(" + I("N", "20") + "))";
