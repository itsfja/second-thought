        case "rb_pihole_blocking": E("await R.pihole_blocking(" + I("N", "60") + ")"); break;
        case "rb_pihole_enable": E("await R.pihole_enable()"); break;
        case "rb_pihole_allow": E("await R.pihole_list(\"allow\", " + pyStr(b.getFieldValue("ACTION")) + ", " + I("DOMAIN", "\"ads.example.com\"") + ")"); break;
        case "rb_pihole_deny": E("await R.pihole_list(\"deny\", " + pyStr(b.getFieldValue("ACTION")) + ", " + I("DOMAIN", "\"bad.example.com\"") + ")"); break;
