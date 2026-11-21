    if (need.docker) out.push("", "[docker]",
      "; Docker's Engine API. Left out, it's the socket on this computer (unix:///var/run/docker.sock), which is root on",
      "; the machine: safer is a socket proxy (tecnativa/docker-socket-proxy with CONTAINERS=1, plus ALLOW_RESTARTS=1 and",
      "; ALLOW_START=1 only if the program restarts, stops or starts containers), and DOCKER_HOST = tcp://that-machine:2375.",
      "; DOCKER_PROTECT lists containers never restarted, stopped or started, like the proxy itself.",
      "; DOCKER_HOST = tcp://docker.local:2375", "DOCKER_PROTECT = ");
