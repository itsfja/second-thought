    # Docker's Engine API (#358): the reads the runtime makes, and what it may do to a container after a yes. Nothing
    # else is ever sent: no exec, run, rm, pull or build (each can run anything on the machine as root), and nothing
    # to do with images, volumes or networks. Restart, stop and start always ask, live, and never run with nobody there.
    "docker_free": [["GET", r"^/(version|containers/json|containers/[A-Za-z0-9][A-Za-z0-9_.-]*/(json|stats|logs))$"]],
    "docker_asks": [["POST", r"^/containers/[A-Za-z0-9][A-Za-z0-9_.-]*/(restart|stop|start)$"]],
