"""Each key's spending on this computer, and allowances per hour, day, week and month (#269).

Part of the second_thought package. tools/sync.py joins these files, in order, into
python/runtime.py, which is what ships inside every exported program and the page.
"""
import datetime
import hashlib
import json
import os
import re
from .settings import on_github_actions
from .core import MEMORY_FILE, RunError, _locked, _number_setting, _write_json
from .providers import CURRENCY, SERVICES, amount_text, call_cost, model_label, per_dollar, service_of
from .settings import tr  # noqa: F401
# ---- package only: tools/sync.py leaves everything above this line out of python/runtime.py ----

# The ledger: what each key has spent on this computer, at list prices in US dollars, by the hour (local time). Kept next
# to memory.json, for about 40 days: enough for this month. A key is known by a hash of it, never the key itself.
SPENDING_DAYS = 40
WINDOWS = ("hourly", "daily", "weekly", "monthly")


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
    return any(allowances_for(s["name"]) for s in SERVICES)


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

    def _within_allowances(self, tiers, now=None):
        """Stops the run if the model to be called has no room left in its key's allowances, or no known price under
        one (it couldn't be counted). Backups without room or a price are left out. Gives the tiers to try."""
        now = now or datetime.datetime.now()

        def problem(tier):
            service, _ = key_id(tier)
            limits = allowances_for(service) if service else {}
            if not limits:
                return None
            if call_cost(tier, 0, 0) is None:
                return tr("Stopped: {model} has no known price, so its spending can't be counted against this key's allowances. Use a model with a price.",
                          model=model_label(tier))
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
            if not limits:
                continue
            parts = [tr("{pct}% of the {window} allowance of {amount}", pct=round(100 * self.spent(tier, w, now) * per_dollar(CURRENCY) / a),
                        window=window_word(w), amount=amount_text(a, CURRENCY)) for w, a in limits.items()]
            out.append(tr("{service} key: {list}", service=service, list=", ".join(parts)))
        return out

    @staticmethod
    def allowance_note():
        """Why allowances count less than they seem to, where that's so: on GitHub Actions the ledger starts afresh."""
        if on_github_actions() and any_allowance():
            return tr("On GitHub Actions the tally doesn't last between runs, so allowances apply to each run on its own.")
        return ""


def window_word(window):
    return {"hourly": tr("hourly"), "daily": tr("daily"), "weekly": tr("weekly"), "monthly": tr("monthly")}[window]
