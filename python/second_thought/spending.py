"""Each key's spending on this computer, and allowances per hour, day, week and month (#269).

Part of the second_thought package. tools/sync.py joins these files, in order, into
python/runtime.py, which is what ships inside every exported program and the page.
"""
import datetime
import hashlib
import sys
import json
import os
import re
from .settings import WHERE_KEYS, on_github_actions
from .core import MEMORY_FILE, RunError, _locked, _number_setting, _write_json
from .providers import CURRENCY, REPORTED, SERVICES, amount_text, call_cost, dollars, model_label, per_dollar, service_of
from .settings import tr  # noqa: F401
# ---- package only: tools/sync.py leaves everything above this line out of python/runtime.py ----

# The ledger: what each key has spent on this computer, at list prices in US dollars, by the hour (local time). Kept next
# to memory.json, for about 40 days: enough for this month. A key is known by a hash of it, never the key itself.
SPENDING_DAYS = 40
WINDOWS = ("hourly", "daily", "weekly", "monthly")


# Each service's plans (#270), as the service names them, with the monthly spend cap it publishes in US dollars (None:
# no cap, or none published). PLAN_<SERVICE> = <plan> in second-thought.ini says which an account is on. Plans and caps
# change: check them at "source" (python tools/smoke_test.py models notes them when "checked" is over 90 days old).
#   utc_months  the cap runs by the calendar month in UTC (Claude pauses at the cap until 00:00 UTC on the 1st)
#   rpm         {model: {plan: requests per minute}}: published per-minute limits, to suggest which plan a key is on
PLANS = {
    "Claude": {"plans": {"evaluation": None, "start": 500, "build": 1000, "scale": 200000, "custom": None}, "utc_months": True,
               "rpm": {"claude-sonnet-5-5": {"start": 4000, "build": 10000, "scale": 13000},
                       "claude-opus-5-5": {"start": 4000, "build": 10000, "scale": 13000},
                       "claude-haiku-4-5-20251001": {"start": 1000, "build": 5000, "scale": 10000}},
               "checked": "2026-11-03", "source": "https://platform.claude.com/docs/en/api/rate-limits"},
    "OpenAI": {"plans": {"free": 100, "build": 500, "launch": 5000, "grow": 200000},
               "checked": "2026-11-03", "source": "https://developers.openai.com/api/docs/guides/rate-limits"},
    # Gemini's tiers have billing caps and a spend limit per rolling 10 minutes, but no monthly cap and no per-model limits
    # on the page (they're in AI Studio), so naming the plan only labels the key.
    "Gemini": {"plans": {"free": None, "tier 1": None, "tier 2": None, "tier 3": None},
               "checked": "2026-11-03", "source": "https://ai.google.dev/gemini-api/docs/rate-limits"},
    "Groq": {"plans": {"free": None, "developer": None},
             "checked": "2026-11-03", "source": "https://console.groq.com/docs/rate-limits"},
}


def plan_setting(service):
    return "PLAN_" + _slug(service)


def plan_of(service):
    """The plan PLAN_<SERVICE> names, made lower case with single spaces, or ''."""
    return re.sub(r"\s+", " ", os.environ.get(plan_setting(service), "")).strip().lower()


def check_plans():
    """Stops the program, saying which names are allowed, if a PLAN_ setting names a plan its service doesn't have."""
    for service, p in PLANS.items():
        plan = plan_of(service)
        if plan and plan not in p["plans"]:
            sys.exit(tr("{setting} = {plan} isn't one of {service}'s plans. Use one of: {names}.", setting=plan_setting(service),
                        plan=plan, service=service, names=", ".join(p["plans"])))


def plan_cap(service):
    """(plan, monthly cap in US dollars, whether the month is in UTC) for the plan set for this service, or None."""
    plan = plan_of(service)
    p = PLANS.get(service)
    if not p or not plan or not p["plans"].get(plan):
        return None
    return plan, p["plans"][plan], bool(p.get("utc_months"))


def month_start(now, utc):
    """The local time this month began: in UTC for a service whose month is in UTC, else in local time."""
    if not utc:
        return window_start("monthly", now)
    offset = datetime.datetime.now().astimezone().utcoffset() or datetime.timedelta(0)
    now_utc = now - offset
    start_utc = now_utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start_utc + offset


def next_month(start):
    return (start.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)


def suggest_plan(service, reported):
    """The plan whose published per-minute requests limit matches what the service reported for this model, or ''."""
    rpm = PLANS.get(service, {}).get("rpm", {}).get(reported.get("model", ""), {})
    limit = reported.get("limits", {}).get("requests", {}).get("limit")
    hits = [plan for plan, n in rpm.items() if n == limit]
    return hits[0] if len(hits) == 1 else ""


def spending_file():
    return os.path.join(os.path.dirname(os.path.abspath(MEMORY_FILE)), ".second-thought-spending.json")


def key_id(tier):
    """(the service's name, a hash of the key this tier's calls use), or (name, None) with no key set."""
    s = service_of(tier)
    if not s:
        return None, None
    key = next((os.environ[k] for k in s.get("keys", ()) if os.environ.get(k)), "")
    if not key:
        return s["name"], None
    return s["name"], hashlib.sha256((s["name"] + "\0" + key).encode("utf-8")).hexdigest()[:16]


def window_start(window, now):
    """The local time a window began: this hour, today, this week (from Monday) or this month."""
    hour = now.replace(minute=0, second=0, microsecond=0)
    day = hour.replace(hour=0)
    return {"hourly": hour, "daily": day, "weekly": day - datetime.timedelta(days=day.weekday()),
            "monthly": day.replace(day=1)}[window]


def window_end(window, now):
    """When a window resets."""
    start = window_start(window, now)
    if window == "monthly":
        return (start.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
    return start + {"hourly": datetime.timedelta(hours=1), "daily": datetime.timedelta(days=1),
                    "weekly": datetime.timedelta(days=7)}[window]


def _slug(name):
    return re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")


def allowance(window, service):
    """The allowance in the program's currency for one window and service, or 0 for none: quota_daily_claude wins over
    quota_daily. Both are in second-thought.ini."""
    own = _number_setting(f"QUOTA_{window.upper()}_{_slug(service)}", 0, "an amount in your currency, like 1.00")
    return own or _number_setting(f"RB_QUOTA_{window.upper()}", 0, "an amount in your currency, like 1.00")


def allowances_for(service):
    """{window: amount} for the windows with an allowance for this service."""
    return {w: a for w in WINDOWS for a in [allowance(w, service)] if a}


def any_allowance():
    return any(allowances_for(s["name"]) or plan_cap(s["name"]) for s in SERVICES)


class Spending:
    """Part of Runtime: the ledger, and stopping a run before a call that a key's allowance has no room for."""

    @staticmethod
    def _ledger_read():
        try:
            with open(spending_file(), encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) and isinstance(data.get("keys"), dict) else {"keys": {}}
        except (OSError, ValueError):
            return {"keys": {}}

    def spend(self, tier, dollars, now=None):
        """Adds one call's cost to its key's hour. Spending that can't be written is lost, never the run."""
        service, kid = key_id(tier)
        if not kid or not dollars:
            return
        now = now or datetime.datetime.now()
        hour = now.strftime("%Y-%m-%dT%H")
        oldest = (now - datetime.timedelta(days=SPENDING_DAYS)).strftime("%Y-%m-%dT%H")
        path = spending_file()
        try:
            with _locked(path):
                data = self._ledger_read()
                entry = data["keys"].setdefault(kid, {"service": service, "hours": {}})
                hours = {h: v for h, v in entry.get("hours", {}).items() if h >= oldest}
                hours[hour] = hours.get(hour, 0.0) + dollars
                entry["hours"], entry["service"] = hours, service
                _write_json(path, data)
        except (OSError, RunError):
            pass

    def spent(self, tier, window, now=None):
        """What this tier's key has spent in a window, in US dollars."""
        _, kid = key_id(tier)
        if not kid:
            return 0.0
        now = now or datetime.datetime.now()
        start = window_start(window, now).strftime("%Y-%m-%dT%H")
        hours = self._ledger_read()["keys"].get(kid, {}).get("hours", {})
        return sum(v for h, v in hours.items() if h >= start)

    def spent_since(self, tier, start):
        """What this tier's key has spent since a local time, in US dollars."""
        _, kid = key_id(tier)
        if not kid:
            return 0.0
        first = start.strftime("%Y-%m-%dT%H")
        hours = self._ledger_read()["keys"].get(kid, {}).get("hours", {})
        return sum(v for h, v in hours.items() if h >= first)

    def _within_allowances(self, tiers, now=None):
        """Stops the run if the model to be called has no room left in its key's allowances, or no known price under
        one (it couldn't be counted). Backups without room or a price are left out. Gives the tiers to try."""
        now = now or datetime.datetime.now()

        def problem(tier):
            service, _ = key_id(tier)
            limits = allowances_for(service) if service else {}
            cap = plan_cap(service) if service else None
            if not limits and not cap:
                return None
            if call_cost(tier, 0, 0) is None:
                return tr("Stopped: {model} has no known price, so its spending can't be counted against this key's allowances. Use a model with a price.",
                          model=model_label(tier))
            if cap:
                plan, usd, utc = cap
                start = month_start(now, utc)
                spent = self.spent_since(tier, start)
                if spent >= usd:
                    return tr("Stopped: this {service} key has spent {spent} this month, which reaches the {plan} plan's monthly cap of {cap}. {service} stops taking calls there until {when}.",
                              service=service, spent=dollars(spent), plan=plan.title(), cap=dollars(usd),
                              when=next_month(start).strftime("%Y-%m-%d %H:%M"))
            for window, limit in limits.items():
                spent = self.spent(tier, window, now) * per_dollar(CURRENCY)
                if spent >= limit:
                    return tr("Stopped: the {window} allowance of {amount} for this {service} key has been reached ({spent} spent). It resets at {when}.",
                              window=window_word(window), amount=amount_text(limit, CURRENCY), service=service,
                              spent=amount_text(spent, CURRENCY), when=window_end(window, now).strftime("%Y-%m-%d %H:%M"))
            return None

        first = problem(tiers[0])
        if first:
            raise RunError(first)
        return [tiers[0]] + [t for t in tiers[1:] if problem(t) is None]

    def allowance_lines(self, tiers, now=None):
        """'Claude key: 34% of the daily allowance of £1.00, …' for each service among these tiers with allowances."""
        now = now or datetime.datetime.now()
        out, seen = [], set()
        for tier in tiers:
            service, kid = key_id(tier)
            if not kid or service in seen:
                continue
            seen.add(service)
            limits = allowances_for(service)
            cap = plan_cap(service)
            if cap:
                plan, usd, utc = cap
                out.append(tr("{service} ({plan} plan): {pct}% of this month's {cap} cap, counted on this computer", service=service,
                              plan=plan.title(), pct=round(100 * self.spent_since(tier, month_start(now, utc)) / usd), cap=dollars(usd)))
            if not limits:
                continue
            parts = [tr("{pct}% of the {window} allowance of {amount}", pct=round(100 * self.spent(tier, w, now) * per_dollar(CURRENCY) / a),
                        window=window_word(w), amount=amount_text(a, CURRENCY)) for w, a in limits.items()]
            out.append(tr("{service} key: {list}", service=service, list=", ".join(parts)))
        return out

    def plan_hints_once(self):
        """The plan hints for this run's services, each given once on this computer (kept in the ledger), so the end of
        a run doesn't repeat it every time. --doctor and saved logs always give them."""
        lines = []
        path = spending_file()
        try:
            with _locked(path):
                data = self._ledger_read()
                given = set(data.get("hinted", []))
                for service, r in REPORTED.items():
                    hint = suggest_plan(service, r)
                    if hint and not plan_of(service) and service not in given:
                        lines.append(tr("{service}'s limits match its {plan} plan: add {setting} = {plan_lower} {where_keys}", service=service,
                                        plan=hint.title(), setting=plan_setting(service), plan_lower=hint, where_keys=WHERE_KEYS))
                        given.add(service)
                if lines:
                    data["hinted"] = sorted(given)
                    _write_json(path, data)
        except (OSError, RunError):
            return []
        return lines

    @staticmethod
    def allowance_note():
        """Why allowances count less than they seem to, where that's so: on GitHub Actions the ledger starts afresh."""
        if on_github_actions() and any_allowance():
            return tr("On GitHub Actions the tally doesn't last between runs, so allowances apply to each run on its own.")
        return ""


LOW = 0.25  # the end of a run mentions a service's limits only when one has less than this left


def reported_lines(services=None, low_only=False, hints=True):
    """What services reported about their rate limits in this run, labelled as theirs, and a plan they seem to be on.
    low_only: only services with a limit nearly used up (for the end of a run, which shouldn't say it every time)."""
    words = {"requests": tr("requests"), "tokens": tr("tokens"), "input-tokens": tr("input tokens"), "output-tokens": tr("output tokens")}
    out = []
    for service, r in REPORTED.items():
        if services is not None and service not in services:
            continue
        if low_only and not any(v["remaining"] < LOW * v["limit"] for v in r["limits"].values()):
            continue
        parts = [tr("{pct}% of its {kind} left", pct=round(100 * v["remaining"] / v["limit"]), kind=words[k]) for k, v in r["limits"].items()]
        out.append(tr("{service} reports {list}", service=service, list=", ".join(parts)))
        hint = suggest_plan(service, r) if hints else ""
        if hint and not plan_of(service):
            out.append(tr("{service}'s limits match its {plan} plan: add {setting} = {plan_lower} {where_keys}", service=service,
                          plan=hint.title(), setting=plan_setting(service), plan_lower=hint, where_keys=WHERE_KEYS))
    return out


def usage_text(now=None):
    """What each service's keys have spent on this computer, and how that stands against each plan cap and allowance:
    the ai_usage tool's answer. Only services whose keys have spent something are listed."""
    now = now or datetime.datetime.now()
    keys = Spending._ledger_read()["keys"]
    if not keys:
        return tr("Nothing has been spent through this computer's keys yet, so there's nothing to count.")
    hours_by_service = {}
    for entry in keys.values():
        hours = hours_by_service.setdefault(entry.get("service") or "", {})
        for hour, value in (entry.get("hours") or {}).items():
            hours[hour] = hours.get(hour, 0.0) + value
    out = [tr("What each model service has been used, counted on this computer at list prices:")]
    for service in sorted(hours_by_service):
        hours = hours_by_service[service]

        def spent_since(start, hours=hours):
            first = start.strftime("%Y-%m-%dT%H")
            return sum(v for h, v in hours.items() if h >= first)

        window_words = {"hourly": tr("this hour"), "daily": tr("today"), "weekly": tr("this week"), "monthly": tr("this month")}
        parts = [tr("{window} {x}", window=window_words[w], x=dollars(spent_since(window_start(w, now)))) for w in WINDOWS]
        cap = plan_cap(service)
        if cap:
            plan, usd, utc = cap
            start = month_start(now, utc)
            month = spent_since(start)
            parts.append(tr("{pct}% of the {plan} plan's monthly cap of {cap} ({spent} spent, resets {when})",
                            pct=round(100 * month / usd), plan=plan.title(), cap=dollars(usd), spent=dollars(month),
                            when=next_month(start).strftime("%Y-%m-%d %H:%M")))
            if month > usd:
                parts.append(tr("over the cap by {x}", x=dollars(month - usd)))
        else:
            plan = plan_of(service)
            parts.append(tr("no plan set: add {setting} in {where} to count it against a cap",
                            setting=plan_setting(service), where=WHERE_KEYS) if not plan else
                         tr("the {plan} plan publishes no monthly cap", plan=plan.title()))
        for window, limit in allowances_for(service).items():
            spent = spent_since(window_start(window, now)) * per_dollar(CURRENCY)
            bit = tr("{pct}% of the {window} allowance of {amount}", pct=round(100 * spent / limit),
                     window=window_word(window), amount=amount_text(limit, CURRENCY))
            if spent > limit:
                bit += tr(", over by {x}", x=amount_text(spent - limit, CURRENCY))
            parts.append(bit)
        out.append(service + ": " + ", ".join(parts) + ".")
    out += reported_lines(sorted(hours_by_service), low_only=False, hints=False)
    return "\n".join(out)


def window_word(window):
    return {"hourly": tr("hourly"), "daily": tr("daily"), "weekly": tr("weekly"), "monthly": tr("monthly")}[window]
