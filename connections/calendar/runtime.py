    # Calendar
    async def _calendar(self, start, end):
        urls = [u for u in re.split(r"\s+", os.environ.get("CALENDAR_URL", "").strip()) if u]
        if not urls:
            raise RunError(tr("The calendar needs CALENDAR_URL {where_keys}: your calendar's private iCal address.", where_keys=WHERE_KEYS))
        out = []
        for u in urls:
            ctype, data = await asyncio.to_thread(get_url, u, True, "The calendar", 20_000_000)
            text = _decode(data, ctype)
            if "BEGIN:VCALENDAR" not in text[:2000]:
                raise RunError(tr("CALENDAR_URL isn't an iCal calendar address (it should end in .ics, or come from 'secret address in iCal format')."))
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
        self.log(tr("Calendar"), "\n".join(f"{r['day']} {r['start'] or tr('all day')}  {r['title']}" for r in recs) or tr("(nothing)"), tr("{recs} events", recs=len(recs)))
        return recs

    async def free_time(self, day="today", frm="09:00", to="17:30", minutes=60):
        start = parse_day(day)
        events = await self._calendar(start, start + datetime.timedelta(days=1))
        slots = free_slots(events, start, frm or "09:00", to or "17:30", minutes)
        head = f"{WEEKDAYS[start.weekday()]} {start:%d %b}"
        return (f"Free on {head}:\n" + "\n".join(f"  {a:%H:%M}–{b:%H:%M}" for a, b in slots)) if slots \
            else f"No free time of {round_js(num(minutes) or 30)} minutes on {head} between {frm} and {to}."

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
                            self._fire(fn, rec, tr("Coming up: {title}", title=e["title"]))
            except RunError as e:
                print(tr("  (Calendar check failed: {e})", e=e), flush=True)
            await asyncio.sleep(self._poll(60))

    # Web pages
    PAGE_LINES_AFTER = 2       # with 'only the part containing', each matching line keeps this many lines after it
    MAX_PAGE_KEEP = 200_000    # characters of each page kept to compare with next time
