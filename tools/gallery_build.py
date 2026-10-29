#!/usr/bin/env python3
"""Writes some of gallery/*.json from readable Python, so a program's blocks can be reviewed and changed as code.

Each program here is the same block file the page would save; the page and the tests treat them like any other
gallery file. Edit a program below, run this, then run tools/sync.py:

    python tools/gallery_build.py           # rewrite the gallery files made here
    python tools/gallery_build.py --check   # exit 1 if any of them differs from what this would write
"""
import itertools
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
GALLERY = ROOT / "gallery"
AUTHOR, RUNTIME = "itsfja", "2.2.0"
_ids = itertools.count(1)


# ----- Building blocks -------------------------------------------------------------------------------------------------
def B(type_, fields=None, **inputs):
    """A block. Keyword inputs are block dicts, or plain values made into shadows (str → text, int/float → number)."""
    b = {"type": type_}
    if fields:
        b["fields"] = fields
    ins = {}
    for k, v in inputs.items():
        if isinstance(v, dict) and "_shadow" in v:
            ins[k] = {"shadow": v["_shadow"]}
        elif isinstance(v, dict):
            ins[k] = {"block": v}
        elif isinstance(v, (int, float)):
            ins[k] = {"shadow": {"type": "math_number", "fields": {"NUM": v}}}
        else:
            ins[k] = {"shadow": {"type": "text", "fields": {"TEXT": v}}}
    if ins:
        b["inputs"] = ins
    return b


def L(text):
    """A long text slot (rb_longtext shadow), for prompts and goals."""
    return {"_shadow": {"type": "rb_longtext", "fields": {"TEXT": text}}}


def chain(*blocks):
    """Links statement blocks one under another. Returns the first."""
    blocks = [b for b in blocks if b]
    for a, b in zip(blocks, blocks[1:]):
        a["next"] = {"block": b}
    return blocks[0]


def join(*parts):
    """text_join of strings (as long texts) and blocks."""
    ins = {f"ADD{i}": (L(p) if isinstance(p, str) else p) for i, p in enumerate(parts)}
    b = B("text_join", **ins)
    b["extraState"] = {"itemCount": len(parts)}
    return b


class Vars:
    def __init__(self, *names):
        self.ids = {n: f"g_{n.replace(' ', '_')}" for n in names}

    def set(self, name, value):
        return B("variables_set", {"VAR": {"id": self.ids[name]}}, VALUE=value)

    def get(self, name):
        return B("variables_get", {"VAR": {"id": self.ids[name]}})

    def decl(self):
        return [{"id": i, "name": n} for n, i in self.ids.items()]


def if_(cond, then, else_=None):
    b = B("controls_if", IF0=cond, DO0=then, **({"ELSE": else_} if else_ else {}))
    if else_:
        b["extraState"] = {"hasElse": True}
    return b


def agent(goal, tools, steps=12, plan=False):
    t = [B("rb_agent_builtin", {"KIND": k}) for k in tools]
    return B("rb_agent", {"PLAN": plan}, GOAL=goal if isinstance(goal, dict) and "_shadow" not in goal else goal,
             STEPS=steps, TOOLS=chain(*t))


def hat(type_, fields=None):
    return B(type_, fields)


def when_time(h, m, days="every"):
    return hat("rb_when_time", {"HOUR": h, "MINUTE": m, "DAYS": days})


def start_and(*hats_, msg, value=None, test=None):
    """Scripts that each start the shared job: Run (with an optional test question) and the real triggers."""
    send = (lambda v: B("rb_broadcast_with_wait", MSG=msg, VALUE=v)) if value is not None or test else (lambda v: B("rb_broadcast_wait", MSG=msg))
    out = [chain(hat("rb_start"), *([B("rb_ask_me", TEXT=L(test))] if test else []), send(B("rb_answer") if test else None))]
    out += [chain(h, send(value)) for h in hats_]
    return out


def receive(msg, *body):
    return chain(hat("rb_receive", {"MSG": msg}), *body)


def email_me(subject, text):
    return B("rb_email_send", TO="you@example.com", SUBJECT=subject, TEXT=text)


def program(name, title, category, description, tip, scripts, v=None):
    blocks = []
    for i, s in enumerate(scripts):
        s["x"], s["y"] = 30 + (i % 2) * 520, 30 + (i // 2) * 260
        blocks.append(s)
    prog = {"blocks": {"languageVersion": 0, "blocks": blocks}}
    if v:
        prog = {"variables": v.decl(), **prog}
    return name, {"format": "reflection-blocks", "version": 1, "name": name,
                  "gallery": {"title": title, "category": category, "description": description, "tip": tip,
                              "author": AUTHOR, "runtime": RUNTIME},
                  "program": prog}


# ----- The programs ----------------------------------------------------------------------------------------------------
PROGRAMS = []


def add(p):
    PROGRAMS.append(p)


# GitHub: #148
add(program(
    "pr-review-roundup", "PR review roundup", "github",
    "Each weekday morning, the open pull requests across your GitHub projects, each with a verdict: ready to merge, or "
    "needs work, and why in a sentence. Emailed to you.",
    "Change 7:30 to when you start work, and the address in the email block to yours.",
    start_and(when_time(7, 30, "weekdays"), msg="roundup") + [receive(
        "roundup",
        agent(L("List my GitHub projects, then the open pull requests in each that changed in the last two weeks, and read each one. "
                "Give each a verdict: READY TO MERGE or NEEDS WORK, with one sentence saying why (tests, description, size, anything "
                "risky). Group them by project, ready ones first. Before you finish, check your verdicts with review_text against: "
                "every verdict names something in the pull request itself; nothing is invented."), ["github", "review"], steps=15),
        email_me("Pull requests: ready or not", B("rb_draft")),
        B("rb_result"))]))

# News: #157
v = Vars("news", "overnight")
add(program(
    "morning-briefing", "Morning briefing", "news",
    "One email each morning: what you need to know today, from your news feeds and a sourced check with Perplexity on "
    "anything big overnight, under 300 words.",
    "Put your feeds in second-thought.ini (feeds = …). On the page, Claude stands in for Perplexity and the feeds are samples.",
    start_and(when_time(7, 0), msg="briefing") + [receive(
        "briefing",
        v.set("news", B("rb_feed_news", URL="")),
        B("rb_with_model", {"TIER": "perplexity-default"}, DO=v.set("overnight", B("rb_ask", TEXT=L(
            "In five short bullet points, each with its source, the most important things that happened overnight that "
            "someone in the UK should know this morning: world, UK, money, weather.")))),
        B("rb_task", TEXT=join("Write \"What you need to know today\": a short, calm briefing from these feed items and this overnight "
                               "check. Most important first, one or two lines each, with its link or source.\n\nFeeds:\n", v.get("news"),
                               "\n\nOvernight:\n", v.get("overnight"))),
        B("rb_generate"),
        B("rb_reflect", CRITERIA=L("under 300 words; nothing said twice; every item has its link or source; plain text"), ROUNDS=2,
          FIX=B("rb_revise")),
        email_me("What you need to know today", B("rb_draft")),
        B("rb_result"))], v))

# News: #158
v = Vars("topic")
add(program(
    "topic-sentinel", "Topic sentinel", "news",
    "Watches one topic, like quantum computing funding. Each Monday, a synthesis of what changed since last week, with a "
    "source for every claim and nothing it already told you.",
    "Change the topic in the first block. It remembers each week's synthesis, so the second week is where it shines.",
    start_and(msg="sentinel") + [
        chain(when_time(8, 0, "weekdays"), if_(B("logic_compare", {"OP": "EQ"}, A=B("rb_now", {"PART": "weekday"}), B="Monday"),
                                               B("rb_broadcast_wait", MSG="sentinel"))),
        receive(
        "sentinel",
        v.set("topic", B("text", {"TEXT": "quantum computing funding"})),
        agent(join("You watch one topic for me: ", v.get("topic"), ".\nFirst recall the note 'last synthesis' (it may not exist yet). "
                   "Search the web for news on the topic from the past week and read the best sources in full. Write a short synthesis "
                   "of what changed since the last one: new funding, programmes, results or policy. Give a source link for every "
                   "claim, and leave out anything the last synthesis already said. Check it with review_text against: every claim "
                   "has a source; nothing repeats last week. Then remember it as 'last synthesis'."),
              ["web", "memory", "review"], steps=15),
        email_me(join("This week in ", v.get("topic")), B("rb_draft")),
        B("rb_result"))], v))

# Home Assistant: #167
v = Vars("openings", "warning")
add(program(
    "leaving-home-check", "Leaving-home check", "home",
    "Your phone calls it as you leave home. If any door or window is still open, the house says so on the kitchen speaker "
    "and you get a notification. If everything's shut, it stays quiet.",
    "In the Home Assistant app, make an automation for leaving home that calls this program's /leaving address (see Web "
    "requests in the README). Change the speaker to yours.",
    start_and(hat("rb_webhook_when", {"PATH": "leaving"}), msg="leaving", value=B("rb_event", {"KEY": ""})) + [receive(
        "leaving",
        v.set("openings", join(B("rb_ha_summary", TEXT="door"), "\n", B("rb_ha_summary", TEXT="window"))),
        if_(B("rb_ask_yesno", TEXT=join("Do these readings show any door or window open (on, or open), not counting the doorbell "
                                        "or anything unavailable?\n\n", v.get("openings"))),
            chain(v.set("warning", B("rb_ask", TEXT=join("In one short spoken sentence, warn someone leaving the house which doors or "
                                                        "windows are still open. Use their everyday names.\n\n", v.get("openings")))),
                  B("rb_ha_speak", TEXT=v.get("warning"), PLAYER="media_player.kitchen_speaker"),
                  B("rb_ha_notify", TARGET="persistent_notification", TEXT=v.get("warning")),
                  B("rb_finish_with", TEXT=v.get("warning"))),
            B("rb_finish_with", TEXT="Everything's shut. Nothing said.")))], v))

# Home Assistant: #168
v = Vars("explained")
add(program(
    "energy-autopsy", "Energy autopsy", "home",
    "Each night, reads the day's power use from Home Assistant and explains the spikes in plain English, like \"the 2 to "
    "4pm spike was the tumble dryer\".",
    "Add your own big appliances' power sensors to the question, in place of the washing machine and garage heater.",
    start_and(when_time(22, 0), msg="autopsy") + [receive(
        "autopsy",
        v.set("explained", B("rb_ask", TEXT=join(
            "Here is today's whole-house power, and the power of some devices. Find the two or three biggest spikes (when, and "
            "roughly how many watts) and say which device most likely caused each, like 'the 2 to 4pm spike was the tumble "
            "dryer'. Plain English, at most five lines, then one thing worth changing.\n\nHouse power, last 24 hours:\n",
            B("rb_ha_history", ENTITY="sensor.house_power", HOURS=24),
            "\n\nWashing machine, last 24 hours:\n", B("rb_ha_history", ENTITY="sensor.washing_machine_power", HOURS=24),
            "\n\nGarage heater, last 24 hours:\n", B("rb_ha_history", ENTITY="sensor.garage_heater_power", HOURS=24),
            "\n\nEverything reporting power now:\n", B("rb_ha_summary", TEXT="power")))),
        B("rb_ha_notify", TARGET="persistent_notification", TEXT=v.get("explained")),
        B("rb_finish_with", TEXT=v.get("explained")))], v))

# Calendar and email: #170
add(program(
    "inbox-shrinking-violet", "Inbox shrinking violet", "calendar",
    "Twice a day, sorts your inbox into needs a reply, read later and maybe unsubscribe, with a draft reply for each of the "
    "first pile, all in one email to you. It never replies for you.",
    "Change the times to suit you. The drafts are in your style if you tell it how you write, in the agent's goal.",
    start_and(when_time(9, 0), when_time(16, 0), msg="sort inbox") + [receive(
        "sort inbox",
        agent(L("Look through my email from the last day (search_email with days 1) and read the ones you need to. Sort every email "
                "into three piles. NEEDS A REPLY: who, what they want, and a short draft reply for each, friendly and brief. READ "
                "LATER: one line each on why it's worth it. MAYBE UNSUBSCRIBE: newsletters and promotions, with the sender. Leave out "
                "anything already handled. Don't send anything."), ["email"], steps=14),
        email_me("Your inbox, sorted", B("rb_draft")),
        B("rb_result"))]))

# Calendar and email: #171
add(program(
    "meeting-fairy", "Meeting fairy", "calendar",
    "The evening before, reads tomorrow's calendar, finds recent emails with the people you're meeting, and sends you a one-page "
    "brief for each meeting: what's open between you first.",
    "Change 19:00 to when you plan tomorrow. Meetings with nobody else in them are skipped.",
    start_and(when_time(19, 0, "weekdays"), msg="brief") + [receive(
        "brief",
        agent(L("Look at tomorrow's calendar. For each meeting with other people, search my email from the last 30 days for recent "
                "messages from or about them and the topic, and read the useful ones. Write a brief for each meeting: who, when and "
                "where; what's open between us (questions, promises, decisions waiting) first; useful background; then two "
                "questions I should ask. Check each with review_text against: under one page; open items first; nothing invented."),
              ["calendar", "email", "review"], steps=16),
        email_me("Tomorrow's meetings", B("rb_draft")),
        B("rb_result"))]))

# Calendar and email: #172
v = Vars("name", "notes", "ideas", "fact")
add(program(
    "birthday-reminder-with-gift-ideas", "Birthdays, with gift ideas", "calendar",
    "A week before each birthday in your calendar, a Telegram reminder with three gift ideas that fit what you've told it about "
    "the person. Tell it things any time: message your bot 'note Sam: loves rye bread'.",
    "Keep birthdays in a calendar it can read. The more notes you send, the better the ideas get.",
    start_and(hat("rb_cal_when", {"N": 10080}), msg="soon", value=B("rb_event", {"KEY": "text"}),
              test="Type a calendar event to test with, like 'Sam's birthday'") + [
        chain(hat("rb_tg_when", {"CONTAINS": "note"}), B("rb_broadcast_with_wait", MSG="note", VALUE=B("rb_event", {"KEY": "text"}))),
        receive(
            "soon",
            if_(B("rb_ask_yesno", TEXT=join("Is this calendar event someone's birthday?\n", B("rb_msg_value"))),
                chain(v.set("name", B("rb_extract", WHAT="the person's first name", TEXT=B("rb_msg_value"))),
                      v.set("notes", B("rb_mem_get", NAME=join("about ", v.get("name")))),
                      v.set("ideas", B("rb_ask", TEXT=join(
                          "Suggest three birthday presents for ", v.get("name"), ", each under £40, that fit what I know about them: ",
                          v.get("notes"), "\nOne line each: the present, and why it suits them. If I know nothing about them, suggest "
                          "thoughtful general ideas, and end by saying what to tell you about them."))),
                      B("rb_tg_send", TEXT=join("🎂 ", v.get("name"), "'s birthday is in a week.\n\n", v.get("ideas"))),
                      B("rb_finish_with", TEXT=v.get("ideas"))),
                B("rb_finish_with", TEXT="Not a birthday."))),
        receive(
            "note",
            v.set("name", B("rb_extract", WHAT="the person's first name", TEXT=B("rb_msg_value"))),
            v.set("fact", B("rb_extract", WHAT="what it says about them", TEXT=B("rb_msg_value"))),
            B("rb_mem_add", {"KIND": "permanent"}, VALUE=v.get("fact"), NAME=join("about ", v.get("name"))),
            B("rb_tg_send", TEXT=join("Noted for ", v.get("name"), ".")),
            B("rb_finish_with", TEXT=join("Noted for ", v.get("name"), ": ", v.get("fact"))))], v))

# Odds and ends: #173
v = Vars("was", "now", "target")
add(program(
    "price-hawk", "Price hawk", "odds",
    "Watches any product page and sends you a Telegram message when the price drops, or reaches your target. Rises and "
    "everything else on the page are ignored.",
    "Change the page address and 'Price' in the hat to the product and the word next to its price. Set a target, or 0 for any drop.",
    start_and(hat("rb_page_when", {"URL": "https://example.com/shop/rye-flour", "WORDS": "Price", "N": 60}), msg="price",
              value=B("rb_event", {"KEY": "text"}), test="Type a change to test with, like '- £2.40' then '+ £2.15' on the next line") + [
        receive(
            "price",
            v.set("target", B("math_number", {"NUM": 0})),
            v.set("was", B("rb_ask_number", TEXT=join("This is how a price changed on a shop's page. Lines starting - are before, + "
                                                      "after. What was the price before, as a number?\n\n", B("rb_msg_value")))),
            v.set("now", B("rb_ask_number", TEXT=join("This is how a price changed on a shop's page. Lines starting - are before, + "
                                                      "after. What is the price now, as a number?\n\n", B("rb_msg_value")))),
            if_(B("logic_operation", {"OP": "OR"},
                  A=B("logic_compare", {"OP": "LT"}, A=v.get("now"), B=v.get("was")),
                  B=B("logic_operation", {"OP": "AND"}, A=B("logic_compare", {"OP": "GT"}, A=v.get("target"), B=B("math_number", {"NUM": 0})),
                      B=B("logic_compare", {"OP": "LTE"}, A=v.get("now"), B=v.get("target")))),
                chain(B("rb_tg_send", TEXT=join("Price drop: ", v.get("was"), " → ", v.get("now"), "\nhttps://example.com/shop/rye-flour")),
                      B("rb_finish_with", TEXT=join("Price drop: ", v.get("was"), " → ", v.get("now")))),
                B("rb_finish_with", TEXT=join("No drop (", v.get("was"), " → ", v.get("now"), ")."))))], v))


def main() -> int:
    bad = []
    for name, data in PROGRAMS:
        path = GALLERY / f"{name}.json"
        text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        if "--check" in sys.argv:
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                bad.append(path.name)
        else:
            path.write_text(text, encoding="utf-8")
    if bad:
        print("Out of date: " + ", ".join(bad) + ". Run: python tools/gallery_build.py")
        return 1
    print(("Checked " if "--check" in sys.argv else "Wrote ") + f"{len(PROGRAMS)} gallery programs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
