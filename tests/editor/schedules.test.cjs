// When a 'when it's' script next runs on the page, and the cron lines Save as GitHub Actions writes for it, in several
// time zones. Each time zone's tests run in a child process with TZ set, so dates are worked out as they would be there.
"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const { execFileSync } = require("child_process");
const { load, plain } = require("./page.cjs");

const hat = fields => ({ id:JSON.stringify(fields), type:fields.type || "rb_when_time", getFieldValue:k => fields[k] });

// The cron lines for 09:00 weekdays, 21:00 weekends, 08:30 every day and 00:15 weekdays.
const CRONS = {
  "UTC":              [["0 9 * * 1-5"], ["0 21 * * 0,6"], ["30 8 * * *"], ["15 0 * * 1-5"]],
  "Europe/London":    [["0 9 * * 1-5", "0 8 * * 1-5"], ["0 21 * * 0,6", "0 20 * * 0,6"], ["30 8 * * *", "30 7 * * *"], ["15 0 * * 1-5", "15 23 * * 0-4"]],
  "America/New_York": [["0 14 * * 1-5", "0 13 * * 1-5"], ["0 2 * * 0,1", "0 1 * * 0,1"], ["30 13 * * *", "30 12 * * *"], ["15 5 * * 1-5", "15 4 * * 1-5"]],
  "Asia/Tokyo":       [["0 0 * * 1-5"], ["0 12 * * 0,6"], ["30 23 * * *"], ["15 15 * * 0-4"]],
  "Asia/Kolkata":     [["30 3 * * 1-5"], ["30 15 * * 0,6"], ["0 3 * * *"], ["45 18 * * 0-4"]],
  // South of the equator, January is summer: winter's line still comes first.
  "Australia/Sydney": [["0 23 * * 0-4", "0 22 * * 0-4"], ["0 11 * * 0,6", "0 10 * * 0,6"], ["30 22 * * *", "30 21 * * *"], ["15 14 * * 0-4", "15 13 * * 0-4"]],
};
const TIMES = [[9, 0, "weekdays"], [21, 0, "weekends"], [8, 30, "every"], [0, 15, "weekdays"]];

if (process.env.ST_TZ_CHILD) {
  // In the child: print what the page makes, for the parent to check.
  const units = load().__editorUnits;
  process.stdout.write(JSON.stringify(TIMES.map(([h, m, d]) => units.actionsCrons(hat({ HOUR:h, MINUTE:m, DAYS:d })))));
} else {
  for (const [tz, want] of Object.entries(CRONS)) {
    test("GitHub Actions cron lines in " + tz, () => {
      const out = execFileSync(process.execPath, [__filename], { env:{ ...process.env, TZ:tz, ST_TZ_CHILD:"1" }, encoding:"utf8" });
      const got = JSON.parse(out);
      TIMES.forEach(([h, m, d], i) => {
        assert.deepEqual(got[i].map(c => c.cron), want[i], tz + " " + h + ":" + m + " " + d);
        assert.deepEqual(got[i].map(c => c.note), want[i].length > 1 ? ["winter", "summer"] : [""], tz + " notes");
      });
    });
  }

  test("'every' cron lines: GitHub's shortest is 5 minutes, and what doesn't divide the hour or day says so", () => {
    const units = load().__editorUnits;
    const every = (N, UNIT) => plain(units.actionsCrons(hat({ type:"rb_every", N, UNIT }))[0]);
    assert.deepEqual(every(1, "min"), { cron:"*/5 * * * *", note:"GitHub runs schedules at most every 5 minutes" });
    assert.deepEqual(every(15, "min"), { cron:"*/15 * * * *", note:"" });
    assert.deepEqual(every(7, "min"), { cron:"*/7 * * * *", note:"every 7 min, starting again each hour" });
    assert.deepEqual(every(60, "min"), { cron:"0 * * * *", note:"every hour" });
    assert.deepEqual(every(6, "h"), { cron:"0 */6 * * *", note:"" });
    assert.deepEqual(every(5, "h"), { cron:"0 */5 * * *", note:"every 5 h, starting again at midnight UTC" });
    assert.deepEqual(every(48, "h"), { cron:"0 0 * * *", note:"once a day" });
  });

  test("a 'when it's' script runs next at its time, on its days", () => {
    const units = load().__editorUnits;
    const next = (fields, now) => new Date(units.nextDueFor(hat(fields), now.getTime()));
    const fri = (h, m) => new Date(2026, 9, 30, h, m);  // Friday 30 October 2026, in this computer's time zone
    assert.deepEqual(next({ HOUR:18, MINUTE:0, DAYS:"every" }, fri(9, 0)), fri(18, 0));
    assert.deepEqual(next({ HOUR:18, MINUTE:0, DAYS:"every" }, fri(18, 5)), fri(18, 0), "up to 10 minutes late it's still due");
    assert.deepEqual(next({ HOUR:18, MINUTE:0, DAYS:"every" }, fri(18, 11)), new Date(2026, 9, 31, 18, 0), "later, it's tomorrow's");
    assert.deepEqual(next({ HOUR:9, MINUTE:0, DAYS:"weekdays" }, fri(10, 0)), new Date(2026, 10, 2, 9, 0), "Friday's has gone: Monday's");
    assert.deepEqual(next({ HOUR:9, MINUTE:0, DAYS:"weekends" }, fri(10, 0)), new Date(2026, 9, 31, 9, 0));
    assert.deepEqual(next({ HOUR:30, MINUTE:99, DAYS:"every" }, fri(10, 0)), fri(23, 59), "hours and minutes out of range are kept in it");
  });

  test("an 'every' script runs first one interval after it's armed", () => {
    const units = load().__editorUnits, now = Date.UTC(2026, 9, 30, 12, 0);
    assert.equal(units.nextDueFor(hat({ type:"rb_every", N:20, UNIT:"min" }), now), now + 20 * 60000);
    assert.equal(units.nextDueFor(hat({ type:"rb_every", N:0, UNIT:"min" }), now), now + 60000, "at least a minute");
    assert.equal(units.nextDueFor(hat({ type:"rb_every", N:30, UNIT:"h" }), now), now + 86400000, "at most a day");
  });
}
