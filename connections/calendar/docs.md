## Calendar

The **Calendar** blocks read your calendar — they never add to it:

- **calendar for the next … days** gives a list of your events as records: day, start, end, title, location.
- **when a calendar event starts in … minutes** runs a script that many minutes before each event (all-day events don't count), for reminders. **what arrived** gives title, start, end, location, minutes and text.
- **free time on …** and the agent's calendar tools give free slots between events.

On the page these blocks use a **sample calendar**: try **A reminder before each event**. The listener starts from what's new after the program starts.

**Settings:** `[calendar]` in `second-thought.ini` — `CALENDAR_URL`, your calendar's private iCal address. In Google Calendar it's under Settings, your calendar, "Secret address in iCal format"; Outlook: Settings, Calendar, Shared calendars, Publish a calendar, ICS link; iCloud: share as public. Several addresses can go on one line, separated by spaces. It can read your calendar, but not add to it. `--doctor` reads this week's events when the program can.
