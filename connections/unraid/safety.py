    # Unraid's own GraphQL API (#399), all of it one POST to /graphql, so the gate reads the query text: a query is a
    # read, and only these mutations are ever sent, after a live yes: starting or stopping one container or VM by
    # name, and a parity read-check. Anything else (stopping the array, adding or removing disks, updating
    # containers, plugins, terminal commands) is never sent.
    "unraid_free": [["POST", r"^(?![\s\S]*mutation)\s*(query|\{)"]],
    "unraid_asks": [["POST", r'^mutation\{docker\{(start|stop)\(id:"container:[^"]+"\)\{id\}\}\}$'],
                    ["POST", r'^mutation\{vm\{(start|stop)\(id:"vm:[^"]+"\)\}\}$'],
                    ["POST", r"^mutation\{parity\{start\(correct:false\)\}\}$"]],
