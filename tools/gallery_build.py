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


def on_day(day, h, m, msg):
    """A script that starts a job at h:m on one day of the week (when it's … has every, weekdays and weekends)."""
    days = "weekends" if day in ("Saturday", "Sunday") else "weekdays"
    return chain(when_time(h, m, days), if_(B("logic_compare", {"OP": "EQ"}, A=B("rb_now", {"PART": "weekday"}), B=day),
                                            B("rb_broadcast_wait", MSG=msg)))


def every_n_days(n, name, msg):
    """A script that starts a job once every n days: a daily check on a note that forgets itself after n days."""
    return chain(when_time(9, 0), if_(B("logic_negate", BOOL=B("rb_mem_has", NAME=name)),
                                      chain(B("rb_mem_set_for", {"UNIT": "d"}, VALUE="sent", NAME=name, N=n), B("rb_broadcast_wait", MSG=msg))))


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


# ===== Batch 2: priority-3 programs that today's blocks can do =========================================================
# GitHub: #151
add(program(
    "stale-branch-sweeper", "Stale branch sweeper", "github",
    "Each Monday, finds branches with no commits in 90 days and no open pull request, across your recent GitHub projects, "
    "and opens one cleanup issue per project, or updates last week's instead of opening another.",
    "It asks before opening or commenting. Choose the no-asking tool once you trust what it writes.",
    start_and(msg="sweep") + [on_day("Monday", 9, 0, "sweep"), receive(
        "sweep",
        agent(L("List my GitHub projects and keep those pushed in the last six months. For each, list its branches. Stale branches "
                "have a last commit over 90 days ago, aren't the default branch, and have no open pull request. For each project with "
                "stale branches, recall the note 'stale branches <project>'. If it names an issue number, comment on that issue with "
                "the updated list. Otherwise open an issue titled 'Stale branches to clean up' listing each branch, how old it is and "
                "who last changed it, and remember its number as 'stale branches <project>'. If nothing is stale, change nothing."),
              ["github", "github_act", "memory"], steps=18),
        B("rb_result"))]))

# Money: #152
v = Vars("charges", "changes")
add(program(
    "spend-canary", "Spend canary", "money",
    "When a bank statement arrives (a file in a folder, or an email), it lists your recurring charges and tells you which "
    "changed price since last month. Statements are sent to the model; only merchants and amounts are kept, in memory.",
    "Change the folder to where you save statements, and the email words to what your bank's statement emails say.",
    start_and(hat("rb_folder_when", {"FOLDER": "~/Bank statements"}), hat("rb_email_when", {"CONTAINS": "statement"}), msg="statement",
              value=B("rb_event", {"KEY": "text"}), test="Paste a few lines of a statement to test with") + [receive(
        "statement",
        v.set("charges", B("rb_ask", TEXT=join("List the card payments and direct debits in this bank statement, one per line, as: "
                                               "merchant — amount. Nothing else.\n\n", B("rb_msg_value")))),
        v.set("changes", B("rb_ask", TEXT=join("Here are this month's charges, and last month's. List recurring charges (the same "
                                               "merchant both months) whose amount changed, with both amounts. If none did, reply "
                                               "exactly: no changes\n\nThis month:\n", v.get("charges"), "\n\nLast month:\n",
                                               B("rb_mem_get", NAME="last month's charges")))),
        B("rb_mem_set", {"KIND": "permanent"}, VALUE=v.get("charges"), NAME="last month's charges"),
        if_(B("rb_contains", A=v.get("changes"), B="no changes"),
            B("rb_finish_with", TEXT="No recurring charge changed price."),
            chain(email_me("Charges that changed price", v.get("changes")), B("rb_finish_with", TEXT=v.get("changes")))))], v))

# Money: #153
v = Vars("invoice")
add(program(
    "invoice-matcher", "Invoice matcher", "money",
    "Keeps a list of the receipts you save to a folder. When an invoice arrives by email, it checks for a matching receipt "
    "and emails you if there isn't one.",
    "Change the folder to where you keep receipts. It only knows receipts saved after it starts.",
    start_and(hat("rb_email_when", {"CONTAINS": "invoice"}), msg="invoice", value=B("rb_event", {"KEY": "text"}),
              test="Paste an invoice email to test with") + [
        chain(hat("rb_folder_when", {"FOLDER": "~/Receipts"}), B("rb_broadcast_with_wait", MSG="receipt", VALUE=B("rb_event", {"KEY": "text"}))),
        receive("receipt",
                B("rb_mem_add", {"KIND": "permanent"}, VALUE=B("rb_ask", TEXT=join(
                    "In one line, from this receipt: supplier — amount — date. Nothing else.\n\n", B("rb_msg_value"))), NAME="receipts"),
                B("rb_finish_with", TEXT="Receipt noted.")),
        receive("invoice",
                v.set("invoice", B("rb_ask", TEXT=join("In one line, from this invoice: supplier — amount — date. Nothing else.\n\n",
                                                       B("rb_msg_value")))),
                if_(B("rb_ask_yesno", TEXT=join("Is there a receipt for this invoice in the list: the same supplier and amount, within a "
                                                "month?\nInvoice: ", v.get("invoice"), "\nReceipts:\n", B("rb_mem_get", NAME="receipts"))),
                    B("rb_finish_with", TEXT=join("Matched: ", v.get("invoice"))),
                    chain(email_me("Invoice with no receipt", join("No receipt found for: ", v.get("invoice"))),
                          B("rb_finish_with", TEXT=join("No receipt for: ", v.get("invoice"))))))], v))

# Money: #155
v = Vars("country", "advice")
add(program(
    "fx-travel-check", "Travel money check", "money",
    "Two days before a calendar event abroad, looks up the exchange rate and sends a Telegram reminder about cash, card fees "
    "and plugs.",
    "It decides from the event's title and place whether it's abroad. Web search only works in exported Python.",
    start_and(hat("rb_cal_when", {"N": 2880}), msg="trip", value=B("rb_event", {"KEY": "text"}),
              test="Type an event to test with, like 'Flight to Lisbon'") + [receive(
        "trip",
        if_(B("rb_ask_yesno", TEXT=join("Does this calendar event take place outside the UK?\n", B("rb_msg_value"))),
            chain(v.set("country", B("rb_extract", WHAT="the country it takes place in", TEXT=B("rb_msg_value"))),
                  v.set("advice", B("rb_ask", TEXT=join(
                      "Using these search results, give today's rate from pounds to the currency of ", v.get("country"),
                      ", then three short reminders for the trip: cash, card fees abroad, and the plug type.\n\n",
                      B("rb_web_search", TEXT=join("pound exchange rate today ", v.get("country")))))),
                  B("rb_tg_send", TEXT=join("✈️ ", B("rb_msg_value"), "\n", v.get("advice"))),
                  B("rb_finish_with", TEXT=v.get("advice"))),
            B("rb_finish_with", TEXT="Not abroad.")))], v))

# News: #159
add(program(
    "competitor-radar", "Competitor radar", "news",
    "Watches competitors' news or changelog pages, keeps every change, and every 28 days emails a digest of what each one shipped.",
    "Add a 'when the web page … changes' hat for each competitor's page, like the one here. The digest goes out 28 days after it starts.",
    start_and(msg="digest") + [
        chain(hat("rb_page_when", {"URL": "https://example.com/competitor/changelog", "WORDS": "", "N": 360}),
              B("rb_broadcast_with_wait", MSG="change", VALUE=B("rb_event", {"KEY": "text"}))),
        every_n_days(28, "competitor digest sent", "digest"),
        receive("change",
                B("rb_mem_add", {"KIND": "permanent"}, VALUE=join(B("rb_now", {"PART": "date"}), ": ", B("rb_msg_value")),
                  NAME="competitor changes"),
                B("rb_finish_with", TEXT="Change noted.")),
        receive("digest",
                B("rb_task", TEXT=join("These are changes I noticed on competitors' pages over the last month, with dates. Write a "
                                       "digest of what each competitor shipped: grouped by competitor, newest first, one line per "
                                       "launch or change, skipping cosmetic edits. If there's nothing, say so.\n\n",
                                       B("rb_mem_get", NAME="competitor changes"))),
                B("rb_generate"),
                email_me("What competitors shipped this month", B("rb_draft")),
                B("rb_mem_forget", NAME="competitor changes"),
                B("rb_result"))]))

# News: #160
v = Vars("topics", "hits")
add(program(
    "local-council-watch", "Council agenda watch", "news",
    "Watches your council's agenda page and emails you when an item matches your topics, with the meeting and its date.",
    "Change the page to your council's agendas and the topics in the first block. Agendas only in PDFs can't be watched.",
    start_and(hat("rb_page_when", {"URL": "https://example.com/council/agendas", "WORDS": "Agenda", "N": 720}), msg="agenda",
              value=B("rb_event", {"KEY": "text"}), test="Paste an agenda item to test with") + [receive(
        "agenda",
        v.set("topics", B("text", {"TEXT": "planning applications, bin collections, parking, cycle lanes"})),
        v.set("hits", B("rb_ask", TEXT=join("This is what changed on a council's agenda page. List any items about these topics: ",
                                            v.get("topics"), ". One line each: the item, the committee, and the meeting date. If none "
                                            "match, reply exactly: nothing\n\n", B("rb_msg_value")))),
        if_(B("rb_contains", A=v.get("hits"), B="nothing"),
            B("rb_finish_with", TEXT="Nothing on the agenda for your topics."),
            chain(email_me("On the council agenda", v.get("hits")), B("rb_finish_with", TEXT=v.get("hits")))))], v))

# News: #161
v = Vars("interests", "papers")
add(program(
    "arxiv-fisher", "arXiv fisher", "news",
    "Each morning, the five new arXiv papers closest to your interests, each with a plain-English paragraph on what they did "
    "and why it matters. Emailed to you.",
    "Put your arXiv category feeds in second-thought.ini, like feeds = https://rss.arxiv.org/rss/cs.AI, and your interests in the first block.",
    start_and(when_time(6, 0), msg="papers") + [receive(
        "papers",
        v.set("interests", B("text", {"TEXT": "AI agents, evaluation, tool use"})),
        v.set("papers", B("rb_feed_news", URL="")),
        B("rb_task", TEXT=join("These are new postings from my feeds (ignore anything that isn't an arXiv paper). My interests: ",
                               v.get("interests"), ". Pick the five most relevant. For each: the title and link, then one "
                               "plain-English paragraph on what they did and why it matters, for someone who doesn't read papers.\n\n",
                               v.get("papers"))),
        B("rb_generate"),
        B("rb_review", CRITERIA=L("five papers at most; each has its link; no jargon left unexplained")),
        if_(B("logic_negate", BOOL=B("rb_passed")), B("rb_revise")),
        email_me("Five papers worth your time", B("rb_draft")),
        B("rb_result"))], v))

# Coding: #162
v = Vars("project")
add(program(
    "docs-drift-detector", "Docs drift detector", "coding",
    "Each Monday, compares a project's README with its code: flags, commands and files the README mentions that don't exist, "
    "and ones the code has that it doesn't mention. Opens an issue, or updates the open one.",
    "Change the project in the first block. On the page, the sample project's README really has drifted.",
    start_and(msg="drift") + [on_day("Monday", 9, 30, "drift"), receive(
        "drift",
        v.set("project", B("text", {"TEXT": "sample-baker/sourdough-chart"})),
        agent(join("In the GitHub project ", v.get("project"), ", read README.md, the top folder, and the code for its command line "
                   "(look in src/ or the main package). List every flag, command and file the README mentions that the code doesn't "
                   "have, and every flag the code has that the README doesn't mention. Check your list with review_text against: each "
                   "difference names where it comes from; nothing invented. If there are differences, search_github for an open issue "
                   "titled 'README drift' in the project: comment on it if there is one, otherwise open one. If there are none, change "
                   "nothing and say so."), ["github", "github_act", "review"], steps=14),
        B("rb_result"))], v))

# Coding: #163
add(program(
    "test-failure-whisperer", "Test failure whisperer", "coding",
    "When CI fails, your workflow sends it the end of the log. It reads the pull request and posts a short 'Probably this:' "
    "comment with the likely cause and one thing to try.",
    "Add a workflow step that runs on failure and posts the repo, PR number and last 200 log lines to /ci-failed. GitHub "
    "must be able to reach the program.",
    start_and(hat("rb_webhook_when", {"PATH": "ci-failed"}), msg="failed", value=B("rb_event", {"KEY": "text"}),
              test="Paste what the workflow would send: repo, PR number and the end of the log") + [receive(
        "failed",
        agent(join("A CI run failed. This is what the workflow sent (the project, the pull request number and the end of the log):\n",
                   B("rb_msg_value"), "\n\nRead the pull request. Work out the most likely cause in two or three sentences, pointing at "
                   "the file and change that probably caused it, and suggest one thing to try. Then post it as a comment on the pull "
                   "request, starting 'Probably this:'. If there's no pull request number, don't comment: just answer."),
              ["github", "github_act"], steps=8),
        B("rb_result"))]))

# Coding: #164
add(program(
    "commit-summariser", "Standup from commits", "coding",
    "Each weekday morning, your commits from the day before across your GitHub projects, grouped by intent, as standup notes "
    "in Slack.",
    "Change 8:45 to before your standup. It reads only commits on each project's main branch.",
    start_and(when_time(8, 45, "weekdays"), msg="standup") + [receive(
        "standup",
        agent(L("List my GitHub projects and keep those pushed in the last two days. In each, list_commits with author me since "
                "yesterday. Group my commits by intent (features, fixes, refactoring, docs, other), one plain-English line each with "
                "the project in brackets. End with a one-line summary I could say at standup. If there are none, say so."),
              ["github"], steps=12),
        B("rb_slack_send", TEXT=B("rb_draft")),
        B("rb_result"))]))

# Coding: #165
v = Vars("project")
add(program(
    "dep-watcher", "Dependency watcher", "coding",
    "Each Monday, reads the releases feeds of your dependencies, summarises breaking changes, and checks your project's "
    "dependency file to say whether each one touches you.",
    "Put each dependency's releases feed in feeds = …, like https://github.com/d3/d3/releases.atom, and your project in the first block.",
    start_and(msg="deps") + [on_day("Monday", 9, 15, "deps"), receive(
        "deps",
        v.set("project", B("text", {"TEXT": "sample-baker/sourdough-chart"})),
        agent(join("Recall the note 'releases seen'. Read my feeds (read_feed with no url): they're the releases of my "
                   "dependencies. For each release newer than the ones I've seen, say in a line whether it has breaking changes, and "
                   "what. Then read the dependency file in ", v.get("project"), " (package.json, requirements.txt or pyproject.toml) "
                   "and say whether each breaking change affects a version I use. Finally remember the newest release of each "
                   "dependency as 'releases seen'."), ["feeds", "github", "memory"], steps=12),
        email_me("Dependency releases this week", B("rb_draft")),
        B("rb_result"))], v))

# Home: #169
v = Vars("rules", "said")
add(program(
    "guest-mode-announcer", "Guest mode announcer", "home",
    "When guest mode turns on or off in Home Assistant, the kitchen speaker tells everyone what changes: guest Wi-Fi, quiet "
    "hours, heating, cameras.",
    "Change the rules in the first block to your house's, and the speaker to yours. Needs an input_boolean.guest_mode helper.",
    start_and(hat("rb_ha_when", {"ENTITY": "input_boolean.guest_mode", "STATE": "on"}),
              hat("rb_ha_when", {"ENTITY": "input_boolean.guest_mode", "STATE": "off"}), msg="guests",
              value=B("rb_event", {"KEY": "state"}), test="Type on or off, as if guest mode just changed") + [receive(
        "guests",
        v.set("rules", B("rb_longtext", {"TEXT": "Guest Wi-Fi is BakeHouse-Guest, password on the fridge. Quiet after 10pm. The spare "
                                                 "room heating comes on. Indoor camera notifications pause."})),
        v.set("said", B("rb_ask", TEXT=join("Guest mode just turned ", B("rb_msg_value"), ". In two warm spoken sentences, tell "
                                            "everyone in the house what changes now (or goes back to normal). Guest mode means: ",
                                            v.get("rules")))),
        B("rb_ha_speak", TEXT=v.get("said"), PLAYER="media_player.kitchen_speaker"),
        B("rb_finish_with", TEXT=v.get("said")))], v))

# Home: #174
add(program(
    "recipe-scaler-weekly", "Weekly recipes and shopping list", "home",
    "Remembers recipes you drop in a folder. Run it on shopping day: say which recipes and for how many, and it scales them and "
    "makes one shopping list grouped by supermarket aisle.",
    "Change the folder to where you keep recipes (PDF, Word or text). Run it by hand, since it asks which recipes you want.",
    [chain(hat("rb_folder_when", {"FOLDER": "~/Recipes"}), B("rb_broadcast_with_wait", MSG="recipe", VALUE=B("rb_event", {"KEY": "text"}))),
     receive("recipe",
             B("rb_mem_add", {"KIND": "permanent"}, VALUE=B("rb_ask", TEXT=join(
                 "Write this recipe as one line: its name (serves N): each ingredient with its amount, separated by semicolons.\n\n",
                 B("rb_msg_value"))), NAME="recipes"),
             B("rb_finish_with", TEXT="Recipe remembered.")),
     chain(hat("rb_start"),
           B("rb_ask_me", TEXT=L("Which recipes this week, and for how many people? (Your recipes are listed in the agent's first step.)")),
           agent(join("My recipes, one per line:\n", B("rb_mem_get", NAME="recipes"), "\n\nThis week I want: ", B("rb_answer"),
                      "\nScale each recipe to the servings I want, using calculate for every amount. If a recipe isn't in my list, "
                      "use a standard version. Then write one shopping list grouped by supermarket aisle (fruit and veg, bakery, "
                      "dairy, meat and fish, tins and jars, dry goods, frozen), adding up the same ingredient across recipes."),
                 ["calc"], steps=12),
           B("rb_file_save", {"EXT": "md"}, VALUE=B("rb_draft"), NAME="shopping-list"),
           email_me("Shopping list", B("rb_draft")),
           B("rb_result"))]))

# Odds and ends: #176
add(program(
    "language-ladybird", "Ladybird lesson", "odds",
    "Each morning, one page of Second Thought's Ladybird book in a different historical language from its translations, "
    "Akkadian days included, with the English alongside and three words to learn.",
    "Historical-language versions are as plausible as Second Thought's own translations, no more. Reading pages works in exported Python.",
    start_and(when_time(7, 30), msg="lesson") + [receive(
        "lesson",
        agent(join("Today is ", B("rb_now", {"PART": "weekday"}), ". Today's language: Monday Latin (la), Tuesday Old English (ang), "
                   "Wednesday Akkadian (akk), Thursday Old Norse (non), Friday Koine Greek (grc), Saturday Sanskrit (sa), Sunday "
                   "Mycenaean Greek in Linear B (gmy). Read https://raw.githubusercontent.com/itsfja/second-thought/main/docs/ladybird-book.md "
                   "and pick one page, a different one each day. Read the language's words at "
                   "https://raw.githubusercontent.com/itsfja/second-thought/main/i18n/<code>.json. Write that page in today's "
                   "language, using the file's words where they fit, with the English alongside. Then give three words from it to "
                   "learn, each with its meaning. End by saying the historical version is plausible, not authoritative."),
              ["web"], steps=6),
        email_me("Today's Ladybird lesson", B("rb_draft")),
        B("rb_result"))]))

# Odds and ends: #177
v = Vars("town", "window")
add(program(
    "rain-window", "Rain window", "odds",
    "Friday evening: the best two-hour window this weekend for drying washing outside, from the forecast, with a runner-up. "
    "Sent to you on Telegram.",
    "Change the town in the first block. Web search only works in exported Python; on the page Claude says what it would look up.",
    start_and(msg="washing") + [on_day("Friday", 18, 0, "washing"), receive(
        "washing",
        v.set("town", B("text", {"TEXT": "London"})),
        v.set("window", B("rb_ask", TEXT=join(
            "From this forecast, find the best two-hour window this Saturday or Sunday to dry washing outside: dry, ideally breezy "
            "and mild. Give the day and time, and a runner-up. If there isn't one, say so kindly.\n\n",
            B("rb_web_search", TEXT=join("hourly weather forecast this weekend ", v.get("town")))))),
        B("rb_tg_send", TEXT=join("🧺 ", v.get("window"))),
        B("rb_finish_with", TEXT=v.get("window")))], v))


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
