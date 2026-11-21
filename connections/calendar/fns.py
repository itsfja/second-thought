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
    freq, step = r.get("FREQ", ""), max(1, int(r["INTERVAL"]) if r.get("INTERVAL", "").isdigit() else 1)  # a broken one: every time (#313)
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
            except (ValueError, OverflowError):
                pass
        elif name == "EXDATE":
            for v in value.split(","):
                try:
                    cur.setdefault("EXDATE", set()).add(_ics_time(v, params)[0])
                except (ValueError, OverflowError):
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
        try:
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
        except (ValueError, OverflowError):  # a broken date or rule: that event is left out, not the whole calendar (#313)
            continue
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
            raise RunError(tr("“{hhmm}” isn't a time like 09:00.", hhmm=hhmm))
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
        raise RunError(tr("“{text}” isn't a day. Use today, tomorrow, a weekday or YYYY-MM-DD.", text=text)) from None

# Calendar: CALENDAR_URL is your calendar's private iCal address (Google Calendar: Settings, your calendar,
# "Secret address in iCal format"; Outlook: Settings, Calendar, Shared calendars, Publish; iCloud: share as public).
