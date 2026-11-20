        case "rb_pihole_summary": return "(await R.pihole_summary())";
        case "rb_pihole_top_domains": return "(await R.pihole_top_domains(" + I("N", "5") + "))";
        case "rb_pihole_top_clients": return "(await R.pihole_top_clients(" + I("N", "5") + "))";
