      case "rb_pihole_blocking": await piholeAsking("disable Pi-hole's blocking for " + (await input(b, tc, "N")) + " seconds"); break;
      case "rb_pihole_enable": await piholeAsking("enable Pi-hole's blocking"); break;
      case "rb_pihole_allow": await piholeAsking(b.getFieldValue("ACTION") + " " + (await input(b, tc, "DOMAIN")) + " on Pi-hole's allow list"); break;
      case "rb_pihole_deny": await piholeAsking(b.getFieldValue("ACTION") + " " + (await input(b, tc, "DOMAIN")) + " on Pi-hole's deny list"); break;
