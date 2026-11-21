    # Docker (#358)
    # Docker's Engine API: DOCKER_HOST is unix:///var/run/docker.sock (the default, except on Windows) or
    # tcp://host:2375. The socket is root on that machine, so point DOCKER_HOST at a socket proxy (such as
    # tecnativa/docker-socket-proxy, allowing CONTAINERS and POST) where you can. With DOCKER_TLS_VERIFY = 1 it uses
    # TLS, with ca.pem (and cert.pem and key.pem, if there) from DOCKER_CERT_PATH, as the docker command does. Reads
    # are the calls in SAFETY["docker_free"]; restart, stop and start (docker_asks) always ask, live, and never run
    # with nobody there; nothing else is ever sent. DOCKER_PROTECT lists containers never restarted, stopped or started.
    DOCKER_POWER = ("restart", "stop", "start")

    async def _docker(self, method, path, query=None, approved=False, raw=False):
        kind = docker_call(method, path)
        if kind is None or (kind == "asks" and not approved):
            raise RunError(tr("Second Thought doesn't send {what} to Docker.", what=f"{method} {path}"))
        host = os.environ.get("DOCKER_HOST", "").strip() or ("" if os.name == "nt" else "unix:///var/run/docker.sock")
        if not host or host.startswith("npipe:"):
            raise RunError(tr("On Windows, set DOCKER_HOST to a tcp:// address: Docker's named pipe isn't supported."))
        u = urllib.parse.urlparse(host if "://" in host else "tcp://" + host)
        full = path + ("?" + urllib.parse.urlencode(query) if query else "")

        def go():
            if u.scheme == "unix":
                import socket

                class Unix(http.client.HTTPConnection):
                    def connect(self):
                        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                        self.sock.settimeout(self.timeout)
                        self.sock.connect(u.path)
                conn = Unix("localhost", timeout=30)
            elif os.environ.get("DOCKER_TLS_VERIFY", "").strip() not in ("", "0") or u.scheme == "https":
                import ssl
                certs = os.path.expanduser(os.environ.get("DOCKER_CERT_PATH", "").strip() or "~/.docker")
                ca = os.path.join(certs, "ca.pem")
                ctx = ssl.create_default_context(cafile=ca if os.path.isfile(ca) else None)
                if os.path.isfile(os.path.join(certs, "cert.pem")):
                    ctx.load_cert_chain(os.path.join(certs, "cert.pem"), os.path.join(certs, "key.pem"))
                conn = http.client.HTTPSConnection(u.hostname, u.port or 2376, timeout=30, context=ctx)
            else:
                conn = http.client.HTTPConnection(u.hostname, u.port or 2375, timeout=30)
            try:
                conn.request(method, full, headers={"Accept": "application/json", "Host": "docker"})
                r = conn.getresponse()
                return r.status, r.read()
            except Exception as e:  # noqa: BLE001 - no socket, refused, a certificate: say which
                raise RunError(tr("Couldn't reach the {who} at {url} ({reason}).", who="Docker engine", url=host, reason=_short(str(e), 120))) from None
            finally:
                conn.close()
        status, body = await asyncio.to_thread(go)
        if status == 404:
            raise RunError(tr("Docker: {why}.", why=tr("not found")))
        if status >= 400 and status != 304:
            raise RunError(tr("Docker: {why}.", why=self._said(status, body)))
        if raw:
            return body
        return json.loads(body) if body.strip() else {}

    @staticmethod
    def _docker_name(name):
        n = to_str(name).strip().lstrip("/")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", n):
            raise RunError(tr("Which Docker container? Give its name, like sonarr."))
        return n

    async def docker_containers(self):
        """Every container, running or not: name, image, state (running, exited, restarting, ...), status (as docker ps
        says it), health (healthy, unhealthy, starting, or "" with no health check), restarts and started."""
        async def one(c):
            name = to_str((c.get("Names") or [""])[0]).lstrip("/")
            info = await self._docker("GET", f"/containers/{self._docker_name(name)}/json")
            st = info.get("State") or {}
            return {"name": name, "image": to_str(c.get("Image")), "state": to_str(c.get("State")), "status": to_str(c.get("Status")),
                    "health": to_str((st.get("Health") or {}).get("Status")), "restarts": int(num(info.get("RestartCount") or 0)),
                    "started": to_str(st.get("StartedAt"))[:16].replace("T", " ")}
        out = list(await asyncio.gather(*(one(c) for c in await self._docker("GET", "/containers/json", {"all": "1"}) if isinstance(c, dict))))
        out.sort(key=lambda c: c["name"])
        lines = "\n".join(f"{c['name']}: {c['status']}" for c in out)
        self.log(tr("Docker containers"), lines or tr("(nothing)"), tr("{n} containers", n=len(out)))
        return out

    async def docker_stats(self):
        """Each running container's use right now: name, cpu (%), memory_mb, limit_mb (the machine's memory, for a
        container with no limit) and memory (% of the limit)."""
        async def one(c):
            name = to_str((c.get("Names") or [""])[0]).lstrip("/")
            s = await self._docker("GET", f"/containers/{self._docker_name(name)}/stats", {"stream": "false"})
            cpu, pre, mem = s.get("cpu_stats") or {}, s.get("precpu_stats") or {}, s.get("memory_stats") or {}
            d_cpu = num((cpu.get("cpu_usage") or {}).get("total_usage") or 0) - num((pre.get("cpu_usage") or {}).get("total_usage") or 0)
            d_sys = num(cpu.get("system_cpu_usage") or 0) - num(pre.get("system_cpu_usage") or 0)
            used = num(mem.get("usage") or 0) - num((mem.get("stats") or {}).get("inactive_file") or 0)
            limit = num(mem.get("limit") or 0)
            return {"name": name, "cpu": self._cents(d_cpu / d_sys * num(cpu.get("online_cpus") or 1) * 100) if d_sys > 0 and d_cpu > 0 else 0,
                    "memory_mb": self._cents(used / 1048576), "limit_mb": self._cents(limit / 1048576), "memory": self._pct(used, limit) if limit else ""}
        out = list(await asyncio.gather(*(one(c) for c in await self._docker("GET", "/containers/json") if isinstance(c, dict))))
        return sorted(out, key=lambda c: c["name"])

    async def docker_logs(self, name, count=50):
        """The last lines a container wrote (its output and its errors together), oldest first."""
        n = max(1, min(1000, int(num(count) or 50)))
        body = await self._docker("GET", f"/containers/{self._docker_name(name)}/logs", {"stdout": "1", "stderr": "1", "tail": str(n)}, raw=True)
        chunks, i = [], 0
        while len(body) - i >= 8 and body[i] in (0, 1, 2) and body[i + 1:i + 4] == b"\0\0\0":  # framed: kind, three zeros, length
            size = int.from_bytes(body[i + 4:i + 8], "big")
            chunks.append(body[i + 8:i + 8 + size])
            i += 8 + size
        text = (b"".join(chunks) if chunks and i >= len(body) else body).decode("utf-8", "replace")
        return [line.rstrip("\r") for line in text.split("\n") if line.strip()][-n:]

    async def docker_power(self, action, name):
        """Restarts, stops or starts one container, by name, after asking you, every time. Never one in
        DOCKER_PROTECT. Gives back True if it was done."""
        action = to_str(action).strip().lower()
        if action not in self.DOCKER_POWER:
            raise RunError(tr("A Docker container can be restarted, stopped or started."))
        name = self._docker_name(name)
        if name.lower() in {x.strip().lstrip("/").lower() for x in os.environ.get("DOCKER_PROTECT", "").split(",") if x.strip()}:
            self.log(tr("Not done"), tr("Container {name} is in DOCKER_PROTECT, so Second Thought never restarts, stops or starts it.", name=name), tr("refused"))
            return False
        info = await self._docker("GET", f"/containers/{name}/json")
        what = f"{action} the Docker container {name} ({to_str((info.get('Config') or {}).get('Image'))}, now {to_str((info.get('State') or {}).get('Status'))})"
        if self._skip_action(what):
            return False
        if not await self.confirm_live(what):
            return False
        await self._docker("POST", f"/containers/{name}/{action}", approved=True)
        self.log(tr("Docker"), what, tr("done"))
        return True
