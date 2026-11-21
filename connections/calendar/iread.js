      case "rb_calendar": {
        const days = Math.max(1, Math.min(62, Math.floor(num(await input(b, tc, "DAYS", 7)) + 0.5) || 7)), start = parseDay("today");
        const recs = sampleEvents(start, new Date(start.getTime() + days * 86400000)).map(e => ({ day:dayText(e.start), start:e.all_day ? "" : pad2(e.start.getHours()) + ":" + pad2(e.start.getMinutes()),
          end:e.all_day ? "" : pad2(e.end.getHours()) + ":" + pad2(e.end.getMinutes()), title:e.title, location:e.location }));
        addStep("Calendar", { mono:true, text:recs.map(r => r.day + " " + (r.start || tr("all day")) + "  " + r.title).join("\n") || tr("(nothing)") }).done(tr("{n} events", { n:recs.length }), "ok");
        return recs;
      }
