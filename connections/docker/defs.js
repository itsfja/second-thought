    /* Docker (#358): reads, and restart, stop and start that always ask */
    V("rb_docker_containers", "Docker containers", [], "Array", { style:"docker",
      tooltip:"A list of records, one for each container, running or not: name, image, state, status, health (healthy, unhealthy, or empty with no health check), restarts and started. On this page it uses a sample stack." }),
    V("rb_docker_stats", "Docker memory and CPU", [], "Array", { style:"docker",
      tooltip:"A list of records, one for each running container: name, cpu (%), memory_mb, limit_mb (the machine's memory, for a container with no limit) and memory (% of the limit)." }),
    V("rb_docker_logs", "Docker logs of %1, last %2 lines", [val("NAME"), val("N")], "Array", { style:"docker", inputsInline:true,
      tooltip:"The last lines a container wrote, its output and its errors together, oldest first." }),
    S("rb_docker_power", "%1 Docker container %2", [{ type:"field_dropdown", name:"ACTION", options:[["restart","restart"],["stop","stop"],["start","start"]] }, val("NAME")],
      { style:"docker", inputsInline:true, tooltip:"Restarts, stops or starts one container, by its name. It always asks you first, even when nothing else asks, and with nobody there to say yes it doesn't run. Containers listed in DOCKER_PROTECT are never touched. On this page nothing really restarts." }),
