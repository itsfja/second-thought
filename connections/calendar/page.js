  function parseDay(text){
    const t = str(text).trim().toLowerCase(), today = new Date(); today.setHours(0, 0, 0, 0);
    if (t === "" || t === "today") return today;
    if (t === "tomorrow") return new Date(today.getTime() + 86400000);
    const k = WEEKDAYS.map(w => w.slice(0, 3).toLowerCase()).indexOf(t.slice(0, 3));
    if (k >= 0 && WEEKDAYS.some(w => w.toLowerCase().startsWith(t)) ) { const d = new Date(today); d.setDate(d.getDate() + ((k - (today.getDay() + 6) % 7) + 7) % 7); return d; }
    const m = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(t);
    if (m) return new Date(+m[1], +m[2] - 1, +m[3]);
    fail(tr("“{text}” isn't a day. Use today, tomorrow, a weekday or YYYY-MM-DD.", { text }));
  }
  function sampleEvents(start, end){
    connNote("Calendar");
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const at = (day, hhmm) => { const d = new Date(today); d.setDate(d.getDate() + day); const [h, m] = (hhmm || "0:0").split(":").map(Number); d.setHours(h, m, 0, 0); return d; };
    return ((CONN.calendar || {}).events || []).map(e => ({ start:at(e.day, e.all_day ? "0:0" : e.start), end:e.all_day ? at(e.day + 1, "0:0") : at(e.day, e.end),
      all_day:!!e.all_day, title:e.title, location:e.location || "" })).filter(e => e.end > start && e.start < end).sort((a, b) => a.start - b.start || (b.all_day - a.all_day));
  }
  const eventLine = e => (e.all_day ? "all day" : pad2(e.start.getHours()) + ":" + pad2(e.start.getMinutes()) + "–" + pad2(e.end.getHours()) + ":" + pad2(e.end.getMinutes())) +
    "  " + e.title + (e.location ? " (" + e.location + ")" : "");
  function calendarText(day, days){
    const start = parseDay(day); days = Math.max(1, Math.min(62, Math.floor(num(days) + 0.5) || 7));
    const lines = []; let cur = null;
    sampleEvents(start, new Date(start.getTime() + days * 86400000)).forEach(e => {
      const d = e.start < start ? start : e.start, key = d.toDateString();
      if (key !== cur) { cur = key; lines.push(dayText(d) + ":"); }
      lines.push("  " + eventLine(e));
    });
    return lines.join("\n") || "Nothing in the calendar for the " + days + " day" + (days !== 1 ? "s" : "") + " from " + dayText(start) + ".";
  }
  function freeTime(day, from, to, minutes){
    const start = parseDay(day), at = hhmm => { const m = /^\s*(\d{1,2})[:.](\d{2})\s*$/.exec(str(hhmm)); if (!m || +m[1] > 24 || +m[2] > 59) fail(tr("“{hhmm}” isn't a time like 09:00.", { hhmm })); return new Date(start.getTime() + (+m[1] * 60 + +m[2]) * 60000); };
    const a = at(from || "09:00"), b = at(to || "17:30"), need = Math.max(1, Math.floor(num(minutes) + 0.5) || 30) * 60000;
    const busy = sampleEvents(start, new Date(start.getTime() + 86400000)).filter(e => !e.all_day && e.end > a && e.start < b).map(e => [Math.max(e.start, a), Math.min(e.end, b)]).sort((x, y) => x[0] - y[0]);
    const free = []; let t = a.getTime();
    busy.forEach(([s0, e0]) => { if (s0 > t) free.push([t, s0]); t = Math.max(t, e0); });
    if (b.getTime() > t) free.push([t, b.getTime()]);
    const hm = ms => { const d = new Date(ms); return pad2(d.getHours()) + ":" + pad2(d.getMinutes()); };
    const slots = free.filter(([x, y]) => y - x >= need);
    return slots.length ? "Free on " + dayText(start) + ":\n" + slots.map(([x, y]) => "  " + hm(x) + "–" + hm(y)).join("\n")
      : "No free time of " + (Math.floor(num(minutes) + 0.5) || 30) + " minutes on " + dayText(start) + " between " + (from || "09:00") + " and " + (to || "17:30") + ".";
  }
