    async def _listen_webhook(self, items):
        import hmac
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        secret = os.environ.get("WEBHOOK_SECRET", "").strip()
        port = int(os.environ.get("WEBHOOK_PORT") or 8765)
        paths = {}
        for path, fn in items:
            paths.setdefault(to_str(path).strip().strip("/").lower(), []).append(fn)
        loop, rt = asyncio.get_running_loop(), self

        class Hook(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _answer(self, code, text):
                body = json.dumps({"ok": code == 200, "message": text}).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                self._handle("GET")

            def do_POST(self):
                self._handle("POST")

            def _handle(self, method):
                u = urllib.parse.urlparse(self.path)
                q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
                key = self.headers.get("X-Second-Thought-Key") or q.pop("key", "")
                if not secret or not hmac.compare_digest(key.encode(), secret.encode()):
                    return self._answer(403, "Wrong or missing key.")
                fns = paths.get(u.path.strip("/").lower())
                if not fns:
                    return self._answer(404, "No script listens at this address.")
                n = int(self.headers.get("Content-Length") or 0)
                if n > 1_000_000:
                    return self._answer(413, "That's too big.")
                body = self.rfile.read(n).decode("utf-8", "replace") if n else ""
                rec = {"path": u.path.strip("/"), "method": method, "text": body or ", ".join(f"{k}={v}" for k, v in q.items())}
                for k, v in q.items():
                    rec.setdefault(k, v)
                try:
                    j = json.loads(body) if body else None
                except ValueError:
                    j = None
                if isinstance(j, dict):
                    for k, v in j.items():
                        rec.setdefault(str(k), json.dumps(v) if isinstance(v, (dict, list)) else v)
                for fn in fns:
                    loop.call_soon_threadsafe(rt._fire, fn, dict(rec), "Web request /" + rec["path"])
                self._answer(200, "Started.")
        if not secret:  # no password, no open port: nothing on the network can even try
            # Said again every hour, so someone who opens the window later (or reads the log) still sees why.
            note = f"set WEBHOOK_SECRET {WHERE_KEYS} to a long password. Until then, the program doesn't listen for them."
            print(tr("Web requests: {note}", note=note), flush=True)
            while True:
                await asyncio.sleep(self._poll(3600))
                print(tr("Web requests, {x}: still not listening. To turn them on, {note}", x=format(datetime.datetime.now(), '%H:%M'), note=note), flush=True)
        host = webhook_host()
        srv = ThreadingHTTPServer((host, port), Hook)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        # On 127.0.0.1 the addresses say so, so it's plain that only this computer can call them (WEBHOOK_HOST opens them up).
        where = host if host in ("127.0.0.1", "localhost", "::1") else "<this computer>"
        print(tr("Listening for web requests on port {port}: {x}.", port=port, x=", ".join(f"http://{where}:{port}/{p_}?key=…" for p_ in paths)), flush=True)
        while True:
            await asyncio.sleep(3600)

    @staticmethod
    def page_part(text, words):
        """The lines that contain all these words, each with the lines after it; the whole text when words is empty."""
        words = [w for w in to_str(words).lower().split() if w]
        if not words:
            return text
        lines, keep = text.splitlines(), set()
        for i, line in enumerate(lines):
            if all(w in line.lower() for w in words):
                keep.update(range(i, min(len(lines), i + 1 + Connections.PAGE_LINES_AFTER)))
        return "\n".join(lines[i] for i in sorted(keep))

    @staticmethod
    def page_changes(before, after, limit=20):
        """What changed, line by line: '- old line' then '+ new line', paired where lines were replaced, at most limit lines."""
        import difflib
        a, c, out = before.splitlines(), after.splitlines(), []
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, c, autojunk=False).get_opcodes():
            if op == "equal":
                continue
            gone, new = a[i1:i2], c[j1:j2]
            for k in range(max(len(gone), len(new))):
                out += ["- " + _short(gone[k], 200)] if k < len(gone) and gone[k].strip() else []
                out += ["+ " + _short(new[k], 200)] if k < len(new) and new[k].strip() else []
        return "\n".join(out[:limit]) + (f"\n… and {len(out) - limit} more changed lines" if len(out) > limit else "")

    async def _read_page_text(self, url):
        ctype, data = await asyncio.to_thread(get_url, url, True, "The page watcher", 5_000_000)
        if not re.search(r"text/|html|xml|json", ctype, re.I) and data[:1] != b"<":
            raise RunError(tr("{url} isn't a web page or text ({x}).", url=_short(url, 80), x=ctype.split(';')[0] or tr('unknown type')))
        return page_text(_decode(data, ctype), ctype)

    async def _listen_page(self, items):
        await asyncio.gather(*(self._watch_page(arg, fn) for arg, fn in items))

    async def _watch_page(self, arg, fn):
        """'when the web page … changes': checks the page every N minutes. The first check only remembers it."""
        url, words, minutes = (to_str(arg).split("|") + ["", "", ""])[:3]
        url, words = url.strip(), words.strip()
        every = max(1, round_js(num(minutes)) or 60) * 60
        key = url + ("  |  " + words.lower() if words else "")
        quiet_noted = False
        print((tr("Watching {url} (the part with “{words}”) for changes, every {n} min.", url=url, words=words, n=every // 60) if words else
                   tr("Watching {url} for changes, every {n} min.", url=url, n=every // 60)), flush=True)
        while True:
            try:
                title, text = await self._read_page_text(url)
                now = self.page_part(text, words).strip()[:self.MAX_PAGE_KEEP]
                if not text.strip() or (words and not now):
                    if not quiet_noted:
                        quiet_noted = True
                        print("  " + (tr("(Page watcher: {url} has no readable words; it may need a browser to show them. It's checked again each time.)", url=_short(url, 80))
                                     if not text.strip() else tr("(Page watcher: {url} has nothing with “{words}” in it right now. It's checked again each time.)",
                                                                 url=_short(url, 80), words=words)), flush=True)
                else:
                    quiet_noted = False
                    with _locked(PAGES_FILE):
                        try:
                            with open(PAGES_FILE, encoding="utf-8") as f:
                                seen = json.load(f)
                        except (OSError, ValueError):
                            seen = {}
                        before = (seen.get(key) or {}).get("text")
                        if before != now:
                            seen[key] = {"text": now, "checked": int(time.time())}
                            _write_json(PAGES_FILE, seen)
                    if before is not None and before != now:
                        changed = self.page_changes(before, now)
                        cut = lambda t: t if len(t) <= 2000 else t[:1999] + "…"  # noqa: E731 - keeps the lines, unlike _short
                        rec = {"url": url, "title": title, "before": cut(before), "after": cut(now), "changed": changed,
                               "text": f"{title or url} changed:\n{changed}"}
                        self._fire(fn, rec, tr("Page changed: {page}", page=_short(title or url, 40)))
            except RunError as e:
                print(tr("  (Page check failed: {e})", e=e), flush=True)
            await asyncio.sleep(self._poll(every))
