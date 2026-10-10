"""Web pages, news feeds, calendars, Home Assistant, GitHub, Telegram, email, chat, MQTT and Homey.

Part of the second_thought package. tools/sync.py joins these files, in order, into
python/runtime.py, which is what ships inside every exported program and the page.
"""
import asyncio
import datetime
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from .settings import WHERE_KEYS
from .core import (DISCORD_API, GITHUB_API, HA_SENSITIVE, HA_TOKEN, HA_TTS_ENTITY, HA_URL, MESSAGE_VALUE, PAGES_FILE,
    Picture, Retryable, RunError, SLACK_API, TELEGRAM_API, TELEGRAM_FILE, WEEKDAYS, _WebSocket, _locked, _num_like,
    _short, _write_json, num, read_text_file, round_js, to_str)
# ---- package only: tools/sync.py leaves everything above this line out of python/runtime.py ----


MAX_PAGE_CHARS = 12000


def page_text(raw, ctype=""):
    """A web page's readable words: no scripts, styles or tags. Gives (title, text)."""
    import html as _html
    if "html" not in ctype.lower() and not re.match(r"\s*<", raw):
        return "", re.sub(r"[ \t]+", " ", raw).strip()
    m = re.search(r"<title[^>]*>(.*?)</title>", raw, re.S | re.I)
    title = _html.unescape(re.sub(r"\s+", " ", m.group(1))).strip() if m else ""
    raw = re.sub(r"<(script|style|noscript|svg|template|head)\b.*?</\1\s*>", " ", raw, flags=re.S | re.I)
    raw = re.sub(r"<!--.*?-->", " ", raw, flags=re.S)
    raw = re.sub(r"<(br|/p|/div|/li|/h[1-6]|/tr|/section|/article)\b[^>]*>", "\n", raw, flags=re.I)
    text = _html.unescape(re.sub(r"<[^>]+>", " ", raw)).replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", re.sub(r" *\n *", "\n", text)).strip()
    return title, text


def _public_addresses(host, port):
    """Looks the name up once, and refuses it if any address is on your own network (your router, your server, this
    computer). The connection then goes to exactly these addresses, so the name can't change its answer in between."""
    import ipaddress
    import socket
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError:
        raise RunError(f"Couldn't find the website “{host}”.") from None
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise RunError("The agent only reads public web pages and feeds, not addresses on your own network (local_pages = yes allows them).")
    return infos


def _public_only(host):
    _public_addresses(host, None)


def _local_pages():
    """local_pages = yes in second-thought.ini lets the agent read pages and feeds on your own network too."""
    return os.environ.get("RB_LOCAL_PAGES", "").strip().lower() in ("1", "yes", "true", "on")


def _pinned_connections():
    """HTTP and HTTPS connections that check the address they connect to (see _public_addresses). HTTPS still checks the
    website's certificate against its name."""
    import http.client
    import socket

    def connect(conn):
        err = None
        for family, kind, proto, _, addr in _public_addresses(conn.host, conn.port):
            sock = socket.socket(family, kind, proto)
            try:
                sock.settimeout(conn.timeout)
                sock.connect(addr)
                conn.sock = sock
                return
            except OSError as e:
                err = e
                sock.close()
        raise err or OSError("no address to connect to")

    class Plain(http.client.HTTPConnection):
        def connect(self):
            connect(self)

    class Secure(http.client.HTTPSConnection):
        def connect(self):
            connect(self)
            self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host)

    class PlainHandler(urllib.request.HTTPHandler):
        def http_open(self, req):
            return self.do_open(Plain, req)

    class SecureHandler(urllib.request.HTTPSHandler):
        def https_open(self, req):
            return self.do_open(Secure, req)
    return PlainHandler, SecureHandler


class _PublicRedirects(urllib.request.HTTPRedirectHandler):
    """Follows a redirect only to a web page. Without a proxy, the new address is checked as it connects."""
    check_hosts = False

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        u = urllib.parse.urlparse(newurl)
        if u.scheme not in ("http", "https") or not u.hostname:
            raise RunError("That address sent the program somewhere that isn't a web page.")
        if self.check_hosts:
            _public_only(u.hostname)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _ProxiedRedirects(_PublicRedirects):
    """Through a proxy nothing is checked as it connects, so every address a redirect sends the program to is checked first."""
    check_hosts = True


def get_url(url, trusted=False, what="read_page", limit=3_000_000):
    """Fetches a web address. Gives (content type, bytes). Addresses that come from your settings are trusted; others
    (chosen by the agent) must be public, unless local_pages = yes."""
    url = to_str(url).strip()
    if url.lower().startswith("webcal://"):
        url = "https://" + url[9:]
    u = urllib.parse.urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise RunError(f"{what} needs a web address starting with http:// or https://.")
    guard = not trusted and not _local_pages()
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; SecondThought/1.0)",
                                               "Accept": "text/html,application/xhtml+xml,application/xml,text/plain;q=0.9,*/*;q=0.5"})
    if not guard:
        opener = urllib.request.build_opener()
    elif urllib.request.getproxies().get(u.scheme) and not urllib.request.proxy_bypass(u.hostname):
        # Through a proxy, the proxy looks the name up, so the best this side can do is check it first,
        # and check again wherever a redirect points.
        _public_only(u.hostname)
        opener = urllib.request.build_opener(_ProxiedRedirects)
    else:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), *_pinned_connections(), _PublicRedirects)
    try:
        with opener.open(req, timeout=20) as r:
            return r.headers.get("Content-Type", ""), r.read(limit)
    except urllib.error.HTTPError as e:
        raise RunError(f"{what} couldn't open {_short(url, 80)}: the website answered {e.code}.") from None
    except urllib.error.URLError as e:
        raise RunError(f"{what} couldn't reach {_short(url, 80)} ({e.reason}).") from None


def _decode(data, ctype):
    m = re.search(r"charset=([\w-]+)", ctype or "", re.I)
    try:
        return data.decode(m.group(1) if m else "utf-8", "replace")
    except LookupError:
        return data.decode("utf-8", "replace")


def fetch_page(url):
    ctype, data = get_url(url)
    url = to_str(url).strip()
    if not re.search(r"text/|html|xml|json", ctype, re.I) and data[:1] != b"<":
        raise RunError(f"That address isn't a web page or text ({ctype.split(';')[0] or 'unknown type'}).")
    title, text = page_text(_decode(data, ctype), ctype)
    if not text:
        return f"{title or url}\n\n(The page has no readable words. It may need a browser to show its content.)"
    cut = len(text) > MAX_PAGE_CHARS
    return (f"{title}\n{url}\n\n" if title else f"{url}\n\n") + text[:MAX_PAGE_CHARS] + ("\n\n… (the page goes on; this is the first part)" if cut else "")


# ----- News feeds (RSS and Atom) -----

def _when(dt):
    return f"{WEEKDAYS[dt.weekday()][:3]} {dt:%d %b %H:%M}"


def _parse_date(text):
    import email.utils
    text = to_str(text).strip()
    if not text:
        return None
    try:
        d = email.utils.parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        try:
            d = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    return d.astimezone().replace(tzinfo=None) if d.tzinfo else d


def parse_feed(raw):
    """An RSS or Atom feed -> (title, [{title, link, date, summary}]), newest first."""
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(raw.encode("utf-8") if isinstance(raw, str) else raw)
    except ET.ParseError:
        raise RunError("That address isn't a news feed (RSS or Atom).") from None
    local = lambda el: el.tag.rsplit("}", 1)[-1].lower()  # noqa: E731

    def child(el, *names):
        for c in el:
            if local(c) in names and (c.text or "").strip():
                return c.text.strip()
        return ""
    if local(root) not in ("rss", "feed", "rdf"):
        raise RunError("That address isn't a news feed (RSS or Atom).")
    channel = next((c for c in root if local(c) == "channel"), root)
    title = child(channel, "title")
    items = []
    for el in root.iter():
        if local(el) not in ("item", "entry"):
            continue
        link = child(el, "link")
        if not link:
            for c in el:
                if local(c) == "link" and c.get("href") and c.get("rel", "alternate") == "alternate":
                    link = c.get("href")
                    break
        summary = child(el, "description", "summary", "content", "encoded")
        items.append({"title": page_text(child(el, "title"))[1] or "(no title)", "link": link,
                      "date": _parse_date(child(el, "pubdate", "published", "updated", "date")),
                      "summary": _short(page_text(summary)[1], 300)})
    items.sort(key=lambda x: x["date"] or datetime.datetime.min, reverse=True)
    return title, items


# ----- Calendars (iCal) -----

def _ics_lines(text):
    out = []
    for line in to_str(text).replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line[:1] in (" ", "\t") and out:
            out[-1] += line[1:]
        elif line:
            out.append(line)
    return out


def _ics_unescape(v):
    return re.sub(r"\\([\\,;nN])", lambda m: "\n" if m.group(1) in "nN" else m.group(1), v)


def _ics_time(value, params):
    """'20261010T090000Z' or with TZID -> a local datetime; '20261010' -> (date, True) for all-day."""
    v = value.strip()
    if re.fullmatch(r"\d{8}", v) or params.get("VALUE") == "DATE":
        return datetime.datetime.strptime(v[:8], "%Y%m%d"), True
    d = datetime.datetime.strptime(v[:15], "%Y%m%dT%H%M%S")
    if v.endswith("Z"):
        return d.replace(tzinfo=datetime.timezone.utc).astimezone().replace(tzinfo=None), False
    tz = params.get("TZID")
    if tz:
        try:
            from zoneinfo import ZoneInfo
            return d.replace(tzinfo=ZoneInfo(tz.strip('"'))).astimezone().replace(tzinfo=None), False
        except Exception:  # noqa: BLE001 - an unknown time zone: treat it as local time
            pass
    return d, False


_ICS_DAYS = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}


def _ics_repeats(start, rule, until_view):
    """Start times of a repeating event, up to the end of the view. Handles DAILY, WEEKLY (with BYDAY), MONTHLY, YEARLY,
    INTERVAL, COUNT and UNTIL: what calendars use for nearly every repeating event."""
    r = dict(part.split("=", 1) for part in rule.split(";") if "=" in part)
    freq, step = r.get("FREQ", ""), max(1, int(r.get("INTERVAL", "1") or 1))
    count = int(r["COUNT"]) if r.get("COUNT", "").isdigit() else None
    until = _ics_time(r["UNTIL"], {})[0] if r.get("UNTIL") else None
    if until is not None and len(r["UNTIL"]) == 8:
        until += datetime.timedelta(days=1) - datetime.timedelta(seconds=1)
    days = [_ICS_DAYS[d[-2:]] for d in r.get("BYDAY", "").split(",") if d[-2:] in _ICS_DAYS]
    out, n, i = [], 0, 0
    while i < 3000:
        if freq == "DAILY":
            batch = [start + datetime.timedelta(days=i * step)]
        elif freq == "WEEKLY":
            week = start - datetime.timedelta(days=start.weekday()) + datetime.timedelta(weeks=i * step)
            batch = sorted(week + datetime.timedelta(days=d) for d in (days or [start.weekday()]))
            batch = [b for b in batch if b >= start]
        elif freq in ("MONTHLY", "YEARLY"):
            months = i * step * (12 if freq == "YEARLY" else 1)
            y, m = start.year + (start.month - 1 + months) // 12, (start.month - 1 + months) % 12 + 1
            try:
                batch = [start.replace(year=y, month=m)]
            except ValueError:  # the 31st in a short month: skipped, as calendars do
                batch = []
        else:
            return [start]
        for b in batch:
            if (until and b > until) or (count is not None and n >= count) or b > until_view:
                return out
            out.append(b)
            n += 1
        i += 1
    return out


def calendar_events(text, start, end):
    """Events between start and end, from iCal text, as {start, end, all_day, title, location}, in time order."""
    events, moved, cur = [], set(), None
    for line in _ics_lines(text):
        if line == "BEGIN:VEVENT":
            cur = {}
            continue
        if line == "END:VEVENT":
            if cur is not None:
                events.append(cur)
            cur = None
            continue
        if cur is None or ":" not in line:
            continue
        head, value = line.split(":", 1)
        name, *ps = head.split(";")
        params = dict(x.split("=", 1) for x in ps if "=" in x)
        name = name.upper()
        if name in ("DTSTART", "DTEND", "RECURRENCE-ID"):
            try:
                cur[name] = _ics_time(value, params)
            except ValueError:
                pass
        elif name == "EXDATE":
            for v in value.split(","):
                try:
                    cur.setdefault("EXDATE", set()).add(_ics_time(v, params)[0])
                except ValueError:
                    pass
        elif name in ("SUMMARY", "LOCATION", "RRULE", "UID", "STATUS", "DURATION"):
            cur[name] = _ics_unescape(value) if name in ("SUMMARY", "LOCATION") else value
    for e in events:
        if "RECURRENCE-ID" in e:
            moved.add((e.get("UID"), e["RECURRENCE-ID"][0]))
    out = []
    for e in events:
        if "DTSTART" not in e or e.get("STATUS", "").upper() == "CANCELLED":
            continue
        s0, all_day = e["DTSTART"]
        if "DTEND" in e:
            length = e["DTEND"][0] - s0
        else:
            m = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?", e.get("DURATION", ""))
            length = datetime.timedelta(days=int(m.group(1) or 0), hours=int(m.group(2) or 0), minutes=int(m.group(3) or 0)) if m \
                else datetime.timedelta(days=1 if all_day else 0)
        starts = _ics_repeats(s0, e["RRULE"], end) if e.get("RRULE") and "RECURRENCE-ID" not in e else [s0]
        for st in starts:
            if st in e.get("EXDATE", ()) or (("RECURRENCE-ID" not in e) and (e.get("UID"), st) in moved):
                continue
            if st + length > start and st < end or (length == datetime.timedelta(0) and start <= st < end):
                out.append({"start": st, "end": st + length, "all_day": all_day, "title": e.get("SUMMARY", "(no title)"),
                            "location": e.get("LOCATION", "")})
    out.sort(key=lambda x: (x["start"], not x["all_day"]))
    return out


def event_line(e):
    if e["all_day"]:
        days = max(1, (e["end"] - e["start"]).days)
        when = "all day" + (f" ({days} days)" if days > 1 else "")
    else:
        when = f"{e['start']:%H:%M}–{e['end']:%H:%M}"
    return f"{when}  {e['title']}" + (f" ({e['location']})" if e["location"] else "")


def free_slots(events, day, frm, to, minutes):
    """Free stretches of at least this many minutes between frm and to (HH:MM) on day."""
    def at(hhmm):
        m = re.fullmatch(r"\s*(\d{1,2})[:.](\d{2})\s*", to_str(hhmm))
        if not m or int(m.group(1)) > 24 or int(m.group(2)) > 59:
            raise RunError(f"“{hhmm}” isn't a time like 09:00.")
        return day + datetime.timedelta(hours=int(m.group(1)), minutes=int(m.group(2)))
    a, b = at(frm), at(to)
    busy = sorted((max(e["start"], a), min(e["end"], b)) for e in events if not e["all_day"] and e["end"] > a and e["start"] < b)
    free, t = [], a
    for s_, e_ in busy:
        if s_ > t:
            free.append((t, s_))
        t = max(t, e_)
    if b > t:
        free.append((t, b))
    need = datetime.timedelta(minutes=max(1, round_js(num(minutes) or 30)))
    return [(x, y) for x, y in free if y - x >= need]


def parse_day(text):
    """'today', 'tomorrow', a weekday name, or YYYY-MM-DD -> midnight that day."""
    t = to_str(text).strip().lower()
    today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if t in ("", "today"):
        return today
    if t == "tomorrow":
        return today + datetime.timedelta(days=1)
    names = [w.lower() for w in WEEKDAYS]
    if t in names or t[:3] in [n[:3] for n in names]:
        k = [n[:3] for n in names].index(t[:3])
        return today + datetime.timedelta(days=(k - today.weekday()) % 7)
    try:
        return datetime.datetime.strptime(t, "%Y-%m-%d")
    except ValueError:
        raise RunError(f"“{text}” isn't a day. Use today, tomorrow, a weekday or YYYY-MM-DD.") from None


class Connections:
    """Home Assistant, the connections (feeds, GitHub, Telegram, email, chat, MQTT, Homey) and listeners. Part of Runtime."""
    # ----- Home Assistant -----
    def _ha_request(self, method, path, body=None, raw=False):
        if not HA_TOKEN:
            raise RunError(f"This program uses Home Assistant. Put HA_URL (for example http://homeassistant.local:8123) "
                           f"and HA_TOKEN (a long-lived access token from your Home Assistant profile, Security tab) {WHERE_KEYS}.")
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(HA_URL + path, data=data, method=method,
                                     headers={"Authorization": "Bearer " + HA_TOKEN, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                payload = r.read()
                return (payload, r.headers.get("Content-Type", "")) if raw else (json.loads(payload or b"null"))
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise RunError("Home Assistant refused the token (401). Check HA_TOKEN.")
            if e.code == 404:
                raise RunError(f"Home Assistant has nothing at {path} (404). Check the entity or service name.")
            raise Retryable(f"Home Assistant answered {e.code} for {path}.")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise Retryable(f"Couldn't reach Home Assistant at {HA_URL} ({getattr(e, 'reason', e)}).")

    async def _ha(self, method, path, body=None, raw=False):
        return await asyncio.to_thread(self._ha_request, method, path, body, raw)

    @staticmethod
    def _ha_val(v):
        return num(v) if _num_like(v) else v

    async def _ha_entity(self, entity):
        entity = to_str(entity).strip()
        if not re.match(r"^[a-z_]+\.[a-z0-9_]+$", entity):
            raise RunError(f"“{entity}” isn't an entity id. Use something like light.kitchen.")
        return await self._ha("GET", "/api/states/" + entity)

    async def ha_state(self, entity):
        return self._ha_val((await self._ha_entity(entity))["state"])

    async def ha_attr(self, attr, entity):
        e = await self._ha_entity(entity)
        attr = to_str(attr).strip()
        if attr == "state":
            return self._ha_val(e["state"])
        v = e.get("attributes", {}).get(attr, "")
        return self._ha_val(v) if not isinstance(v, (list, dict)) else json.dumps(v)

    async def _ha_match(self, text):
        words = [w for w in re.split(r"[\s,]+", to_str(text).lower()) if w]
        out = []
        for e in await self._ha("GET", "/api/states"):
            a = e.get("attributes", {})
            hay = " ".join(to_str(x) for x in (e["entity_id"], a.get("friendly_name"), a.get("area"), e["state"],
                                                a.get("device_class"), a.get("unit_of_measurement"))).lower()
            if not words or "*" in words or all(w in hay for w in words):
                out.append(e)
        return out[:150]

    async def ha_find(self, text):
        return [{"entity": e["entity_id"], "name": e.get("attributes", {}).get("friendly_name", e["entity_id"]),
                 "state": self._ha_val(e["state"]), "unit": e.get("attributes", {}).get("unit_of_measurement", ""),
                 "area": e.get("attributes", {}).get("area", "")} for e in await self._ha_match(text)]

    async def ha_summary(self, text):
        lines = []
        for e in await self._ha_match(text):
            a = e.get("attributes", {})
            extra = "".join(f"; {k.replace('_', ' ')}: {v}" for k, v in a.items()
                            if k not in ("friendly_name", "area", "unit_of_measurement", "device_class", "icon", "entity_picture",
                                         "supported_features", "attribution", "state_class") and not isinstance(v, (list, dict)))
            unit = " " + a["unit_of_measurement"] if a.get("unit_of_measurement") else ""
            area = f" [{a['area']}]" if a.get("area") else ""
            lines.append(f"{a.get('friendly_name', e['entity_id'])} ({e['entity_id']}): {e['state']}{unit}{area}{extra}")
        return "\n".join(lines) or "(no matching entities)"

    async def ha_history(self, entity, hours):
        entity = to_str(entity).strip()
        hours = max(1, min(168, num(hours) or 24))
        start = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)).isoformat()
        q = urllib.parse.urlencode({"filter_entity_id": entity, "minimal_response": "", "no_attributes": ""})
        data = await self._ha("GET", "/api/history/period/" + urllib.parse.quote(start) + "?" + q)
        rows = data[0] if data else []
        if len(rows) > 48:
            step = len(rows) / 48
            rows = [rows[int(i * step)] for i in range(48)] + [rows[-1]]
        out = []
        for r in rows:
            try:
                t = datetime.datetime.fromisoformat(r.get("last_changed", "").replace("Z", "+00:00")).astimezone()
                label = t.strftime("%a %H:%M")
            except ValueError:
                label = r.get("last_changed", "")
            out.append({"time": label, "state": self._ha_val(r.get("state", ""))})
        return out

    async def ha_snapshot(self, camera):
        camera = to_str(camera).strip()
        data, ctype = await self._ha("GET", "/api/camera_proxy/" + camera, raw=True)
        pic = Picture(data, (ctype or "image/jpeg").split(";")[0], camera.replace("camera.", "") + "-snapshot")
        self.log("Snapshot: " + camera, "Saved to " + self._picture_path(pic), "done")
        return pic

    async def _ha_call_live(self, service, entity, data_text=""):
        service, entity = to_str(service).strip(), to_str(entity).strip()
        if not re.match(r"^[a-z_]+\.[a-z0-9_]+$", service):
            raise RunError(f"“{service}” isn't a service name. Use domain.service, for example light.turn_off.")
        body = {}
        if to_str(data_text).strip():
            try:
                body = json.loads(to_str(data_text))
            except ValueError:
                raise RunError(f"The data for {service} isn't valid JSON. Use something like {{\"temperature\": 20}}.")
        if entity:
            body["entity_id"] = entity
        sensitive = any(re.match(p, service) for p in HA_SENSITIVE)
        if not sensitive and not await self._allowed(["ha"], f"{service} on {entity or 'Home Assistant'}"):
            return False
        if sensitive:
            if self.schedule_mode and not sys.stdin.isatty():
                self.log("Not done", f"{service} on {entity} needs your approval, and nobody is at the keyboard.", "refused")
                return False
            if not await self.approve(f"Allow {service} on {entity or 'Home Assistant'}? (unlocking, opening and disarming always ask)"):
                self.log("Not done", f"{service} on {entity} was refused, so nothing happened.", "refused")
                return False
        domain, action = service.split(".", 1)
        await self._ha("POST", f"/api/services/{domain}/{action}", body)
        self.log("Home Assistant: " + service, entity + (f" with {to_str(data_text).strip()}" if to_str(data_text).strip() else ""), "done")
        return True

    async def _ha_notify_live(self, target, text):
        target, text = to_str(target).strip() or "persistent_notification", to_str(text)
        if not text.strip():
            raise RunError("The 'notify' block has no message.")
        if not await self._allowed(["ha", "messages"], f"send a notification to {target}: {_short(text, 120)}"):
            return
        if target in ("persistent_notification", "persistent_notification.create"):
            await self._ha("POST", "/api/services/persistent_notification/create", {"message": text, "title": "Second Thought"})
        else:
            svc = target.split(".", 1)[1] if target.startswith("notify.") else target
            await self._ha("POST", f"/api/services/notify/{svc}", {"message": text, "title": "Second Thought"})
        self.log("Notification → " + target, text, "sent")

    async def _ha_speak_live(self, text, player):
        text, player = to_str(text), to_str(player).strip()
        if not text.strip():
            raise RunError("The 'say' block has nothing to say.")
        if not await self._allowed(["ha", "messages"], f"say on {player or 'a speaker'}: {_short(text, 120)}"):
            return
        await self._ha("POST", "/api/services/tts/speak", {"entity_id": HA_TTS_ENTITY, "media_player_entity_id": player, "message": text})
        self.log("Spoken on " + player, text, "sent")

    @staticmethod
    def ha_trigger():
        v = MESSAGE_VALUE.get()
        return v if isinstance(v, dict) else {"entity": "", "name": "", "from": "", "to": ""}

    async def _listen_ha_event(self, items):
        """'when Home Assistant event … happens': subscribes to Home Assistant's events over its WebSocket API, so a button press,
        an automation firing or a custom event starts the script at once. Reconnects (after a minute) if the connection drops."""
        if not HA_TOKEN:
            raise RunError(f"Home Assistant events need HA_URL and HA_TOKEN {WHERE_KEYS}.")
        wants = []
        for arg, fn in items:
            kind, _, words = to_str(arg).partition("|")
            kind = kind.strip()
            wants.append(("" if kind.lower() in ("", "anything") else kind, words.lower().split(), fn))
        url = re.sub(r"^http", "ws", HA_URL) + "/api/websocket"
        try:
            ws = await _WebSocket.connect(url, timeout=10)
        except asyncio.TimeoutError:
            raise RunError(f"Home Assistant didn't answer at {url} within 10 seconds.") from None
        try:
            # Home Assistant answers these at once; a stalled sign-in becomes an error, so the listener tries again.
            try:
                hello = await asyncio.wait_for(ws.recv_json(), 10)
                if hello.get("type") == "auth_required":
                    await ws.send_json({"type": "auth", "access_token": HA_TOKEN})
                    hello = await asyncio.wait_for(ws.recv_json(), 10)
            except asyncio.TimeoutError:
                raise RunError("Home Assistant didn't finish signing in for events within 10 seconds.") from None
            if hello.get("type") != "auth_ok":
                raise RunError("Home Assistant refused the token for events (auth_invalid). Check HA_TOKEN.")
            kinds = [None] if any(k == "" for k, _, _ in wants) else sorted({k for k, _, _ in wants})
            for n, kind in enumerate(kinds, 1):
                await ws.send_json(dict({"id": n, "type": "subscribe_events"}, **({"event_type": kind} if kind else {})))
            print("Listening for Home Assistant events: " + ", ".join(k or "everything" for k in kinds) + ".", flush=True)
            while True:
                msg = await ws.recv_json()
                if msg.get("type") == "result" and not msg.get("success", True):
                    raise RunError("Home Assistant wouldn't send those events: " + to_str((msg.get("error") or {}).get("message")))
                if msg.get("type") != "event":
                    continue
                ev = msg.get("event") or {}
                kind, data = to_str(ev.get("event_type")), ev.get("data") or {}
                blob = json.dumps(data, ensure_ascii=False, default=str)
                rec = {"event_type": kind, "entity": to_str(data.get("entity_id", "")), "data": blob, "time": to_str(ev.get("time_fired", "")),
                       "text": f"{kind}: {_short(blob, 400)}"}
                for k, v in data.items():
                    rec.setdefault(str(k), json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
                for want, words, fn in wants:
                    if (not want or want == kind) and all(w in blob.lower() for w in words):
                        self._fire(fn, dict(rec), "Home Assistant: " + kind)
        finally:
            ws.close()

    # ----- Connections: news feeds, GitHub, Telegram, email and calendar -----
    MAX_FEED_ITEMS = 10

    async def feed_items(self, url="", limit=10, trusted=False):
        """Items from one feed, or from every feed in your settings (feeds = ...) when url is empty."""
        url = to_str(url).strip()
        mine = [u for u in re.split(r"[\s,]+", os.environ.get("RB_FEEDS", "")) if u]
        urls = [url] if url else mine
        if not urls:
            raise RunError(f"No feed given, and no feeds in your settings. Add  feeds = <addresses>  {WHERE_KEYS}.")
        limit = max(1, min(50, round_js(num(limit)) or self.MAX_FEED_ITEMS))
        out = []
        for u in urls:
            ctype, data = await asyncio.to_thread(get_url, u, trusted or u in mine, "read_feed", 5_000_000)
            title, items = parse_feed(data)
            for it in items[:limit]:
                out.append(dict(it, feed=title or u))
        return out

    async def feed_records(self, url):
        """For the 'news from feed' block: a list of records (feed, title, link, date, summary)."""
        items = await self.feed_items(url)
        recs = [{"feed": i["feed"], "title": i["title"], "link": i["link"], "date": _when(i["date"]) if i["date"] else "",
                 "summary": i["summary"]} for i in items]
        self.log("News: " + (_short(url, 60) or "your feeds"), "\n".join(f"{r['date']}  {r['title']}" for r in recs[:12]) or "(nothing)",
                 f"{len(recs)} items")
        return recs

    @staticmethod
    def feed_text(items):
        lines, feed = [], None
        for i in items:
            if i["feed"] != feed:
                feed = i["feed"]
                lines.append(("\n" if lines else "") + feed)
            lines.append(f"- {_when(i['date']) if i['date'] else '(no date)'}  {i['title']}" + (f"\n  {i['link']}" if i["link"] else "")
                         + (f"\n  {i['summary']}" if i["summary"] else ""))
        return "\n".join(lines) or "The feed has no items."

    # GitHub
    async def _gh(self, path, method="GET", body=None):
        token = os.environ.get("GITHUB_TOKEN", "")
        if not token:
            raise RunError(f"GitHub needs a token: set GITHUB_TOKEN {WHERE_KEYS} (make one at https://github.com/settings/tokens).")
        req = urllib.request.Request(GITHUB_API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                                              "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "SecondThought",
                                              "Content-Type": "application/json"})

        def go():
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    return json.loads(r.read() or b"null")
            except urllib.error.HTTPError as e:
                why = {401: "the token was refused. Check GITHUB_TOKEN", 403: "GitHub said no (the token may lack access, or the hourly limit was reached)",
                       404: "not found, or the token can't see it", 422: "GitHub couldn't use that request"}.get(e.code, f"GitHub answered {e.code}")
                raise RunError(f"GitHub: {why}.") from None
            except urllib.error.URLError as e:
                raise RunError(f"Couldn't reach GitHub ({e.reason}).") from None
        return await asyncio.to_thread(go)

    @staticmethod
    def _gh_repo(repo):
        repo = to_str(repo).strip().removeprefix("https://github.com/").strip("/")
        if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
            raise RunError(f"“{repo}” isn't a GitHub project. Use owner/name, like octocat/hello-world.")
        return repo

    @staticmethod
    def _ago(iso):
        d = _parse_date(iso)
        if not d:
            return ""
        h = (datetime.datetime.now() - d).total_seconds() / 3600
        return "just now" if h < 1 else f"{int(h)} h ago" if h < 48 else f"{int(h // 24)} days ago"

    async def gh_repos(self, owner=""):
        owner = to_str(owner).strip()
        rows = await self._gh(f"/users/{urllib.parse.quote(owner)}/repos?sort=pushed&per_page=30" if owner else "/user/repos?sort=pushed&per_page=30")
        return "\n".join(f"{r['full_name']}: {r.get('description') or '(no description)'} · {r.get('language') or '-'} · "
                         f"★{r.get('stargazers_count', 0)} · {r.get('open_issues_count', 0)} open issues and pull requests · pushed {self._ago(r.get('pushed_at'))}"
                         for r in rows) or "No projects."

    async def gh_pulls(self, repo, state="open"):
        repo = self._gh_repo(repo)
        state = to_str(state).strip().lower() or "open"
        rows = await self._gh(f"/repos/{repo}/pulls?state={state if state in ('open', 'closed', 'all') else 'open'}&per_page=20&sort=updated&direction=desc")
        return "\n".join(f"#{r['number']} {r['title']} · by {r['user']['login']} · updated {self._ago(r.get('updated_at'))}"
                         + (" · draft" if r.get("draft") else "") for r in rows) or f"No {state} pull requests in {repo}."

    async def _gh_search(self, q, n=20):
        data = await self._gh("/search/issues?per_page=" + str(n) + "&sort=updated&q=" + urllib.parse.quote(q))
        out = []
        for r in data.get("items", []):
            repo = r.get("repository_url", "").split("/repos/", 1)[-1]
            kind = "pull request" if "pull_request" in r else "issue"
            out.append(f"{repo} #{r['number']} {r['title']} · {kind} by {r['user']['login']} · {r.get('state', '')} · updated {self._ago(r.get('updated_at'))}")
        return out

    async def gh_for_me(self):
        review = await self._gh_search("is:pr is:open review-requested:@me archived:false")
        mine = await self._gh_search("is:pr is:open author:@me archived:false")
        return ("Waiting for your review:\n" + ("\n".join(review) or "(none)") + "\n\nYour open pull requests:\n" + ("\n".join(mine) or "(none)"))

    async def gh_search(self, query):
        query = to_str(query).strip()
        if not query:
            raise RunError("search_github needs something to search for.")
        return "\n".join(await self._gh_search(query)) or f"Nothing found for “{query}”."

    async def gh_read_pr(self, repo, number):
        repo, n = self._gh_repo(repo), round_js(num(number))
        pr = await self._gh(f"/repos/{repo}/pulls/{n}")
        files = await self._gh(f"/repos/{repo}/pulls/{n}/files?per_page=50")
        comments = await self._gh(f"/repos/{repo}/issues/{n}/comments?per_page=30")
        lines = [f"{repo} #{n}: {pr['title']}", f"By {pr['user']['login']} · {pr['state']}" + (" · draft" if pr.get("draft") else "")
                 + (" · merged" if pr.get("merged") else "") + f" · {pr['head']['ref']} → {pr['base']['ref']} · updated {self._ago(pr.get('updated_at'))}",
                 "", _short(pr.get("body") or "(no description)", 2000), "", f"Files changed ({len(files)}):"]
        budget = 9000
        for f in files:
            lines.append(f"- {f['filename']} (+{f.get('additions', 0)} −{f.get('deletions', 0)})")
            patch = f.get("patch") or ""
            if patch and budget > 0:
                lines.append(patch[:min(1500, budget)])
                budget -= min(1500, len(patch))
        if comments:
            lines += ["", "Comments:"] + [f"- {c['user']['login']}: {_short(c.get('body', ''), 400)}" for c in comments[-10:]]
        return "\n".join(lines)

    async def gh_comment(self, repo, number, text, approved=False):
        repo, n, text = self._gh_repo(repo), round_js(num(number)), to_str(text).strip()
        if not text:
            raise RunError("A comment needs some text.")
        if not approved and not await self._allowed(["messages"], f"comment on {repo} #{n}: {_short(text, 120)}"):
            return False
        await self._gh(f"/repos/{repo}/issues/{n}/comments", "POST", {"body": text})
        self.log(f"GitHub comment on {repo} #{n}", text, "sent")
        return True

    # Telegram
    def _tg_chats(self):
        return [c for c in re.split(r"[\s,]+", os.environ.get("TELEGRAM_CHAT_ID", "")) if c]

    async def _tg(self, method, params=None, wait=0):
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        if not token:
            raise RunError(f"Telegram needs a bot: set TELEGRAM_BOT_TOKEN {WHERE_KEYS} (message @BotFather in Telegram to make one).")
        req = urllib.request.Request(f"{TELEGRAM_API}/bot{token}/{method}", data=json.dumps(params or {}).encode(),
                                     headers={"Content-Type": "application/json"})

        def go():
            try:
                with urllib.request.urlopen(req, timeout=wait + 20) as r:
                    data = json.loads(r.read())
            except urllib.error.HTTPError as e:
                try:
                    data = json.loads(e.read())
                except ValueError:
                    data = {"description": f"Telegram answered {e.code}"}
            except urllib.error.URLError as e:
                raise RunError(f"Couldn't reach Telegram ({e.reason}).") from None
            if not data.get("ok"):
                raise RunError("Telegram: " + to_str(data.get("description") or "it said no") + ".")
            return data.get("result")
        return await asyncio.to_thread(go)

    def _tg_load(self):
        try:
            with open(TELEGRAM_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {"offset": 0, "messages": []}

    async def tg_fetch(self, wait=0):
        """Collects new messages to the bot, keeps those from your chats (TELEGRAM_CHAT_ID), and gives back the new ones.
        One at a time: two scripts fetching at once would read the same messages twice, or lose one."""
        async with self._tg_lock:
            return await self._tg_fetch(wait)

    async def _tg_fetch(self, wait):
        offset = self._tg_load().get("offset", 0)
        updates = await self._tg("getUpdates", {"offset": offset, "timeout": wait,
                                                "allowed_updates": ["message", "channel_post"]}, wait)
        mine, new, top = self._tg_chats(), [], offset
        for u in updates or []:
            top = max(top, u["update_id"] + 1)
            m = u.get("message") or u.get("channel_post") or {}
            if "text" not in m and "caption" not in m:
                continue
            chat = m.get("chat", {})
            if str(chat.get("id")) not in mine:
                print(f"  (A Telegram message from chat {chat.get('id')} was ignored. To let this program use that chat, "
                      f"set TELEGRAM_CHAT_ID = {chat.get('id')} {WHERE_KEYS}.)", flush=True)
                continue
            who = m.get("from", {})
            new.append({"text": m.get("text") or m.get("caption", ""), "sender": " ".join(x for x in (who.get("first_name"), who.get("last_name")) if x)
                        or chat.get("title", ""), "chat": str(chat.get("id")), "chat_name": chat.get("title") or chat.get("first_name", ""),
                        "date": m.get("date", 0), "update_id": u["update_id"]})
        # Another program sharing this bot may have saved messages while this one waited on Telegram. Read the file again
        # under the lock and add to what's there, skipping any message it already has, instead of writing over it.
        try:
            with _locked(TELEGRAM_FILE):
                store = self._tg_load()
                have = {m.get("update_id") for m in store.get("messages", []) if m.get("update_id") is not None}
                fresh = [m for m in new if m["update_id"] not in have]
                store["offset"] = max(store.get("offset", 0), top)
                store["messages"] = (store.get("messages", []) + fresh)[-2000:]
                _write_json(TELEGRAM_FILE, store)
            new = fresh
        except OSError:
            pass
        return new

    async def tg_search(self, text="", limit=20):
        if not getattr(self, "_tg_polling", False):
            await self.tg_fetch()
        words = to_str(text).lower().split()
        found = [m for m in sorted(self._tg_load().get("messages", []), key=lambda m: -m.get("date", 0)) if all(w in m["text"].lower() for w in words)][:max(1, min(50, round_js(num(limit)) or 20))]
        return "\n".join(f"{_when(datetime.datetime.fromtimestamp(m['date']))} · {m['sender']}: {_short(m['text'], 300)}" for m in found) \
            or ("No messages found" + (f" with “{text}”" if words else "") + ". The bot only sees messages sent to it, from the chats in TELEGRAM_CHAT_ID.")

    async def tg_send(self, text, chat="", approved=False):
        text = to_str(text).strip()
        if not text:
            raise RunError("A Telegram message needs some text.")
        trig = MESSAGE_VALUE.get()
        chat = to_str(chat).strip() or (trig.get("chat") if isinstance(trig, dict) and trig.get("chat") else "") or next(iter(self._tg_chats()), "")
        if not chat:
            raise RunError(f"Telegram needs a chat to send to: set TELEGRAM_CHAT_ID {WHERE_KEYS}. "
                           "Send your bot a message first; the program then says which chat it came from.")
        if not approved and not await self._allowed(["messages"], f"send a Telegram message: {_short(text, 120)}"):
            return False
        for i in range(0, len(text), 4000):
            await self._tg("sendMessage", {"chat_id": chat, "text": text[i:i + 4000]})
        self.log("Telegram message sent", text, "sent")
        return True

    @staticmethod
    def telegram_message(part="text"):
        v = MESSAGE_VALUE.get()
        if not isinstance(v, dict) or "text" not in v:
            return ""
        return {"text": v["text"], "sender": v.get("sender", ""), "chat": v.get("chat_name") or v.get("chat", "")}.get(part, v["text"])

    async def _tg_watch(self, watches):
        """Long-polls Telegram and starts 'when a Telegram message arrives' scripts."""
        self._tg_polling = True
        started, busy = time.time() - 60, None
        while True:
            try:
                new = await self.tg_fetch(wait=25)
            except RunError as e:
                print("  (Telegram check failed: " + str(e) + ")", flush=True)
                await asyncio.sleep(15)
                continue
            for m in new:
                if m["date"] < started:
                    continue  # sent while the program wasn't running: kept for searching, not acted on
                for contains, fn in watches:
                    if contains.strip().lower() not in ("", "anything") and contains.strip().lower() not in m["text"].lower():
                        continue
                    if busy and not busy.done():
                        self.start_script(fn, m)
                    else:
                        busy = asyncio.ensure_future(self.run([(fn, m)], "Telegram message"))

    # Discord and Slack: the same shape for both. Only the channels in the settings are read or posted in.
    CHATS = {"discord": {"name": "Discord", "token": "DISCORD_BOT_TOKEN", "channels": "DISCORD_CHANNEL_ID", "limit": 2000,
                         "make": "a bot in the Discord Developer Portal (Applications, your app, Bot), with the Message Content intent on"},
             "slack": {"name": "Slack", "token": "SLACK_BOT_TOKEN", "channels": "SLACK_CHANNEL_ID", "limit": 3500,
                       "make": "a Slack app (api.slack.com/apps) with a bot token and the channels:history and chat:write scopes"}}

    def _chat_channels(self, service):
        return [c for c in re.split(r"[\s,]+", os.environ.get(self.CHATS[service]["channels"], "")) if c]

    async def _chat_api(self, service, method, path, body=None, query=None):
        c = self.CHATS[service]
        token = os.environ.get(c["token"], "").strip()
        if not token:
            raise RunError(f"{c['name']} needs {c['token']} {WHERE_KEYS}: make {c['make']}.")
        base = DISCORD_API if service == "discord" else SLACK_API
        url = base + path + ("?" + urllib.parse.urlencode(query) if query else "")
        req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": ("Bot " if service == "discord" else "Bearer ") + token,
                                              "Content-Type": "application/json; charset=utf-8", "User-Agent": "SecondThought (+https://claude.ai)"})

        def go():
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = json.loads(r.read() or b"null")
            except urllib.error.HTTPError as e:
                why = {401: f"the bot token was refused. Check {c['token']}", 403: "the bot isn't allowed in that channel. Add it to the channel and give it permission to read and send messages",
                       404: "there's no such channel, or the bot can't see it", 429: "it's asking the program to slow down. Try again in a minute"}.get(e.code, f"it answered {e.code}")
                raise RunError(f"{c['name']}: {why}.") from None
            except urllib.error.URLError as e:
                raise RunError(f"Couldn't reach {c['name']} ({e.reason}).") from None
            if service == "slack" and isinstance(data, dict) and not data.get("ok"):
                err = to_str(data.get("error") or "it said no")
                why = {"not_in_channel": "the bot isn't in that channel. Invite it with /invite", "channel_not_found": "there's no such channel, or the bot can't see it",
                       "invalid_auth": f"the bot token was refused. Check {c['token']}", "missing_scope": "the app needs more scopes (channels:history and chat:write)"}.get(err, err)
                raise RunError(f"Slack: {why}.")
            return data
        return await asyncio.to_thread(go)

    async def _chat_read(self, service, channel, after=None, limit=50):
        """(messages, newest id): messages in one channel, oldest first, as records (text, sender, channel, id), skipping
        bots, this one included. The newest id counts every message, bots too, so a listener knows where it got to."""
        out, newest = [], after
        if service == "discord":
            q = {"limit": limit, **({"after": after} if after else {})}
            raw = await self._chat_api("discord", "GET", f"/channels/{urllib.parse.quote(channel)}/messages", query=q) or []
            newest = max((m["id"] for m in raw), key=int, default=after)
            for m in sorted(raw, key=lambda x: int(x["id"])):
                a = m.get("author") or {}
                if a.get("bot") or not to_str(m.get("content")).strip():
                    continue
                out.append({"text": m["content"], "sender": a.get("global_name") or a.get("username", ""), "channel": channel, "id": m["id"],
                            "date": _parse_date(m.get("timestamp", "")) or datetime.datetime.now()})
        else:
            q = {"channel": channel, "limit": limit, **({"oldest": after} if after else {})}
            raw = [m for m in (await self._chat_api("slack", "GET", "/conversations.history", query=q) or {}).get("messages", []) if m.get("ts") != after]
            newest = max((m["ts"] for m in raw), key=float, default=after)
            for m in sorted(raw, key=lambda x: float(x["ts"])):
                if m.get("bot_id") or m.get("subtype") or not to_str(m.get("text")).strip():
                    continue
                out.append({"text": m["text"], "sender": m.get("user", ""), "channel": channel, "id": m["ts"],
                            "date": datetime.datetime.fromtimestamp(float(m["ts"]))})
        return out, newest

    def _chat_need_channels(self, service):
        chans = self._chat_channels(service)
        if not chans:
            c = self.CHATS[service]
            raise RunError(f"{c['name']} needs {c['channels']} {WHERE_KEYS}: the channels it reads and posts in (anyone can post in a "
                           f"{'server' if service == 'discord' else 'workspace'}, so only these count).")
        return chans

    async def chat_search(self, service, text="", limit=20):
        words, found = to_str(text).lower().split(), []
        for ch in self._chat_need_channels(service):
            found += [m for m in (await self._chat_read(service, ch, limit=100))[0] if all(w in m["text"].lower() for w in words)]
        found.sort(key=lambda m: m["date"], reverse=True)
        name = self.CHATS[service]["name"]
        return "\n".join(f"{_when(m['date'])} · {m['sender']} in {m['channel']}: {_short(m['text'], 300)}" for m in found[:max(1, min(50, round_js(num(limit)) or 20))]) \
            or (f"No {name} messages found" + (f" with “{text}”" if words else "") + f". Only the channels in {self.CHATS[service]['channels']} are read.")

    async def chat_send(self, service, text, channel="", approved=False):
        c = self.CHATS[service]
        text = to_str(text).strip()
        if not text:
            raise RunError(f"A {c['name']} message needs some text.")
        mine = self._chat_need_channels(service)
        trig = MESSAGE_VALUE.get()
        channel = to_str(channel).strip() or (trig.get("channel") if isinstance(trig, dict) and trig.get("service") == service else "") or mine[0]
        if channel not in mine:
            raise RunError(f"{c['name']}: channel {channel} isn't in {c['channels']}, so nothing is sent there.")
        if not approved and not await self._allowed(["messages"], f"send a {c['name']} message: {_short(text, 120)}"):
            return False
        for i in range(0, len(text), c["limit"]):
            part = text[i:i + c["limit"]]
            if service == "discord":
                await self._chat_api("discord", "POST", f"/channels/{urllib.parse.quote(channel)}/messages", {"content": part, "allowed_mentions": {"parse": []}})
            else:
                await self._chat_api("slack", "POST", "/chat.postMessage", {"channel": channel, "text": part})
        self.log(f"{c['name']} message sent", text, "sent")
        return True

    async def _listen_chat(self, service, items):
        """'when a Discord/Slack message arrives': checks each channel every 10 seconds. Messages already there at the start don't count."""
        chans = self._chat_need_channels(service)
        last = {ch: (await self._chat_read(service, ch, limit=1))[1] for ch in chans}
        if service == "slack":  # Slack's 'oldest' is a time; start from now if the channel was empty
            last = {ch: v or f"{time.time():.6f}" for ch, v in last.items()}
        print(f"Listening for {self.CHATS[service]['name']} messages in " + ", ".join(chans) + ".", flush=True)
        while True:
            await asyncio.sleep(self._poll(10))
            for ch in chans:
                try:
                    new, last[ch] = await self._chat_read(service, ch, after=last[ch])
                except RunError as e:
                    print(f"  ({self.CHATS[service]['name']} check failed: {e})", flush=True)
                    continue
                for m in new:
                    rec = {"service": service, "text": m["text"], "sender": m["sender"], "channel": ch, "id": m["id"]}
                    for contains, fn in items:
                        want = to_str(contains).strip().lower()
                        if want in ("", "anything") or want in m["text"].lower():
                            self._fire(fn, dict(rec), f"{self.CHATS[service]['name']} message")

    async def _listen_discord(self, items):
        await self._listen_chat("discord", items)

    async def _listen_slack(self, items):
        await self._listen_chat("slack", items)

    # Email
    MAIL_SERVERS = {"gmail.com": ("imap.gmail.com", "smtp.gmail.com", 465), "googlemail.com": ("imap.gmail.com", "smtp.gmail.com", 465),
                    "icloud.com": ("imap.mail.me.com", "smtp.mail.me.com", 587), "me.com": ("imap.mail.me.com", "smtp.mail.me.com", 587),
                    "yahoo.com": ("imap.mail.yahoo.com", "smtp.mail.yahoo.com", 465), "yahoo.co.uk": ("imap.mail.yahoo.com", "smtp.mail.yahoo.com", 465),
                    "fastmail.com": ("imap.fastmail.com", "smtp.fastmail.com", 465)}

    def _mail(self):
        addr, pw = os.environ.get("EMAIL_ADDRESS", "").strip(), os.environ.get("EMAIL_PASSWORD", "")
        if not addr or not pw:
            raise RunError(f"Email needs EMAIL_ADDRESS and EMAIL_PASSWORD {WHERE_KEYS}. Use an app password, not your normal one.")
        guess = self.MAIL_SERVERS.get(addr.rsplit("@", 1)[-1].lower(), (None, None, 465))
        imap = os.environ.get("EMAIL_IMAP_HOST") or guess[0]
        smtp = os.environ.get("EMAIL_SMTP_HOST") or guess[1]
        if not imap or not smtp:
            raise RunError(f"Set EMAIL_IMAP_HOST and EMAIL_SMTP_HOST {WHERE_KEYS}: your email provider's help pages list them.")
        secure = os.environ.get("EMAIL_SSL", "yes").strip().lower() not in ("0", "no", "false", "off")
        return {"addr": addr, "pw": pw, "imap": imap, "imap_port": int(os.environ.get("EMAIL_IMAP_PORT") or (993 if secure else 143)),
                "smtp": smtp, "smtp_port": int(os.environ.get("EMAIL_SMTP_PORT") or guess[2]), "ssl": secure}

    def _imap(self, c):
        import imaplib
        try:
            m = imaplib.IMAP4_SSL(c["imap"], c["imap_port"], timeout=30) if c["ssl"] else imaplib.IMAP4(c["imap"], c["imap_port"], timeout=30)
            m.login(c["addr"], c["pw"])
        except imaplib.IMAP4.error as e:
            raise RunError(f"The email server refused the login ({_short(e, 120)}). Check EMAIL_PASSWORD is an app password.") from None
        except OSError as e:
            raise RunError(f"Couldn't reach the email server {c['imap']} ({e}).") from None
        return m

    @staticmethod
    def _mail_text(msg, limit):
        """The readable text of an email: the plain part, or the HTML part's words."""
        plain = html = None
        for part in msg.walk():
            if part.get_content_maintype() == "multipart" or part.get_filename():
                continue
            if part.get_content_type() in ("text/plain", "text/html"):
                try:
                    body = part.get_content()
                except (LookupError, ValueError):
                    body = part.get_payload(decode=True).decode("utf-8", "replace") if part.get_payload(decode=True) else ""
                if part.get_content_type() == "text/plain" and plain is None:
                    plain = body
                elif html is None:
                    html = page_text(body, "text/html")[1]
        text = (plain if plain and plain.strip() else html) or ""
        return re.sub(r"\n{3,}", "\n\n", text).strip()[:limit]

    @staticmethod
    def _mail_head(msg, uid):
        import email.utils
        d = _parse_date(msg.get("Date", ""))
        who = email.utils.parseaddr(str(msg.get("From", "")))
        return f"id {uid} · {_when(d) if d else '?'} · From: {who[0] or who[1]}" + (f" <{who[1]}>" if who[0] else "") + f" · Subject: {msg.get('Subject', '(no subject)')}"

    async def email_search(self, query="", days=7):
        import email
        import email.policy
        c, query, days = self._mail(), to_str(query).strip(), max(1, min(365, round_js(num(days)) or 7))

        def go():
            m = self._imap(c)
            try:
                m.select("INBOX", readonly=True)
                since = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%d-%b-%Y")
                if query and not query.isascii():
                    m.literal = query.encode("utf-8")
                    typ, data = m.uid("SEARCH", "CHARSET", "UTF-8", "SINCE", since, "TEXT")
                elif query:
                    typ, data = m.uid("SEARCH", "SINCE", since, "TEXT", '"' + query.replace('"', "") + '"')
                else:
                    typ, data = m.uid("SEARCH", "SINCE", since)
                uids = (data[0] or b"").split()[-20:][::-1]
                out = []
                for uid in uids:
                    typ, got = m.uid("FETCH", uid, "(BODY.PEEK[]<0.20000>)")
                    raw = next((x[1] for x in got if isinstance(x, tuple)), b"")
                    msg = email.message_from_bytes(raw, policy=email.policy.default)
                    out.append(self._mail_head(msg, uid.decode()) + "\n  " + _short(self._mail_text(msg, 600), 200))
                return out
            finally:
                try:
                    m.logout()
                except Exception:  # noqa: BLE001
                    pass
        found = await asyncio.to_thread(go)
        return "\n".join(found) or f"No emails in the last {days} days" + (f" with “{query}”." if query else ".")

    async def email_read(self, uid):
        import email
        import email.policy
        c, uid = self._mail(), to_str(uid).strip().removeprefix("id").strip()
        if not uid.isdigit():
            raise RunError("read_email needs an email's id number, from search_email.")

        def go():
            m = self._imap(c)
            try:
                m.select("INBOX", readonly=True)
                typ, got = m.uid("FETCH", uid, "(BODY.PEEK[])")
                raw = next((x[1] for x in got if isinstance(x, tuple)), None)
                if not raw:
                    raise RunError(f"There's no email with id {uid}.")
                msg = email.message_from_bytes(raw, policy=email.policy.default)
                files = [p.get_filename() for p in msg.walk() if p.get_filename()]
                return (self._mail_head(msg, uid) + (f"\nTo: {msg.get('To', '')}" if msg.get("To") else "") + "\n\n" + self._mail_text(msg, 15000)
                        + (f"\n\nAttachments: {', '.join(files)}" if files else ""))
            finally:
                try:
                    m.logout()
                except Exception:  # noqa: BLE001
                    pass
        return await asyncio.to_thread(go)

    async def email_send(self, to, subject, body, approved=False):
        import smtplib
        from email.message import EmailMessage
        to, subject, body = to_str(to).strip(), to_str(subject).strip(), to_str(body)
        addrs = [a.strip() for a in re.split(r"[,;]", to) if a.strip()]
        if not addrs or not all(re.fullmatch(r"[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+", a) for a in addrs):
            raise RunError(f"“{to}” isn't an email address.")
        c = self._mail()
        if not approved and not await self._allowed(["messages"], f"send an email to {to}: {subject}"):
            return False
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = c["addr"], ", ".join(addrs), subject or "(no subject)"
        msg.set_content(body)

        def go():
            try:
                if c["ssl"] and c["smtp_port"] == 465:
                    s_ = smtplib.SMTP_SSL(c["smtp"], 465, timeout=30)
                else:
                    s_ = smtplib.SMTP(c["smtp"], c["smtp_port"], timeout=30)
                    if c["ssl"]:
                        s_.starttls()
                with s_:
                    s_.login(c["addr"], c["pw"])
                    s_.send_message(msg)
            except smtplib.SMTPException as e:
                raise RunError(f"The email couldn't be sent ({_short(e, 160)}).") from None
            except OSError as e:
                raise RunError(f"Couldn't reach the email server {c['smtp']} ({e}).") from None
        await asyncio.to_thread(go)
        self.log(f"Email sent to {to}", f"Subject: {subject}\n\n{_short(body, 600)}", "sent")
        return True

    # Calendar
    async def _calendar(self, start, end):
        urls = [u for u in re.split(r"\s+", os.environ.get("CALENDAR_URL", "").strip()) if u]
        if not urls:
            raise RunError(f"The calendar needs CALENDAR_URL {WHERE_KEYS}: your calendar's private iCal address.")
        out = []
        for u in urls:
            ctype, data = await asyncio.to_thread(get_url, u, True, "The calendar", 20_000_000)
            text = _decode(data, ctype)
            if "BEGIN:VCALENDAR" not in text[:2000]:
                raise RunError("CALENDAR_URL isn't an iCal calendar address (it should end in .ics, or come from 'secret address in iCal format').")
            out += calendar_events(text, start, end)
        out.sort(key=lambda x: (x["start"], not x["all_day"]))
        return out

    async def calendar_text(self, day="today", days=7):
        start, days = parse_day(day), max(1, min(62, round_js(num(days)) or 7))
        events = await self._calendar(start, start + datetime.timedelta(days=days))
        lines, cur = [], None
        for e in events:
            d = max(e["start"], start).date()
            if d != cur:
                cur = d
                lines.append(f"{WEEKDAYS[d.weekday()]} {d:%d %b}:")
            lines.append("  " + event_line(e))
        return "\n".join(lines) or f"Nothing in the calendar for the {days} day{'s' if days != 1 else ''} from {start:%a %d %b}."

    async def calendar_records(self, days):
        start = parse_day("today")
        events = await self._calendar(start, start + datetime.timedelta(days=max(1, min(62, round_js(num(days)) or 7))))
        recs = [{"day": f"{WEEKDAYS[e['start'].weekday()]} {e['start']:%d %b}", "start": "" if e["all_day"] else f"{e['start']:%H:%M}",
                 "end": "" if e["all_day"] else f"{e['end']:%H:%M}", "title": e["title"], "location": e["location"]} for e in events]
        self.log("Calendar", "\n".join(f"{r['day']} {r['start'] or 'all day'}  {r['title']}" for r in recs) or "(nothing)", f"{len(recs)} events")
        return recs

    async def free_time(self, day="today", frm="09:00", to="17:30", minutes=60):
        start = parse_day(day)
        events = await self._calendar(start, start + datetime.timedelta(days=1))
        slots = free_slots(events, start, frm or "09:00", to or "17:30", minutes)
        head = f"{WEEKDAYS[start.weekday()]} {start:%d %b}"
        return (f"Free on {head}:\n" + "\n".join(f"  {a:%H:%M}–{b:%H:%M}" for a, b in slots)) if slots \
            else f"No free time of {round_js(num(minutes) or 30)} minutes on {head} between {frm} and {to}."

    # Homey
    # Homey Pro's local Web API: HOMEY_URL is its address on your network (a Homey Self-Hosted Server serves the same
    # API on port 4859, so add :4859; devices on a Homey Bridge show up through it), HOMEY_API_KEY a key from the Homey Web App
    # (Settings, API Keys). Give the key the permissions your program needs: devices (view, and control to switch
    # things), flows (view and start), Logic (view, and edit to set variables).
    HOMEY_SENSITIVE = {("locked", False), ("garagedoor_closed", False), ("homealarm_state", "disarmed")}

    async def _homey(self, method, path, body=None):
        url, key = os.environ.get("HOMEY_URL", "").strip().rstrip("/"), os.environ.get("HOMEY_API_KEY", "").strip()
        if not url or not key:
            raise RunError(f"Homey needs HOMEY_URL and HOMEY_API_KEY {WHERE_KEYS}. Make a key in the Homey Web App: Settings, API Keys.")
        if not re.match(r"^https?://", url):
            url = "http://" + url
        req = urllib.request.Request(url + "/api/manager" + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})

        def go():
            try:
                with urllib.request.urlopen(req, timeout=20) as r:
                    raw = r.read()
                    return json.loads(raw) if raw.strip() else None
            except urllib.error.HTTPError as e:
                why = {401: "the API key was refused. Check HOMEY_API_KEY", 403: "the API key isn't allowed to do that. Give it more permissions in the Homey Web App",
                       404: "not found"}.get(e.code, f"Homey answered {e.code}")
                raise RunError(f"Homey: {why}.") from None
            except urllib.error.URLError as e:
                hint = "" if urllib.parse.urlparse(url).port else " For a Homey Self-Hosted Server, add its port: :4859."
                raise RunError(f"Couldn't reach Homey at {url} ({e.reason}).{hint}") from None
        return await asyncio.to_thread(go)

    async def _homey_home(self):
        """Every device, with its zone's name."""
        devices = await self._homey("GET", "/devices/device/")
        try:
            zones = {k: v.get("name", "") for k, v in (await self._homey("GET", "/zones/zone/")).items()}
        except RunError:
            zones = {}
        out = []
        for d in (devices or {}).values():
            caps = {k: c.get("value") for k, c in (d.get("capabilitiesObj") or {}).items()}
            zone = d.get("zone")
            zone = zones.get(zone if isinstance(zone, str) else (zone or {}).get("id"), "") or (zone.get("name", "") if isinstance(zone, dict) else "")
            out.append({"id": d.get("id"), "name": d.get("name", ""), "zone": zone, "class": d.get("class", ""), "caps": caps})
        out.sort(key=lambda x: (x["zone"], x["name"]))
        return out

    @staticmethod
    def _homey_show(v):
        return "on" if v is True else "off" if v is False else "-" if v is None else to_str(v)

    def _homey_line(self, d):
        return f"{d['name']} ({d['zone'] or 'no zone'}, {d['class']}): " + ", ".join(f"{k}={self._homey_show(v)}" for k, v in d["caps"].items())

    async def _homey_device(self, name):
        """A device by its name (or id). An exact name wins; otherwise one device whose name contains the words."""
        name = to_str(name).strip()
        if not name:
            raise RunError("Which Homey device? Give its name, like Kitchen light.")
        home = await self._homey_home()
        exact = [d for d in home if d["name"].lower() == name.lower() or d["id"] == name]
        if exact:
            return exact[0]
        some = [d for d in home if all(w in d["name"].lower() for w in name.lower().split())]
        if len(some) == 1:
            return some[0]
        raise RunError(f"There's no Homey device called “{name}”." + (" Did you mean: " + ", ".join(d["name"] for d in some[:6]) + "?" if some else ""))

    async def homey_find(self, text="*"):
        """Records (name, zone, class, and each capability) for devices whose name, zone or class contain every word."""
        words = [w for w in to_str(text).lower().split() if w != "*"]
        found = [d for d in await self._homey_home() if all(w in f"{d['name']} {d['zone']} {d['class']}".lower() for w in words)]
        return [dict({"name": d["name"], "zone": d["zone"], "class": d["class"]}, **{k: self._homey_show(v) if isinstance(v, bool) else v for k, v in d["caps"].items()})
                for d in found]

    async def homey_find_text(self, text="*"):
        words = [w for w in to_str(text).lower().split() if w != "*"]
        found = [d for d in await self._homey_home() if all(w in f"{d['name']} {d['zone']} {d['class']}".lower() for w in words)]
        return "\n".join(self._homey_line(d) for d in found) or f"No Homey devices match “{to_str(text).strip()}”."

    async def homey_value(self, capability, device):
        d = await self._homey_device(device)
        cap = to_str(capability).strip()
        if cap not in d["caps"]:
            raise RunError(f"{d['name']} has no “{cap}”. It has: {', '.join(d['caps']) or 'nothing'}.")
        v = d["caps"][cap]
        return self._homey_show(v) if isinstance(v, bool) else v

    @staticmethod
    def _homey_value_for(old, value):
        """Turns 'on', 'yes', '50' and so on into the kind of value the capability holds."""
        v = value
        if isinstance(old, bool) or (isinstance(v, str) and v.strip().lower() in ("on", "off", "true", "false", "yes", "no")):
            if isinstance(v, str):
                t = v.strip().lower()
                if t not in ("on", "off", "true", "false", "yes", "no", "1", "0"):
                    raise RunError(f"“{value}” isn't on or off.")
                return t in ("on", "true", "yes", "1")
            return bool(v)
        if isinstance(old, (int, float)):
            if not _num_like(v):
                raise RunError(f"“{value}” isn't a number.")
            return num(v)
        return to_str(v) if not isinstance(v, (int, float, bool)) else v

    async def homey_set(self, device, capability, value, approved=False):
        d = await self._homey_device(device)
        cap = to_str(capability).strip()
        if cap not in d["caps"]:
            raise RunError(f"{d['name']} has no “{cap}”. It has: {', '.join(d['caps']) or 'nothing'}.")
        v = self._homey_value_for(d["caps"][cap], value)
        what = f"set {d['name']} {cap} to {self._homey_show(v)}"
        if (cap, v) in self.HOMEY_SENSITIVE:  # unlocking, opening and disarming always ask, unless you've just said yes to this very change
            if not approved and not await self.confirm(what + " (a safety check: unlocking, opening and disarming always ask)"):
                return False
        elif not approved and not await self._allowed(["ha"], what):
            return False
        await self._homey("PUT", f"/devices/device/{urllib.parse.quote(d['id'])}/capability/{urllib.parse.quote(cap)}", {"value": v})
        self.log("Homey: " + d["name"], f"{cap}: {self._homey_show(d['caps'][cap])} → {self._homey_show(v)}", "done")
        return True

    async def _homey_flows(self):
        flows = []
        for path, adv in (("/flow/flow/", False), ("/flow/advancedflow/", True)):
            try:
                for f in (await self._homey("GET", path) or {}).values():
                    flows.append({"id": f.get("id"), "name": f.get("name", ""), "advanced": adv, "enabled": f.get("enabled", True),
                                  "triggerable": f.get("triggerable", True)})
            except RunError:
                if not adv:
                    raise
        return flows

    async def homey_flows_text(self):
        return "\n".join(f"{f['name']}" + (" (advanced)" if f["advanced"] else "") + ("" if f["enabled"] else " (turned off)")
                         for f in sorted(await self._homey_flows(), key=lambda f: f["name"].lower())) or "No flows."

    async def homey_run_flow(self, name, approved=False):
        name = to_str(name).strip()
        flows = await self._homey_flows()
        f = next((x for x in flows if x["name"].lower() == name.lower()), None) or \
            (lambda c: c[0] if len(c) == 1 else None)([x for x in flows if name.lower() in x["name"].lower()])
        if not f:
            raise RunError(f"There's no Homey flow called “{name}”.")
        if not approved and not await self._allowed(["ha"], f"start the Homey flow “{f['name']}”"):
            return False
        await self._homey("POST", ("/flow/advancedflow/" if f["advanced"] else "/flow/flow/") + urllib.parse.quote(f["id"]) + "/trigger", {})
        self.log("Homey flow started", f["name"], "started")
        return True

    async def _homey_var(self, name):
        name = to_str(name).strip()
        vs = list((await self._homey("GET", "/logic/variable/") or {}).values())
        v = next((x for x in vs if x.get("name", "").lower() == name.lower()), None)
        if not v:
            raise RunError(f"There's no Homey variable called “{name}”." + (" Its variables are: " + ", ".join(x.get("name", "") for x in vs[:12]) if vs else ""))
        return v

    async def homey_variable(self, name):
        return (await self._homey_var(name)).get("value", "")

    async def homey_set_variable(self, name, value, approved=False):
        v = await self._homey_var(name)
        old = v.get("value")
        new = self._homey_value_for(old, value) if v.get("type") in ("boolean", "number") else to_str(value)
        if not approved and not await self._allowed(["ha"], f"set the Homey variable “{v['name']}” to {self._homey_show(new)}"):
            return False
        await self._homey("PUT", "/logic/variable/" + urllib.parse.quote(v["id"]), {"value": new})
        self.log("Homey variable " + v["name"], f"{self._homey_show(old)} → {self._homey_show(new)}", "set")
        return True

    async def _listen_homey(self, items):
        """'when Homey device … changes': checks every 10 seconds and starts the script when a value changes."""
        before = None
        print("Watching Homey devices for changes.", flush=True)
        while True:
            try:
                home = await self._homey_home()
                now = {(d["name"], k): (v, d) for d in home for k, v in d["caps"].items()}
                if before is not None:
                    for (dname, cap), (v, d) in now.items():
                        if (dname, cap) not in before or before[(dname, cap)][0] == v:
                            continue
                        old = before[(dname, cap)][0]
                        for arg, fn in items:
                            want_dev, _, want_cap = to_str(arg).partition("|")
                            want_cap = want_cap.strip().lower()
                            if want_dev.strip().lower() not in (dname.lower(), d["id"]) or want_cap not in ("", "anything", cap.lower()):
                                continue
                            rec = {"device": dname, "zone": d["zone"], "capability": cap, "from": self._homey_show(old) if isinstance(old, bool) else old,
                                   "to": self._homey_show(v) if isinstance(v, bool) else v,
                                   "text": f"{dname} {cap}: {self._homey_show(old)} → {self._homey_show(v)}"}
                            self._fire(fn, rec, f"Homey: {dname} {cap}")
                before = now
            except RunError as e:
                print(f"  (Homey check failed: {e})", flush=True)
            await asyncio.sleep(self._poll(10))

    # MQTT
    def _mqtt_new(self, on_message=None, topics=()):
        """A connected MQTT client, running in the background. Subscribes (again after a reconnect) to these topics."""
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            raise RunError("MQTT needs the paho-mqtt package: pip install paho-mqtt") from None
        host = os.environ.get("MQTT_HOST", "").strip()
        if not host:
            raise RunError(f"MQTT needs MQTT_HOST {WHERE_KEYS}: your broker's address, like homeassistant.local.")
        tls = os.environ.get("MQTT_TLS", "").strip().lower() in ("1", "yes", "true", "on")
        port = int(os.environ.get("MQTT_PORT") or (8883 if tls else 1883))
        c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if os.environ.get("MQTT_USERNAME"):
            c.username_pw_set(os.environ["MQTT_USERNAME"], os.environ.get("MQTT_PASSWORD") or None)
        if tls:
            c.tls_set()
        ready, result = threading.Event(), {}

        def on_connect(client, userdata, flags, reason_code, properties):
            result["rc"] = reason_code
            if not reason_code.is_failure:
                for t in topics:
                    client.subscribe(t, qos=0)
            ready.set()
        c.on_connect = on_connect
        if on_message:
            c.on_message = on_message
        try:
            c.connect(host, port, keepalive=60)
        except OSError as e:
            raise RunError(f"Couldn't reach the MQTT broker at {host}:{port} ({e}).") from None
        c.loop_start()
        if not ready.wait(10) or result["rc"].is_failure:
            c.loop_stop()
            raise RunError(f"The MQTT broker at {host}:{port} " + (f"refused the connection ({result['rc']}). Check MQTT_USERNAME and MQTT_PASSWORD."
                                                                   if "rc" in result else "didn't answer."))
        return c

    @staticmethod
    def _mqtt_payload(topic, raw):
        """An MQTT message as a record: its topic and text, plus the fields of a JSON message (like zigbee2mqtt's)."""
        text = raw.decode("utf-8", "replace") if isinstance(raw, (bytes, bytearray)) else to_str(raw)
        rec = {"topic": topic, "text": text}
        try:
            j = json.loads(text)
        except ValueError:
            j = None
        if isinstance(j, dict):
            for k, v in j.items():
                rec.setdefault(str(k), json.dumps(v) if isinstance(v, (dict, list)) else v)
        return rec

    @staticmethod
    def _mqtt_topic(topic, publishing=False):
        topic = to_str(topic).strip()
        if not topic:
            raise RunError("MQTT needs a topic, like home/kitchen/temperature.")
        if publishing and ("+" in topic or "#" in topic):
            raise RunError("You can't publish to a topic with + or # in it: those only work for listening.")
        return topic

    async def mqtt_read(self, topic, wait=2.0):
        """The latest messages on a topic (+ and # allowed): {topic: text}. Retained messages arrive straight away."""
        topic, got = self._mqtt_topic(topic), {}

        def on_message(client, userdata, msg):
            if len(got) < 200:
                got[msg.topic] = self._mqtt_payload(msg.topic, msg.payload)["text"]
        c = await asyncio.to_thread(self._mqtt_new, on_message, [topic])
        try:
            await asyncio.sleep(wait)
        finally:
            c.loop_stop()
            c.disconnect()
        return got

    async def mqtt_value(self, topic):
        """For the 'latest MQTT message' block: the text, or a record of topic -> text for a topic with + or #."""
        got = await self.mqtt_read(topic)
        topic = to_str(topic).strip()
        if "+" not in topic and "#" not in topic:
            v = got.get(topic, "")
            self.log("MQTT " + topic, v or "(no message yet: only messages the broker keeps show up straight away)", "read")
            return v
        self.log("MQTT " + topic, "\n".join(f"{k}: {_short(v, 80)}" for k, v in sorted(got.items())) or "(nothing)", f"{len(got)} topics")
        return got

    async def mqtt_publish(self, topic, text, retain=False, approved=False):
        topic, text = self._mqtt_topic(topic, True), to_str(text)
        if not approved and not await self._allowed(["ha", "messages"], f"publish to MQTT {topic}: {_short(text, 120)}"):
            return False
        c = await asyncio.to_thread(self._mqtt_new)
        try:
            info = c.publish(topic, text, qos=1, retain=bool(retain))
            await asyncio.to_thread(info.wait_for_publish, 10)
        finally:
            c.loop_stop()
            c.disconnect()
        self.log(f"MQTT → {topic}", text + ("  (kept by the broker)" if retain else ""), "published")
        return True

    # ----- Listeners: scripts that start when something arrives -----
    # Each 'when …' block below runs while the program runs on schedule (run-on-schedule, or --schedule). What arrived is
    # a record; 'what arrived' gives one of its fields, and every record has a 'text' field that sums it up.
    LISTEN_NAMES = {"homey": "Homey", "mqtt": "MQTT", "webhook": "Web request", "email": "Email", "feed": "News feed", "folder": "Folder",
                    "github": "GitHub", "calendar": "Calendar", "discord": "Discord", "slack": "Slack", "page": "Web page", "ha_event": "Home Assistant events"}

    @staticmethod
    def event(key="text"):
        v = MESSAGE_VALUE.get()
        key = to_str(key).strip()
        if not isinstance(v, dict):
            return v if key in ("", "text", "all") else ""
        return dict(v) if key in ("", "all") else v.get(key, "")

    @staticmethod
    def _poll(seconds):
        """How often a listener checks. RB_POLL_SECONDS (the tests use it) makes every listener check that often."""
        try:
            return max(0.2, float(os.environ["RB_POLL_SECONDS"])) if os.environ.get("RB_POLL_SECONDS") else seconds
        except ValueError:
            return seconds

    def _fire(self, fn, payload, label):
        busy = getattr(self, "_listen_busy", None)
        if busy and not busy.done():
            self.start_script(fn, payload)
        else:
            self._listen_busy = asyncio.ensure_future(self.run([(fn, payload)], label))

    async def _listen(self, listeners):
        groups = {}
        for kind, arg, fn in listeners:
            groups.setdefault(kind, []).append((arg, fn))
        for kind, items in groups.items():
            asyncio.ensure_future(self._keep_listening(kind, items))

    async def _keep_listening(self, kind, items):
        runner = getattr(self, "_listen_" + kind)
        while True:
            try:
                await runner(items)
                return
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 - say what went wrong, then try again
                print(f"  ({self.LISTEN_NAMES.get(kind, kind)}: {self._describe(e)} Trying again in a minute.)", flush=True)
                await asyncio.sleep(self._poll(60))

    async def _listen_mqtt(self, items):
        import paho.mqtt.client as mqtt
        loop = asyncio.get_running_loop()

        def on_message(client, userdata, msg):
            if msg.retain:
                return  # a kept message is an old value, not something that has just arrived
            payload = self._mqtt_payload(msg.topic, msg.payload)
            for sub_, fn in items:
                if mqtt.topic_matches_sub(sub_, msg.topic):
                    loop.call_soon_threadsafe(self._fire, fn, dict(payload), "MQTT " + msg.topic)
        await asyncio.to_thread(self._mqtt_new, on_message, sorted({self._mqtt_topic(t) for t, _ in items}))
        print("Listening for MQTT messages on " + ", ".join(sorted({t for t, _ in items})) + ".", flush=True)
        while True:
            await asyncio.sleep(3600)

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
            print("Web requests: " + note, flush=True)
            while True:
                await asyncio.sleep(self._poll(3600))
                print(f"Web requests, {datetime.datetime.now():%H:%M}: still not listening. To turn them on, " + note, flush=True)
        srv = ThreadingHTTPServer((os.environ.get("WEBHOOK_HOST", "0.0.0.0"), port), Hook)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        print(f"Listening for web requests on port {port}: " + ", ".join(f"http://<this computer>:{port}/{p_}?key=…" for p_ in paths) + ".", flush=True)
        while True:
            await asyncio.sleep(3600)

    def _mail_new(self, c, last):
        """Emails that arrived since the last check: (newest id, [records])."""
        import email
        import email.policy
        import email.utils
        m = self._imap(c)
        try:
            m.select("INBOX", readonly=True)
            if last is None:
                typ, data = m.uid("SEARCH", "ALL")
                uids = [int(x) for x in (data[0] or b"").split()]
                return (max(uids) if uids else 0), []
            typ, data = m.uid("SEARCH", "UID", f"{last + 1}:*")
            uids = sorted(int(x) for x in (data[0] or b"").split() if int(x) > last)
            out = []
            for uid in uids[:20]:
                typ, got = m.uid("FETCH", str(uid), "(BODY.PEEK[]<0.30000>)")
                raw = next((x[1] for x in got if isinstance(x, tuple)), b"")
                msg = email.message_from_bytes(raw, policy=email.policy.default)
                who = email.utils.parseaddr(str(msg.get("From", "")))
                body = self._mail_text(msg, 8000)
                sender = f"{who[0]} <{who[1]}>" if who[0] else who[1]
                out.append({"id": str(uid), "from": sender, "subject": str(msg.get("Subject", "")), "body": body,
                            "text": f"From: {sender}\nSubject: {msg.get('Subject', '')}\n\n{body[:3000]}"})
            return (max(uids) if uids else last), out
        finally:
            try:
                m.logout()
            except Exception:  # noqa: BLE001
                pass

    async def _listen_email(self, items):
        c, last = self._mail(), None
        print("Checking for new email.", flush=True)
        while True:
            try:
                last, new = await asyncio.to_thread(self._mail_new, c, last)
                for rec in new:
                    hay = (rec["from"] + " " + rec["subject"] + " " + rec["body"]).lower()
                    for contains, fn in items:
                        want = to_str(contains).strip().lower()
                        if want in ("", "anything") or want in hay:
                            self._fire(fn, dict(rec), "New email: " + _short(rec["subject"], 40))
            except RunError as e:
                print(f"  (Email check failed: {e})", flush=True)
            await asyncio.sleep(self._poll(120))

    async def _listen_feed(self, items):
        seen = {}
        while True:
            for url, fn in items:
                try:
                    got = await self.feed_items(url, 30, trusted=True)
                except RunError as e:
                    print(f"  (Feed check failed: {e})", flush=True)
                    continue
                keys = {i["link"] or i["title"] for i in got}
                if url in seen:
                    for i in reversed(got):  # oldest first
                        if (i["link"] or i["title"]) not in seen[url]:
                            rec = {"feed": i["feed"], "title": i["title"], "link": i["link"], "date": _when(i["date"]) if i["date"] else "",
                                   "summary": i["summary"], "text": f"{i['title']}\n{i['summary']}\n{i['link']}".strip()}
                            self._fire(fn, rec, "New in " + _short(i["feed"], 40))
                    seen[url] |= keys
                else:
                    seen[url] = keys
            await asyncio.sleep(self._poll(900))

    async def _listen_folder(self, items):
        base = os.path.dirname(os.path.abspath(sys.argv[0]))
        folders = []
        for d, fn in items:
            d = os.path.expanduser(to_str(d).strip() or "inbox")
            d = d if os.path.isabs(d) else os.path.join(base, d)
            os.makedirs(d, exist_ok=True)
            folders.append((d, fn))
        known, waiting = {d: set(os.listdir(d)) for d, _ in folders}, {}
        print("Watching for new files in " + ", ".join(d for d, _ in folders) + ".", flush=True)
        while True:
            await asyncio.sleep(self._poll(5))
            for d, fn in folders:
                try:
                    names = set(os.listdir(d))
                except OSError:
                    continue
                for n in sorted(names - known[d]):
                    path = os.path.join(d, n)
                    if n.startswith((".", "~")) or n.endswith((".tmp", ".part", ".crdownload")) or not os.path.isfile(path):
                        continue
                    size = os.path.getsize(path)
                    if waiting.get(path) != size:  # still being written: wait until its size stops changing
                        waiting[path] = size
                        continue
                    waiting.pop(path, None)
                    known[d].add(n)
                    try:
                        text = read_text_file(path)[:100000] if size <= 25 * 1024 * 1024 else ""
                    except Exception:  # noqa: BLE001 - a picture or other file: no text, but the script still runs
                        text = ""
                    self._fire(fn, {"name": n, "path": path, "size": size, "text": text}, "New file: " + n)
                known[d] &= names

    async def _listen_github(self, items):
        seen = None
        while True:
            try:
                data = await self._gh("/search/issues?per_page=50&q=" + urllib.parse.quote("is:pr is:open review-requested:@me archived:false"))
                now = {}
                for r in data.get("items", []):
                    repo = r.get("repository_url", "").split("/repos/", 1)[-1]
                    now[f"{repo}#{r['number']}"] = {"repo": repo, "number": r["number"], "title": r["title"], "user": r["user"]["login"],
                                                     "link": r.get("html_url", ""), "text": f"{repo} #{r['number']}: {r['title']} (by {r['user']['login']})"}
                if seen is not None:
                    for k, rec in now.items():
                        if k not in seen:
                            for _, fn in items:
                                self._fire(fn, dict(rec), "Review requested: " + k)
                seen = set(now)
            except RunError as e:
                print(f"  (GitHub check failed: {e})", flush=True)
            await asyncio.sleep(self._poll(300))

    async def _listen_calendar(self, items):
        fired = set()
        while True:
            try:
                now = datetime.datetime.now()
                ahead = max(max(0, round_js(num(a))) for a, _ in items)
                for e in await self._calendar(now, now + datetime.timedelta(minutes=ahead + 1)):
                    mins = (e["start"] - now).total_seconds() / 60
                    if e["all_day"] or mins < 0:
                        continue
                    for a, fn in items:
                        key = (e["title"], e["start"], a)
                        if mins <= max(0, round_js(num(a))) and key not in fired:
                            fired.add(key)
                            rec = {"title": e["title"], "start": f"{e['start']:%H:%M}", "end": f"{e['end']:%H:%M}", "location": e["location"],
                                   "minutes": max(0, round_js(mins)),
                                   "text": f"{e['title']} at {e['start']:%H:%M}" + (f" ({e['location']})" if e["location"] else "")}
                            self._fire(fn, rec, "Coming up: " + e["title"])
            except RunError as e:
                print(f"  (Calendar check failed: {e})", flush=True)
            await asyncio.sleep(self._poll(60))

    # Web pages
    PAGE_LINES_AFTER = 2       # with 'only the part containing', each matching line keeps this many lines after it
    MAX_PAGE_KEEP = 200_000    # characters of each page kept to compare with next time

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
            raise RunError(f"{_short(url, 80)} isn't a web page or text ({ctype.split(';')[0] or 'unknown type'}).")
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
        print(f"Watching {url}" + (f" (the part with “{words}”)" if words else "") + f" for changes, every {every // 60} min.", flush=True)
        while True:
            try:
                title, text = await self._read_page_text(url)
                now = self.page_part(text, words).strip()[:self.MAX_PAGE_KEEP]
                if not text.strip() or (words and not now):
                    if not quiet_noted:
                        quiet_noted = True
                        print(f"  (Page watcher: {_short(url, 80)} " + ("has no readable words; it may need a browser to show them." if not text.strip()
                              else f"has nothing with “{words}” in it right now.") + " It's checked again each time.)", flush=True)
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
                        self._fire(fn, rec, "Page changed: " + _short(title or url, 40))
            except RunError as e:
                print(f"  (Page check failed: {e})", flush=True)
            await asyncio.sleep(self._poll(every))
