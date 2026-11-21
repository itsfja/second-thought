## Docker

The blue **Docker** blocks read your containers through Docker's Engine API, and can restart, stop and start them, always asking first:

- **Docker containers**: each container, running or not, with name, image, state, status, health (healthy, unhealthy, or empty with no health check), restarts and started.
- **Docker memory and CPU**: each running container's cpu (%), memory_mb, limit_mb and memory (% of the limit). A container with no limit of its own has the machine's memory as its limit.
- **Docker logs of … last … lines**: the last lines a container wrote, its output and its errors together.
- **restart / stop / start Docker container …** asks you every time, even when nothing else does, with the container's name, image and state. With nobody there to say yes (a schedule, GitHub Actions), it doesn't run; `approve_by = telegram` asks on your phone instead. Containers listed in `DOCKER_PROTECT` are never touched at all.

Nothing else is ever sent: no exec, run, remove, pull or build, and nothing about images, volumes or networks. Compose isn't used at all. On the page these blocks use a **sample stack**, where one container keeps restarting, one is unhealthy and one is close to its memory limit. The gallery program **Is the stack healthy?** reports each morning and sums up the week's memory each Sunday, and only reads.

**Using your own Docker.** With no settings, the blocks use the socket on the computer the program runs on (`/var/run/docker.sock`; the program's user must be allowed to use it). They also follow `DOCKER_HOST`, `DOCKER_TLS_VERIFY` and `DOCKER_CERT_PATH`, as the `docker` command does:

```
[docker]
DOCKER_HOST = tcp://docker.local:2375
DOCKER_PROTECT = socket-proxy, homeassistant
```

**Put a socket proxy in front.** Docker's socket is root on the machine: anything that can write to it can start a container that owns the host. Second Thought sends only what's listed above, but a proxy makes Docker itself refuse the rest. [docker-socket-proxy](https://github.com/Tecnativa/docker-socket-proxy) with `CONTAINERS=1` allows reading containers, their memory and logs; the **Docker** check in `--doctor` also needs `VERSION=1`, which is on by default. If the program restarts, stops or starts containers, add `ALLOW_RESTARTS=1` (restart and stop) and `ALLOW_START=1`, and leave `POST` off: with `POST=1` the proxy would allow exec and creating containers too. Point `DOCKER_HOST` at the proxy, and keep the proxy's port off the internet: plain `tcp://` has no password. For Docker on another machine without a proxy, use TLS (`DOCKER_TLS_VERIFY = 1`, with `ca.pem`, `cert.pem` and `key.pem` in `DOCKER_CERT_PATH`). On Windows, set `DOCKER_HOST` to a `tcp://` address: Docker's named pipe isn't supported. `--doctor` says Docker's version and how many containers it sees.

Docker's own MCP Toolkit is a different thing, a gateway to MCP servers that run in containers; an agent can use it as an [MCP server](mcp.md#docker-mcp-toolkit).
