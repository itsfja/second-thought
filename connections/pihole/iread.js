      case "rb_pihole_summary": return piholeSummary();
      case "rb_pihole_top_domains": return piholeTopDomains(await input(b, tc, "N"));
      case "rb_pihole_top_clients": return piholeTopClients(await input(b, tc, "N"));
