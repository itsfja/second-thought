    /* MikroTik (#360): read only */
    V("rb_mikrotik_ports", "MikroTik ports", [], "Array", { style:"mikrotik",
      tooltip:"A list of records, one for each port on your MikroTik router or switch: port, running, speed (like 10Gbps), errors, drops, link_downs and comment. Errors and drops count from when it last started. It only reads: nothing on the switch changes. On this page it uses a sample switch." }),
    V("rb_mikrotik_sfp", "MikroTik SFP modules", [], "Array", { style:"mikrotik",
      tooltip:"A list of records, one for each SFP module plugged in: port, module, temperature (°C), rx_power and tx_power (dBm)." }),
    V("rb_mikrotik_health", "MikroTik health", [], null, { style:"mikrotik",
      tooltip:"A record about the router or switch itself: board, version, uptime, cpu_load (%), free_memory (MB), temperature (°C), and any other sensors it has." }),
    V("rb_mikrotik_log", "MikroTik log, last %1 lines", [val("N")], "Array", { style:"mikrotik", inputsInline:true,
      tooltip:"The last lines of the router's log, oldest first, each as \"time topics: message\"." }),
