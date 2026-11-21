        case "rb_docker_containers": return "(await R.docker_containers())";
        case "rb_docker_stats": return "(await R.docker_stats())";
        case "rb_docker_logs": return "(await R.docker_logs(" + I("NAME", '""') + ", " + I("N", "50") + "))";
