      case "rb_docker_containers": return dockerContainers();
      case "rb_docker_stats": return dockerStats();
      case "rb_docker_logs": return dockerLogs(await input(b, tc, "NAME"), await input(b, tc, "N", 50));
