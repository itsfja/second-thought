"""Stand-ins for the services the connection blocks talk to: news feeds, GitHub's API, Telegram's Bot API and an iCal
calendar, all on one local web server, plus a tiny IMAP and SMTP mail server. They serve the same sample data the page
uses (samples/connections.json), shaped the way the real services answer."""
import datetime
import json
import pathlib
import socketserver
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
GH_TOKEN = "gh-test-token"
TG_TOKEN = "123:tg-test"
HOMEY_KEY = "homey-test-key"
TG_CHAT = 4242
DISCORD_TOKEN = "discord-test-token"
SLACK_TOKEN = "xoxb-slack-test"
DISCORD_CHANNEL, SLACK_CHANNEL = "111", "C111"   # the channels the tests allow; "999" / "C999" are someone else's
MAIL_USER, MAIL_PASS = "you@example.com", "app-password"


def _iso(hours_ago):
    return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _rss(feed):
    import email.utils
    items = "".join(f"<item><title>{i['title']}</title><link>{i['link']}</link><description><![CDATA[<p>{i['summary']}</p>]]></description>"
                    f"<pubDate>{email.utils.format_datetime(datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=i['hours_ago']))}</pubDate></item>"
                    for i in feed["items"])
    return f'<?xml version="1.0"?><rss version="2.0"><channel><title>{feed["title"]}</title>{items}</channel></rss>'


def _atom(feed):
    entries = "".join(f'<entry><title>{i["title"]}</title><link rel="alternate" href="{i["link"]}"/><updated>{_iso(i["hours_ago"])}</updated>'
                      f'<summary>{i["summary"]}</summary></entry>' for i in feed["items"])
    return f'<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>{feed["title"]}</title>{entries}</feed>'


def _ics(soon=False):
    """A calendar with the awkward cases: a weekly repeat with a skipped date, a time zone, an all-day event,
    a cancelled event and a moved occurrence."""
    now = datetime.datetime.now().replace(second=0, microsecond=0)
    today = now.replace(hour=0, minute=0)
    f = lambda d: d.strftime("%Y%m%dT%H%M%S")  # noqa: E731
    utc = lambda d: d.astimezone(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")  # noqa: E731
    weekly0 = today - datetime.timedelta(days=14) + datetime.timedelta(hours=18)
    skipped = weekly0 + datetime.timedelta(days=21)
    moved = weekly0 + datetime.timedelta(days=28)
    ev = [
        ["UID:dentist", f"DTSTART:{f(today + datetime.timedelta(hours=10))}", f"DTEND:{f(today + datetime.timedelta(hours=11))}",
         "SUMMARY:Dentist", "LOCATION:High Street\\, No. 4"],
        ["UID:call", f"DTSTART:{utc(today + datetime.timedelta(hours=15, minutes=30))}", f"DTEND:{utc(today + datetime.timedelta(hours=16))}",
         "SUMMARY:Call with the web designer"],
        ["UID:delivery", f"DTSTART;VALUE=DATE:{(today + datetime.timedelta(days=2)):%Y%m%d}", f"DTEND;VALUE=DATE:{(today + datetime.timedelta(days=3)):%Y%m%d}",
         "SUMMARY:Flour delivery"],
        ["UID:yoga", f"DTSTART:{f(weekly0)}", "DURATION:PT1H", "RRULE:FREQ=WEEKLY;COUNT=10", f"EXDATE:{f(skipped)}", "SUMMARY:Yoga"],
        ["UID:yoga", f"RECURRENCE-ID:{f(moved)}", f"DTSTART:{f(moved + datetime.timedelta(hours=1))}", f"DTEND:{f(moved + datetime.timedelta(hours=2))}",
         "SUMMARY:Yoga (later this week)"],
        ["UID:club", f"DTSTART;TZID=Europe/London:{f(today + datetime.timedelta(days=3, hours=14))}",
         f"DTEND;TZID=Europe/London:{f(today + datetime.timedelta(days=3, hours=17))}", "SUMMARY:Baking club"],
        ["UID:gone", f"DTSTART:{f(today + datetime.timedelta(hours=12))}", f"DTEND:{f(today + datetime.timedelta(hours=13))}",
         "STATUS:CANCELLED", "SUMMARY:Cancelled lunch"],
    ]
    if soon:  # for the 'event starts soon' listener: one event, ten minutes from now
        ev = [["UID:soon", f"DTSTART:{f(now + datetime.timedelta(minutes=10))}", f"DTEND:{f(now + datetime.timedelta(minutes=40))}",
               "SUMMARY:Feed the starter", "LOCATION:Kitchen"]]
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//test//EN"]
    for e in ev:
        lines += ["BEGIN:VEVENT"] + e + ["END:VEVENT"]
    lines.append("END:VCALENDAR")
    # Long lines are folded, as real calendars do.
    out = []
    for line in lines:
        while len(line) > 70:
            out.append(line[:70])
            line = " " + line[70:]
        out.append(line)
    return "\r\n".join(out) + "\r\n"


def start():
    data = json.loads((ROOT / "samples" / "connections.json").read_text(encoding="utf-8"))
    gh = data["github"]
    log = {"gh": [], "tg_sent": [], "tg_updates": [], "mail_sent": [], "homey": [], "homey_flows": [], "discord": {}, "discord_sent": [], "slack": {}, "slack_sent": [],
           "page": {"price": "£2.40", "visitors": 17}}

    def homey_change(device, cap, value):
        d = next(x for x in data["homey"]["devices"] if x["name"] == device)
        d["capabilitiesObj"][cap]["value"] = value
    log["homey_change"] = homey_change
    feeds = list(data["feeds"].values())

    def gh_pr(p):
        return {"number": p["number"], "title": p["title"], "user": {"login": p["user"]}, "state": "open", "draft": p["draft"], "merged": False,
                "body": p["body"], "head": {"ref": p["head"]}, "base": {"ref": p["base"]}, "updated_at": _iso(p["days_ago"] * 24)}

    def gh_search_item(r, pr):
        return dict({"number": r["number"], "title": r["title"], "user": {"login": r["user"]}, "state": r.get("state", "open"),
                     "updated_at": _iso(r["days_ago"] * 24), "repository_url": "https://api.github.com/repos/" + r["repo"]},
                    **({"pull_request": {}} if pr else {}))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json"):
            out = body if isinstance(body, bytes) else (body.encode() if isinstance(body, str) else json.dumps(body).encode())
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n) or b"{}") if n else {}

        def do_GET(self):
            self._route("GET")

        def do_POST(self):
            self._route("POST")

        def do_PUT(self):
            self._route("PUT")

        def _route(self, method):
            url = urlparse(self.path)
            path, q = unquote(url.path), parse_qs(url.query)
            if path == "/feeds/baking.rss":
                return self._send(200, _rss(feeds[0]), "application/rss+xml; charset=utf-8")
            if path == "/feeds/tech.atom":
                return self._send(200, _atom(feeds[1]), "application/atom+xml")
            if path == "/watch.html":  # a shop page the page-watch test changes while the program runs
                pg_ = log["page"]
                return self._send(200, f"<html><head><title>Rye flour</title></head><body><h1>Wholemeal rye flour, 1 kg</h1><p>Price</p>"
                                       f"<p>{pg_['price']}</p><p>In stock</p><p>Visitors today: {pg_['visitors']}</p></body></html>", "text/html; charset=utf-8")
            if path == "/feeds/page.html":
                return self._send(200, "<html><title>Not a feed</title></html>", "text/html")
            if path in ("/calendar.ics", "/calendar-soon.ics"):
                return self._send(200, _ics(soon=path == "/calendar-soon.ics"), "text/calendar; charset=utf-8")
            if path.startswith("/gh/"):
                return self._github(method, path[3:], q)
            if path.startswith("/homey/api/manager/"):
                return self._homey(method, path[len("/homey/api/manager"):])
            if path.startswith("/discord/"):
                if self.headers.get("Authorization") != "Bot " + DISCORD_TOKEN:
                    return self._send(401, {"message": "401: Unauthorized", "code": 0})
                return self._discord(method, path[8:], q)
            if path.startswith("/slack/"):
                if self.headers.get("Authorization") != "Bearer " + SLACK_TOKEN:
                    return self._send(200, {"ok": False, "error": "invalid_auth"})
                return self._slack(method, path[6:], q)
            if path.startswith("/tg/bot"):
                token, _, call = path[7:].partition("/")
                if token != TG_TOKEN:
                    return self._send(401, {"ok": False, "error_code": 401, "description": "Unauthorized"})
                return self._telegram(call)
            self._send(404, {"message": "Not Found"})

        def _discord(self, method, path, q):
            parts = path.strip("/").split("/")  # channels/<id>/messages
            if len(parts) != 3 or parts[0] != "channels" or parts[2] != "messages":
                return self._send(404, {"message": "Unknown route"})
            msgs = log["discord"].setdefault(parts[1], [])
            if method == "POST":
                body = self._body()
                log["discord_sent"].append((parts[1], body.get("content", "")))
                return self._send(200, discord_add(parts[1], body.get("content", ""), "SecondThought", bot=True))
            after = int((q.get("after") or ["0"])[0])
            limit = int((q.get("limit") or ["50"])[0])
            got = [m for m in msgs if int(m["id"]) > after]
            return self._send(200, list(reversed(got))[:limit] if not after else got[:limit])  # newest first, like Discord without 'after'

        def _slack(self, method, path, q):
            if path == "/chat.postMessage" and method == "POST":
                body = self._body()
                log["slack_sent"].append((body.get("channel"), body.get("text", "")))
                slack_add(body.get("channel"), body.get("text", ""), "B1", bot=True)
                return self._send(200, {"ok": True})
            if path == "/conversations.history":
                ch = (q.get("channel") or [""])[0]
                if ch not in log["slack"]:
                    return self._send(200, {"ok": False, "error": "channel_not_found"})
                oldest = float((q.get("oldest") or ["0"])[0])
                got = [m for m in log["slack"][ch] if float(m["ts"]) > oldest]
                return self._send(200, {"ok": True, "messages": list(reversed(got))[:int((q.get("limit") or ["100"])[0])]})
            return self._send(200, {"ok": False, "error": "unknown_method"})

        def _github(self, method, path, q):
            log["gh"].append(method + " " + path)
            if self.headers.get("Authorization") != "Bearer " + GH_TOKEN:
                return self._send(401, {"message": "Bad credentials"})
            parts = path.strip("/").split("/")
            if path == "/user/repos" or (parts[0] == "users" and parts[-1] == "repos"):
                return self._send(200, [{"full_name": r["full_name"], "description": r["description"], "language": r["language"],
                                         "stargazers_count": r["stars"], "open_issues_count": r["open_issues"], "pushed_at": _iso(r["days_ago"] * 24)}
                                        for r in gh["repos"]])
            if path == "/search/issues":
                words = q.get("q", [""])[0]
                if "review-requested:@me" in words:
                    rows = [gh_search_item(p, True) for p in gh["pulls"] if p["review_requested"]]
                elif "author:@me" in words:
                    rows = [gh_search_item(p, True) for p in gh["pulls"] if p["user"] == gh["login"]]
                else:
                    terms = [w.lower() for w in words.split() if ":" not in w]
                    rows = [gh_search_item(r, pr) for r, pr in [(p, True) for p in gh["pulls"]] + [(i, False) for i in gh["issues"]]
                            if all(t in r["title"].lower() for t in terms)]
                return self._send(200, {"total_count": len(rows), "items": rows})
            if parts[0] == "repos" and len(parts) >= 4:
                repo = parts[1] + "/" + parts[2]
                prs = [p for p in gh["pulls"] if p["repo"] == repo]
                if parts[3] == "pulls" and len(parts) == 4:
                    return self._send(200, [gh_pr(p) for p in prs])
                if parts[3] in ("pulls", "issues") and len(parts) >= 5:
                    p = next((x for x in prs if str(x["number"]) == parts[4]), None)
                    if not p:
                        return self._send(404, {"message": "Not Found"})
                    if len(parts) == 5:
                        return self._send(200, gh_pr(p))
                    if parts[5] == "files":
                        return self._send(200, p["files"])
                    if parts[5] == "comments":
                        if method == "POST":
                            body = self._body()
                            p["comments"].append({"user": gh["login"], "body": body.get("body", "")})
                            return self._send(201, {"id": 1, "body": body.get("body", "")})
                        return self._send(200, [{"user": {"login": c["user"]}, "body": c["body"]} for c in p["comments"]])
            self._send(404, {"message": "Not Found"})

        def _homey(self, method, path):
            log["homey"].append(method + " " + path)
            if self.headers.get("Authorization") != "Bearer " + HOMEY_KEY:
                return self._send(401, {"error": "invalid_token"})
            parts = [x for x in path.split("/") if x]
            hm = data["homey"]
            if parts == ["devices", "device"]:
                return self._send(200, {d["id"]: d for d in hm["devices"]})
            if parts == ["zones", "zone"]:
                return self._send(200, {k: {"id": k, "name": v} for k, v in hm["zones"].items()})
            if parts[:2] == ["devices", "device"] and len(parts) == 5 and parts[3] == "capability" and method == "PUT":
                d = next((x for x in hm["devices"] if x["id"] == parts[2]), None)
                if not d or parts[4] not in d["capabilitiesObj"]:
                    return self._send(404, {"error": "not_found"})
                d["capabilitiesObj"][parts[4]]["value"] = self._body()["value"]
                return self._send(200, {})
            if parts in (["flow", "flow"], ["flow", "advancedflow"]):
                adv = parts[1] == "advancedflow"
                return self._send(200, {f["id"]: {"id": f["id"], "name": f["name"], "enabled": True, "triggerable": True} for f in hm["flows"] if f["advanced"] == adv})
            if parts[0] == "flow" and len(parts) == 4 and parts[3] == "trigger" and method == "POST":
                log["homey_flows"].append(parts[2])
                return self._send(200, {})
            if parts == ["logic", "variable"]:
                return self._send(200, {v["id"]: v for v in hm["variables"]})
            if parts[:2] == ["logic", "variable"] and len(parts) == 3 and method == "PUT":
                v = next((x for x in hm["variables"] if x["id"] == parts[2]), None)
                if not v:
                    return self._send(404, {"error": "not_found"})
                v["value"] = self._body()["value"]
                return self._send(200, v)
            self._send(404, {"error": "not_found"})

        def _telegram(self, call):
            body = self._body()
            if call == "getUpdates":
                offset = int(body.get("offset") or 0)
                ups = [u for u in log["tg_updates"] if u["update_id"] >= offset]
                if not ups and body.get("timeout"):
                    time.sleep(min(2, int(body["timeout"])))
                return self._send(200, {"ok": True, "result": ups})
            if call == "sendMessage":
                log["tg_sent"].append(body)
                return self._send(200, {"ok": True, "result": {"message_id": len(log["tg_sent"])}})
            self._send(404, {"ok": False, "description": "Not Found: method not found"})

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    srv.handle_error = lambda *a: None  # a program stopped mid-request (the Telegram listener is killed when its test ends)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def tg_add(text, chat=TG_CHAT, minutes_ago=0):
        n = len(log["tg_updates"]) + 1
        log["tg_updates"].append({"update_id": 1000 + n, "message": {"message_id": n, "date": int(time.time() - minutes_ago * 60), "text": text,
                                                                    "chat": {"id": chat, "type": "private", "first_name": "Sample"},
                                                                    "from": {"id": chat, "first_name": "Sample", "last_name": "Baker"}}})
    for m in data["telegram"]["messages"]:
        tg_add(m["text"], minutes_ago=m["hours_ago"] * 60)
    tg_add("Someone else's message about starter", chat=999, minutes_ago=30)
    imap_port, smtp_port = _mail_servers(data["email"], log)

    ids = [100000]

    def discord_add(channel, text, user, bot=False):
        ids[0] += 1
        m = {"id": str(ids[0]), "content": text, "timestamp": _iso(0), "author": {"username": user, "global_name": user, "bot": bot}}
        log["discord"].setdefault(channel, []).append(m)
        return m

    def slack_add(channel, text, user, bot=False):
        ids[0] += 1
        m = dict({"type": "message", "ts": f"{1700000000 + ids[0]}.000100", "text": text, "user": user}, **({"bot_id": user, "subtype": "bot_message"} if bot else {}))
        log["slack"].setdefault(channel, []).append(m)
        return m
    for m in reversed(data["discord"]["messages"]):
        discord_add(DISCORD_CHANNEL, m["text"], m["from"])
    discord_add(DISCORD_CHANNEL, "Bot's own earlier post", "SecondThought", bot=True)  # newest message at start is a bot's
    discord_add("999", "Someone else's channel: bake-along cancelled", "stranger")
    for m in reversed(data["slack"]["messages"]):
        slack_add(SLACK_CHANNEL, m["text"], m["from"])
    slack_add("C999", "Other channel: oven broken", "stranger")
    log["discord_add"], log["slack_add"] = discord_add, slack_add

    def add_feed_item(title, link):
        feeds[0]["items"].insert(0, {"title": title, "link": link, "hours_ago": 0, "summary": "Just in."})

    def add_review(title):
        gh["pulls"].append({"repo": "sample-baker/recipes", "number": 3, "title": title, "user": "crumb-shot", "days_ago": 0, "draft": False,
                            "review_requested": True, "body": "", "head": "x", "base": "main", "files": [], "comments": []})
    log["add_feed_item"], log["add_review"] = add_feed_item, add_review
    return base, log, tg_add, imap_port, smtp_port


# ----- A tiny IMAP and SMTP server: just enough for search, read and send -----

def _mail_servers(email_data, log):
    import email.utils
    from email.message import EmailMessage
    msgs = []
    for m in sorted(email_data["messages"], key=lambda x: x["id"]):
        e = EmailMessage()
        e["From"], e["To"], e["Subject"] = m["from"], MAIL_USER, m["subject"]
        e["Date"] = email.utils.format_datetime(datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=m["hours_ago"]))
        if m["id"] == "1041":  # one HTML email with an attachment, to check the text comes out readably
            e.set_content(m["body"])
            e.add_alternative("<html><body><p>" + m["body"].replace("\n", "<br>") + "</p><script>x()</script></body></html>", subtype="html")
            e.add_attachment(b"rye starter notes", maintype="text", subtype="plain", filename="starter-notes.txt")
        else:
            e.set_content(m["body"])
        msgs.append((int(m["id"]), m["hours_ago"], e.as_bytes()))

    def add_mail(sender, subject, body):
        e = EmailMessage()
        e["From"], e["To"], e["Subject"] = sender, MAIL_USER, subject
        e["Date"] = email.utils.format_datetime(datetime.datetime.now(datetime.timezone.utc))
        e.set_content(body)
        msgs.append((max(u for u, h, r in msgs) + 1, 0, e.as_bytes()))
    log["add_mail"] = add_mail

    class Imap(socketserver.StreamRequestHandler):
        def send(self, line):
            self.wfile.write(line if isinstance(line, bytes) else (line + "\r\n").encode())

        def handle(self):
            self.send("* OK test IMAP ready")
            authed = False
            while True:
                raw = self.rfile.readline()
                if not raw:
                    return
                line = raw.decode("utf-8", "replace").rstrip("\r\n")
                tag, _, rest = line.partition(" ")
                cmd, _, args = rest.partition(" ")
                cmd = cmd.upper()
                if cmd == "UID":
                    cmd2, _, args = args.partition(" ")
                    cmd = "UID " + cmd2.upper()
                if cmd == "CAPABILITY":
                    self.send("* CAPABILITY IMAP4rev1 AUTH=PLAIN")
                    self.send(f"{tag} OK done")
                elif cmd == "LOGIN":
                    user, pw = [a.strip('"') for a in args.split(" ", 1)]
                    if user == MAIL_USER and pw == MAIL_PASS:
                        authed = True
                        self.send(f"{tag} OK logged in")
                    else:
                        self.send(f"{tag} NO [AUTHENTICATIONFAILED] Invalid credentials")
                elif cmd in ("SELECT", "EXAMINE") and authed:
                    self.send(f"* {len(msgs)} EXISTS")
                    self.send(f"{tag} OK [READ-ONLY] selected")
                elif cmd == "UID SEARCH" and authed and (args.strip() == "ALL" or args.startswith("UID ")):
                    low = int(args.split()[1].split(":")[0]) if args.startswith("UID ") else 0
                    self.send("* SEARCH " + " ".join(str(u) for u, h, r in msgs if u >= low))
                    self.send(f"{tag} OK search done")
                elif cmd == "UID SEARCH" and authed:
                    words = args.split()
                    days = 365
                    if "SINCE" in words:
                        since = datetime.datetime.strptime(words[words.index("SINCE") + 1], "%d-%b-%Y")
                        days = (datetime.datetime.now() - since).total_seconds() / 86400
                    text = args.split("TEXT", 1)[1].strip().strip('"').lower() if "TEXT" in args else ""
                    hits = [str(uid) for uid, h, raw_ in msgs if h <= days * 24 + 24 and (not text or text in raw_.decode("utf-8", "replace").lower())]
                    self.send("* SEARCH " + " ".join(hits))
                    self.send(f"{tag} OK search done")
                elif cmd == "UID FETCH" and authed:
                    uid = args.split()[0]
                    found = next((raw_ for u, h, raw_ in msgs if str(u) == uid), None)
                    if found is not None:
                        part = found[:20000] if "<0.20000>" in args else found
                        self.send(f"* 1 FETCH (UID {uid} BODY[] {{{len(part)}}}".encode() + b"\r\n" + part + b")\r\n")
                    self.send(f"{tag} OK fetch done")
                elif cmd == "LOGOUT":
                    self.send("* BYE")
                    self.send(f"{tag} OK bye")
                    return
                else:
                    self.send(f"{tag} BAD unknown command")

    class Smtp(socketserver.StreamRequestHandler):
        def handle(self):
            w = lambda s: self.wfile.write((s + "\r\n").encode())  # noqa: E731
            w("220 test SMTP ready")
            mail = {"to": []}
            while True:
                raw = self.rfile.readline()
                if not raw:
                    return
                line = raw.decode("utf-8", "replace").rstrip("\r\n")
                up = line.upper()
                if up.startswith(("EHLO", "HELO")):
                    w("250-test")
                    w("250 AUTH PLAIN LOGIN")
                elif up.startswith("AUTH"):
                    w("235 2.7.0 Authentication successful")
                elif up.startswith("MAIL FROM"):
                    mail["from"] = line.split(":", 1)[1].strip()
                    w("250 OK")
                elif up.startswith("RCPT TO"):
                    mail["to"].append(line.split(":", 1)[1].strip())
                    w("250 OK")
                elif up == "DATA":
                    w("354 go ahead")
                    body = []
                    while True:
                        ln = self.rfile.readline().decode("utf-8", "replace")
                        if ln.rstrip("\r\n") == ".":
                            break
                        body.append(ln)
                    mail["data"] = "".join(body)
                    log["mail_sent"].append(dict(mail))
                    mail = {"to": []}
                    w("250 OK queued")
                elif up == "QUIT":
                    w("221 bye")
                    return
                else:
                    w("250 OK")

    class Srv(socketserver.ThreadingTCPServer):
        daemon_threads = True
        allow_reuse_address = True

        def handle_error(self, *a):
            pass
    servers = [Srv(("127.0.0.1", 0), Imap), Srv(("127.0.0.1", 0), Smtp)]
    for s in servers:
        threading.Thread(target=s.serve_forever, daemon=True).start()
    return servers[0].server_address[1], servers[1].server_address[1]
