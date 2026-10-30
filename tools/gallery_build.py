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


# ===== Batch 3: programs that use the GitHub listeners (#145) ===========================================================
# GitHub: #149
v = Vars("project")
add(program(
    "issue-triage-bot", "Issue triage bot", "github",
    "When someone opens an issue, it labels it from the project's own labels, links a likely duplicate in a comment, and "
    "messages you on Telegram if it looks urgent.",
    "Change the project in the hat. Labelling and commenting ask first; use the no-asking tool once you trust it.",
    start_and(hat("rb_gh_issue_when", {"REPO": "sample-baker/sourdough-chart"}), msg="triage", value=B("rb_event", {"KEY": "text"}),
              test="Type an issue to test with, like 'Chart is blank on Safari: nothing shows in the chart area'") + [receive(
        "triage",
        v.set("project", B("text", {"TEXT": "sample-baker/sourdough-chart"})),
        agent(join("A new issue was opened in ", v.get("project"), ":\n", B("rb_msg_value"), "\n\nFind its number if it isn't given "
                   "(search_github for the title). Add one or two fitting labels, using only labels the project has. Search the "
                   "project's open issues for a likely duplicate; if there's a clear one, comment linking it. Finally answer in one "
                   "line: URGENT if it describes data loss, a security problem or the app not working for everyone, otherwise ROUTINE, "
                   "then a short reason."), ["github", "github_act"], steps=10),
        if_(B("rb_contains", A=B("rb_draft"), B="URGENT"), B("rb_tg_send", TEXT=join("🚨 Urgent issue: ", B("rb_msg_value"), "\n", B("rb_draft")))),
        B("rb_result"))], v))

# GitHub: #150
add(program(
    "release-notes-writer", "Release notes writer", "github",
    "When a release is published, gathers the pull requests merged since the release before it and drafts changelog-ready "
    "notes grouped into Added, Changed and Fixed. Saved as a file and emailed to you.",
    "Change the project in the hat. It drafts; you paste. It never edits the release itself.",
    start_and(hat("rb_gh_release_when", {"REPO": "sample-baker/sourdough-chart"}), msg="release", value=B("rb_event", {"KEY": "text"}),
              test="Type a release to test with, like 'sample-baker/sourdough-chart v1.4.0, previous v1.3.2'") + [receive(
        "release",
        agent(join("A release was published: ", B("rb_msg_value"), ". Search for the pull requests merged in that project since the "
                   "previous release (search_github with is:pr is:merged and the project), and read the ones whose titles aren't clear. "
                   "Draft release notes grouped into Added, Changed and Fixed: one line each, in plain language a user would understand, "
                   "with the pull request's link. Leave out internal changes (tests, CI, refactoring) unless they change behaviour."),
              ["github"], steps=12),
        B("rb_reflect", CRITERIA=L("every line is user-facing language; every line has its pull request link; nothing invented"),
          ROUNDS=2, FIX=B("rb_revise")),
        B("rb_file_save", {"EXT": "md"}, VALUE=B("rb_draft"), NAME="release-notes"),
        email_me("Draft release notes", B("rb_draft")),
        B("rb_result"))]))

# Coding: #166
add(program(
    "first-issue-fixer", "First-issue fixer", "coding",
    "When an issue is opened that's trivial to fix from the text alone (a typo, a broken link, a missing line of docs), it "
    "reads the file and comments with a suggested patch. It can't run code, so it leaves anything else alone.",
    "Change the project in the hat. Commenting asks first. It never opens pull requests or changes the code.",
    start_and(hat("rb_gh_issue_when", {"REPO": "sample-baker/sourdough-chart"}), msg="issue", value=B("rb_event", {"KEY": "text"}),
              test="Type an issue to test with, like 'sample-baker/sourdough-chart #43: Typo in README: fermantation'") + [receive(
        "issue",
        if_(B("rb_ask_yesno", TEXT=join("Can this GitHub issue be fixed by changing a few lines of text (a typo, a broken link, a "
                                        "missing sentence in the docs), with no need to run code?\n\n", B("rb_msg_value"))),
            chain(agent(join("This issue looks trivial to fix:\n", B("rb_msg_value"), "\n\nFind the file it's about (read_github_file, "
                             "starting from the top folder) and the exact lines. Write the fix as a small unified diff. Post it as a "
                             "comment on the issue, starting 'Suggested fix (not tested):'. If, once you've read the file, it isn't "
                             "trivial after all, don't comment: just say why."), ["github", "github_act"], steps=8),
                  B("rb_result")),
            B("rb_finish_with", TEXT="Not a text-only fix, so left for a person.")))]))


# ===== Priority 4 ======================================================================================================
# Money: #154
add(program(
    "subscription-hit-list", "Subscription hit list", "money",
    "Every 90 days, finds your subscriptions from receipt emails, asks which you've actually used, and suggests which to "
    "cancel, with what each costs a year and where to cancel it.",
    "The first review is 90 days after it starts; press Run for one now. It only suggests: you do the cancelling.",
    start_and(msg="subs") + [every_n_days(90, "subscription review done", "subs"), receive(
        "subs",
        agent(L("Search my email from the last 90 days for receipts and renewal notices from subscriptions (streaming, software, "
                "apps, memberships, boxes). List each subscription once with what it costs a month and a year. Then ask me, in one "
                "question, which of them I've used in the last month. From my answer, suggest which to cancel, cheapest saving last, "
                "and for each, search the web for the page where it's cancelled and give its link."), ["email", "ask", "web"], steps=14),
        B("rb_result"))]))

# Money: #156
v = Vars("holdings", "summary")
add(program(
    "portfolio-breather", "Portfolio breather", "money",
    "Friday evening, a deliberately calm summary of your holdings: what each did this week and this month, in plain words, with "
    "no alarms, no predictions and no advice.",
    "Press Run once to tell it what you hold; it remembers. Prices come from web search, so they can lag. Not financial advice.",
    [chain(hat("rb_start"),
           if_(B("logic_negate", BOOL=B("rb_mem_has", NAME="holdings")),
               chain(B("rb_ask_me", TEXT=L("What do you hold? One per line, like 'Vanguard FTSE Global All Cap: £12,000'.")),
                     B("rb_mem_set", {"KIND": "permanent"}, VALUE=B("rb_answer"), NAME="holdings"))),
           B("rb_broadcast_wait", MSG="breathe")),
     on_day("Friday", 18, 30, "breathe"),
     receive(
         "breathe",
         v.set("holdings", B("rb_mem_get", NAME="holdings")),
         agent(join("My holdings:\n", v.get("holdings"), "\n\nFor each, search the web for its price now, a week ago and a month ago, "
                    "and work out the changes with calculate."), ["web", "calc"], steps=12),
         v.set("summary", B("rb_rewrite", TEXT=B("rb_draft"), HOW=L(
             "a calm Friday note in plain words: one line per holding with its weekly and monthly change, then one line on the "
             "whole. No alarms, no predictions, no advice. End with: Prices come from web search and can lag. This isn't "
             "financial advice."))),
         email_me("Your week, calmly", v.get("summary")),
         B("rb_finish_with", TEXT=v.get("summary")))], v))


# ===== Programs that use folder pictures and the setup check (#146, #147) ==============================================
# Odds and ends: #175
v = Vars("report")
add(program(
    "second-thought-doctor", "Second Thought doctor", "odds",
    "Once a week, runs the same checks as --doctor on your keys and connections and emails you the report if anything needs "
    "fixing, before a program finds out the hard way.",
    "Point it at the second-thought.ini in your home folder, so it checks the keys every program shares. Only runs in exported Python.",
    start_and(msg="checkup") + [on_day("Sunday", 8, 0, "checkup"), receive(
        "checkup",
        v.set("report", B("rb_setup_check")),
        if_(B("rb_contains", A=v.get("report"), B="FAIL"),
            chain(email_me("Second Thought: something to fix", v.get("report")), B("rb_finish_with", TEXT=v.get("report"))),
            B("rb_finish_with", TEXT=join("All well.\n\n", v.get("report")))))], v))

# Home: #178
v = Vars("about")
add(program(
    "family-archivist", "Family archivist", "home",
    "Watches a photos folder. For each new picture it notes the date, place and what's happening, groups it with photos from the "
    "same event, and drafts captions, asking before it writes anything. Every photo is sent to the model.",
    "To keep photos at home, choose Llama in the Model menu. It describes scenes, never who people are.",
    [chain(hat("rb_folder_when", {"FOLDER": "~/Pictures/Family"}), B("rb_broadcast_with_wait", MSG="photo", VALUE=B("rb_event", {"KEY": "picture"}))),
     chain(hat("rb_start"), B("rb_broadcast_with_wait", MSG="photo", VALUE=B("rb_img_choose"))),
     receive(
         "photo",
         v.set("about", B("rb_img_ask", TEXT=L(
             "Describe this family photo in one line for an album: the likely date or season, the place if it's obvious, and "
             "what's happening. Never say who anyone is, or guess names from faces."), IMG=B("rb_msg_value"))),
         B("rb_mem_add", {"KIND": "permanent"}, VALUE=join(B("rb_now", {"PART": "date"}), ": ", v.get("about")), NAME="photo notes"),
         B("rb_task", TEXT=join("These are notes on recent family photos, one per line, newest last:\n", B("rb_mem_get", NAME="photo notes"),
                                "\n\nGroup them into events (photos from the same day and place go together), give each event a short "
                                "title, and write a warm one-line caption for the newest photo.")),
         B("rb_generate"),
         B("rb_ask_first", {"WHAT": "files"}),
         B("rb_file_save", {"EXT": "md"}, VALUE=B("rb_draft"), NAME="album-captions"),
         B("rb_result"))], v))

# ----- Teaching (#196): the field's own standards, a mark scheme, a reading age, a word limit, are the review criteria -----
v = Vars("mark scheme", "essay")
add(program(
    "rubric-feedback", "Rubric feedback", "learning",
    "Paste a pupil's essay. Claude drafts feedback against your mark scheme, checks it's kind, specific and ends with two next "
    "steps, and you approve it before it's saved. Nothing goes to the pupil from here.",
    "Put your own mark scheme in the first block. The pupil's name isn't needed: leave it out of what you paste.",
    [chain(hat("rb_start"),
           v.set("mark scheme", B("rb_longtext", {"TEXT": "AO1 ideas: a clear argument, developed through the essay.\n"
                                                   "AO2 evidence: quotations chosen well and explained.\n"
                                                   "AO3 writing: paragraphs that link; accurate spelling and punctuation."})),
           B("rb_ask_me", TEXT=L("Paste the essay")),
           v.set("essay", B("rb_answer")),
           B("rb_task", TEXT=join("Write feedback on this essay for the pupil who wrote it, using the mark scheme. Say what works first, "
                                  "then what would lift it, quoting the essay. End with exactly two next steps.\n\nMark scheme:\n",
                                  v.get("mark scheme"), "\n\nEssay:\n", v.get("essay"))),
           B("rb_generate"),
           B("rb_reflect", CRITERIA=L("every point refers to something in the mark scheme; kind, and talks to the pupil; specific, quoting "
                                      "the essay; ends with exactly two next steps the pupil can act on; no mark or grade; under 200 words"),
             ROUNDS=3, FIX=B("rb_revise")),
           if_(B("rb_approve", TEXT=join("Feedback ready. Save it?\n\n", B("rb_draft"))),
               chain(B("rb_ask_first", {"WHAT": "files"}), B("rb_file_save", {"EXT": "md"}, VALUE=B("rb_draft"), NAME="essay-feedback"),
                     B("rb_result")),
               B("rb_finish_with", TEXT=join("Not saved. The draft, to edit yourself:\n\n", B("rb_draft")))))], v))

v = Vars("text", "level")
add(program(
    "three-levels", "Three reading levels", "learning",
    "One text as three worksheets, for reading ages of about 7, 10 and 13. Each keeps the facts and is checked against its reading "
    "age, with three questions at the end. Saved as one file to print.",
    "Change the reading ages in the list block to suit your class.",
    [chain(hat("rb_start"),
           B("rb_ask_me", TEXT=L("Paste the text to make worksheets from")),
           v.set("text", B("rb_answer")),
           B("controls_forEach", {"VAR": {"id": v.ids["level"]}},
             LIST={**B("lists_create_with", ADD0="7", ADD1="10", ADD2="13"), "extraState": {"itemCount": 3}},
             DO=chain(B("rb_task", TEXT=join("Rewrite this text as a worksheet for a reading age of about ", v.get("level"),
                                             ". Keep every fact. Add a title, and three questions at the end, the last one asking the "
                                             "reader what they think.\n\n", v.get("text"))),
                      B("rb_generate"),
                      B("rb_reflect", CRITERIA=join("reads at about a reading age of ", v.get("level"), "; every fact from the original is "
                                                    "still there and still right; no fact added; short paragraphs; three questions at the end"),
                        ROUNDS=3, FIX=B("rb_revise")),
                      B("rb_add_result", TEXT=join("Reading age ", v.get("level"), "\n\n", B("rb_draft"))))),
           B("rb_ask_first", {"WHAT": "files"}),
           B("rb_file_save", {"EXT": "md"}, VALUE=B("rb_result_text"), NAME="worksheets"),
           B("rb_result"))], v))

v = Vars("plan")
add(program(
    "parent-update", "Parent update", "learning",
    "Paste this week's lesson plan. Claude writes a warm note to parents, under 150 words, with one thing to try at home, and "
    "you approve it before it's emailed.",
    "Change the email address to your parents' list. No pupil is ever named.",
    [chain(hat("rb_start"),
           B("rb_ask_me", TEXT=L("Paste this week's lesson plan")),
           v.set("plan", B("rb_answer")),
           B("rb_task", TEXT=join("Write this week's note to parents from the lesson plan: what the class learned, in everyday words, and "
                                  "one thing they could try at home.\n\nLesson plan:\n", v.get("plan"))),
           B("rb_generate"),
           B("rb_reflect", CRITERIA=L("warm and friendly; under 150 words; no teaching jargon; one thing to try at home; no pupil named"),
             ROUNDS=3, FIX=B("rb_revise")),
           if_(B("rb_approve", TEXT=join("Email this to parents?\n\n", B("rb_draft"))),
               chain(B("rb_ask_first", {"WHAT": "messages"}),
                     B("rb_email_send", TO="parents@example.com", SUBJECT="This week in class", TEXT=B("rb_draft")),
                     B("rb_result")),
               B("rb_finish_with", TEXT=join("Not sent. The draft, to edit yourself:\n\n", B("rb_draft")))))], v))

add(program(
    "quiz-from-notes", "Quiz from notes", "learning",
    "Choose your lesson notes. Claude writes a ten-question quiz from them, with the answers, and for each question the wrong "
    "answer pupils most often give and why it's wrong. Saved to print.",
    "Works with a PDF, Word file or text file. Ask for fewer questions in the blue block for a quick starter.",
    [chain(hat("rb_start"),
           B("rb_task", TEXT=join("Write a ten-question quiz from these lesson notes. Mix recall and understanding. After the questions, "
                                  "an answer section: for each question the answer, the wrong answer pupils most often give, and one "
                                  "sentence on why it's wrong.\n\nNotes:\n", B("rb_file_choose"))),
           B("rb_generate"),
           B("rb_reflect", CRITERIA=L("every question can be answered from the notes; each has one right answer; the common wrong answers "
                                      "are ones pupils really give, not silly ones; answers kept apart from the questions"),
             ROUNDS=3, FIX=B("rb_revise")),
           B("rb_ask_first", {"WHAT": "files"}),
           B("rb_file_save", {"EXT": "md"}, VALUE=B("rb_draft"), NAME="quiz"),
           B("rb_result"))]))

# ----- Food businesses (#197): the 14 allergens, the fridge's 0–5 °C, a house style -----
ALLERGENS = ("celery; cereals containing gluten (wheat, rye, barley, oats); crustaceans; eggs; fish; lupin; milk; molluscs; mustard; "
             "tree nuts; peanuts; sesame; soya; sulphur dioxide and sulphites")
add(program(
    "allergen-check", "Allergen check", "home",
    "Paste a recipe card. Claude checks it against the UK's 14 allergens: which each ingredient contains, 'may contain' wording to "
    "look at, and anything the card should declare but doesn't. A second pair of eyes, not a guarantee.",
    "Paste the ingredients with any sub-recipes (the stock, the sauce): allergens hide there.",
    [chain(hat("rb_start"),
           B("rb_ask_me", TEXT=L("Paste the recipe card, with its ingredients and any allergen statement")),
           B("rb_task", TEXT=join("Check this recipe card against the UK's 14 allergens (" + ALLERGENS + "). Give: a table of each "
                                  "ingredient and the allergens it contains; any 'may contain' or 'made in a kitchen that' wording, and "
                                  "what it would cover; and allergens the card should declare but doesn't. End with the full list to "
                                  "declare, in bold.\n\nRecipe card:\n", B("rb_answer"))),
           B("rb_generate"),
           B("rb_reflect", CRITERIA=L("names all 14 allergens, saying for each whether it's present; every ingredient that contains one "
                                      "is named; sub-recipes and processed ingredients (stock, sauces, bread) are checked; anything "
                                      "unclear says what to ask the supplier; says it is a check to confirm, not a guarantee"),
             ROUNDS=3, FIX=B("rb_revise")),
           B("rb_result"))]))

v = Vars("log")
add(program(
    "fridge-log", "Fridge log", "home",
    "Each evening, drafts the day's fridge and freezer temperature log from Home Assistant sensors, flagging any reading outside "
    "0–5 °C for the fridge or above −18 °C for the freezer, with the time and what to do. Saved for you to sign.",
    "Change the sensors to yours. The log is a draft to check against the thermometer, not a replacement for it.",
    start_and(when_time(18, 0), msg="log") + [receive(
        "log",
        v.set("log", B("rb_ask", TEXT=join(
            "Draft today's temperature log for a food business from these readings. A table: time, fridge °C, freezer °C, OK or not. "
            "Flag every fridge reading outside 0 to 5 °C and every freezer reading above −18 °C, with the time and the usual action "
            "(check the door and seals, move food, call the engineer). Then a line for 'Checked by' and 'Action taken', left blank. "
            "Today is ", B("rb_now", {"PART": "date"}), ".\n\nFridge, last 24 hours:\n",
            B("rb_ha_history", ENTITY="sensor.fridge_temperature", HOURS=24),
            "\n\nFreezer, last 24 hours:\n", B("rb_ha_history", ENTITY="sensor.freezer_temperature", HOURS=24)))),
        B("rb_ask_first", {"WHAT": "files"}),
        B("rb_file_save", {"EXT": "md"}, VALUE=v.get("log"), NAME=join("fridge-log-", B("rb_now", {"PART": "date"}))),
        B("rb_finish_with", TEXT=v.get("log")))], v))

v = Vars("house style")
add(program(
    "menu-writer", "Menu writer", "home",
    "List your dishes and what's in them. Claude writes each one a menu description in your house style, 25 words or fewer, with "
    "its allergens from the UK's 14 listed underneath.",
    "Describe your house style in the first block: a few words and one description you like.",
    [chain(hat("rb_start"),
           v.set("house style", B("rb_longtext", {"TEXT": "Plain and warm. Say where things come from. No 'delicious', 'homemade' or "
                                                   "'mouth-watering'. Like: Rye sourdough, 48-hour ferment, with Netherend butter."})),
           B("rb_ask_me", TEXT=L("List the dishes, each with what's in it")),
           B("rb_task", TEXT=join("Write a menu description for each dish, in this house style:\n", v.get("house style"),
                                  "\nUnder each, list the allergens it contains from the UK's 14 (" + ALLERGENS + ").\n\nDishes:\n",
                                  B("rb_answer"))),
           B("rb_generate"),
           B("rb_reflect", CRITERIA=join("each description 25 words or fewer; in the house style; every dish lists its allergens, and only "
                                         "ones its ingredients really contain; nothing claimed that the ingredients don't say"),
             ROUNDS=3, FIX=B("rb_revise")),
           B("rb_result"))], v))

v = Vars("changes")
add(program(
    "supplier-price-watch", "Supplier price watch", "home",
    "Watches a supplier's price list page. When a price moves by more than 5%, you get an email with the item, the old and new "
    "price and the change. Smaller moves are ignored.",
    "Change the page address in the hat to your supplier's price list. It asks before its first email.",
    start_and(hat("rb_page_when", {"URL": "https://example.com/supplier/price-list", "WORDS": "£", "N": 360}), msg="prices",
              value=B("rb_event", {"KEY": "text"}), test="Type a change to test with, like '- Rye flour 25kg £21.00' then '+ Rye flour 25kg £23.50'") + [
        receive(
            "prices",
            if_(B("rb_ask_yesno", TEXT=join("This is how a supplier's price list changed. Lines starting - are before, + after. Did any "
                                            "item's price change by more than 5%?\n\n", B("rb_msg_value"))),
                chain(v.set("changes", B("rb_ask", TEXT=join(
                          "List each item whose price changed by more than 5%: the item, old price → new price, and the change as a "
                          "percentage. Biggest change first. Nothing else.\n\n", B("rb_msg_value")))),
                      B("rb_ask_first", {"WHAT": "messages"}),
                      email_me("Supplier prices moved", v.get("changes")),
                      B("rb_finish_with", TEXT=v.get("changes"))),
                B("rb_finish_with", TEXT="No price moved by more than 5%.")))], v))

# ----- Plain English and accessibility (#198): a reading age, a jargon list, alt-text guidance, easy-read rules -----
add(program(
    "plain-english", "Plain English", "odds",
    "Paste a letter or notice. Claude rewrites it until it passes a plain-English check: a reading age of about 9 to 11, no "
    "jargon, short sentences, and every fact, date and amount kept.",
    "Paste one letter at a time. Read the result against the original before you send it.",
    [chain(hat("rb_start"),
           B("rb_ask_me", TEXT=L("Paste the letter or notice")),
           B("rb_task", TEXT=join("Rewrite this in plain English for anyone to read. Use 'you' and 'we'. Put the most important thing "
                                  "first.\n\n", B("rb_answer"))),
           B("rb_generate"),
           B("rb_reflect", CRITERIA=L("reading age of about 9 to 11; no jargon, or any term that must stay is explained; sentences "
                                      "average 15 to 20 words and none is over 30; active voice; every fact, date, amount and deadline "
                                      "from the original is kept and right; what the reader needs to do is clear"),
             ROUNDS=4, FIX=B("rb_revise")),
           B("rb_result"))]))

v = Vars("alt")
add(program(
    "alt-text-folder", "Alt text for a folder", "odds",
    "Watches a folder. For each new picture, Claude writes alt text, checks it against accessibility guidance (short, says what "
    "matters, includes any words in the picture), and adds it to a file, asking before it writes.",
    "Change the folder to where your website's pictures go. Every picture is sent to the model.",
    [chain(hat("rb_folder_when", {"FOLDER": "~/Pictures/For the website"}),
           B("rb_broadcast_with_wait", MSG="picture", VALUE=B("rb_event", {"KEY": "picture"}))),
     chain(hat("rb_start"), B("rb_broadcast_with_wait", MSG="picture", VALUE=B("rb_img_choose"))),
     receive(
         "picture",
         B("rb_set_draft", TEXT=B("rb_img_ask", TEXT=L(
             "Write alt text for this picture, for someone using a screen reader: what matters about it in one or two short "
             "sentences. Include any words in the picture. Don't start with 'image of' or 'picture of'."), IMG=B("rb_msg_value"))),
         B("rb_reflect", CRITERIA=L("under 125 characters, or two short sentences if there's text in the picture; says what matters, not "
                                    "every detail; any words in the picture are included; doesn't start 'image of' or 'picture of'; "
                                    "doesn't guess who people are"), ROUNDS=2, FIX=B("rb_revise")),
         v.set("alt", join(B("rb_now", {"PART": "datetime"}), ": ", B("rb_draft"))),
         B("rb_mem_add", {"KIND": "permanent"}, VALUE=v.get("alt"), NAME="alt text"),
         B("rb_ask_first", {"WHAT": "files"}),
         B("rb_file_save", {"EXT": "md"}, VALUE=B("rb_mem_get", NAME="alt text"), NAME="alt-text"),
         B("rb_finish_with", TEXT=B("rb_draft")))], v))

add(program(
    "easy-read", "Easy read", "odds",
    "Choose a document. Claude makes an easy-read version: one idea per sentence, everyday words, a heading every few points and "
    "a suggested picture for each, checked against easy-read guidance. Saved to print.",
    "Easy read is for people with learning disabilities. Ask someone who uses it to check the result.",
    [chain(hat("rb_start"),
           B("rb_task", TEXT=join("Make an easy-read version of this document. Keep what the reader needs to know or do; leave out the "
                                  "rest. For each point, suggest a picture in [square brackets] before it.\n\n", B("rb_file_choose"))),
           B("rb_generate"),
           B("rb_reflect", CRITERIA=L("one idea per sentence; sentences of 15 words or fewer; everyday words, with any hard word "
                                      "explained; a heading every three to five points; a suggested picture for each point; numbers "
                                      "written as digits; nothing the reader needs is left out"),
             ROUNDS=3, FIX=B("rb_revise")),
           B("rb_ask_first", {"WHAT": "files"}),
           B("rb_file_save", {"EXT": "md"}, VALUE=B("rb_draft"), NAME="easy-read"),
           B("rb_result"))]))

# ----- Charities and volunteer groups (#199): the funder's criteria, availability, the minutes -----
v = Vars("criteria", "application", "criterion")
add(program(
    "grant-check", "Grant check", "odds",
    "Paste the funder's criteria, then choose your application. Claude checks the application against each criterion in turn, "
    "quoting where it meets it and saying what's missing, then gives the three changes that would help most.",
    "Copy the criteria from the funder's guidance word for word. It checks; it doesn't rewrite your application.",
    [chain(hat("rb_start"),
           B("rb_ask_me", TEXT=L("Paste the funder's criteria")),
           v.set("criteria", B("rb_ask_list", TEXT=join("List each separate criterion in this funder's guidance, in its own words, one "
                                                         "per item:\n\n", B("rb_answer")))),
           v.set("application", B("rb_file_choose")),
           B("controls_forEach", {"VAR": {"id": v.ids["criterion"]}}, LIST=v.get("criteria"),
             DO=chain(B("rb_set_draft", TEXT=B("rb_ask", TEXT=join(
                          "Does this grant application meet this criterion? Say MEETS, PARTLY or MISSING, quote the part of the "
                          "application that meets it, and say in one sentence what's missing.\n\nCriterion: ", v.get("criterion"),
                          "\n\nApplication:\n", v.get("application")))),
                      B("rb_reflect", CRITERIA=L("quotes the application word for word; the verdict fits the quote; says what's missing "
                                                 "in one sentence; doesn't invent anything the application doesn't say"),
                        ROUNDS=2, FIX=B("rb_revise")),
                      B("rb_add_result", TEXT=join(v.get("criterion"), "\n", B("rb_draft"))))),
           B("rb_add_result", TEXT=B("rb_ask", TEXT=join(
               "From these checks of a grant application against each criterion, give the three changes that would help it most, most "
               "important first.\n\n", B("rb_result_text")))),
           B("rb_result"))], v))

add(program(
    "volunteer-rota", "Volunteer rota", "calendar",
    "Drafts next month's volunteer rota from the shifts in your calendar and the availability people emailed you, fairly shared, "
    "and asks you to approve it before emailing it round.",
    "Put the shifts in a calendar it can read, and ask volunteers to reply to one email with their dates. Change the address to your list.",
    [chain(hat("rb_start"),
           agent(L("Draft next month's volunteer rota. Read the calendar for next month's shifts (calendar with days 40). Search my email "
                   "from the last 21 days for volunteers' availability replies and read them. Give each shift its volunteers: only "
                   "people who said they're free then, shared out as evenly as you can, nobody on two shifts in one day. List any shift "
                   "still short of people at the top. Then a table by date. Check it with review_text against: every name is someone "
                   "who said they were free; no shift has someone twice; shifts with too few people are listed first."),
                 ["calendar", "email", "review"], steps=16),
           if_(B("rb_approve", TEXT=join("Email this rota to the volunteers?\n\n", B("rb_draft"))),
               chain(B("rb_ask_first", {"WHAT": "messages"}),
                     B("rb_email_send", TO="volunteers@example.com", SUBJECT="Next month's rota", TEXT=B("rb_draft")),
                     B("rb_result")),
               B("rb_finish_with", TEXT=join("Not sent. The draft, to edit yourself:\n\n", B("rb_draft")))))]))

add(program(
    "minutes-to-actions", "Minutes to actions", "odds",
    "Choose the minutes of a trustees' or committee meeting. Claude lists every action with its owner and date, flags any with no "
    "owner or no date, and saves the list to send round.",
    "Works with a PDF, Word file or text file. It only lists what the minutes say: anything unclear is flagged, not guessed.",
    [chain(hat("rb_start"),
           B("rb_task", TEXT=join("List every action agreed in these meeting minutes: the action, who owns it and when it's due, as a "
                                  "table, by owner. Under the table, list actions with no owner or no date as NEEDS AN OWNER or NEEDS A "
                                  "DATE.\n\nMinutes:\n", B("rb_file_choose"))),
           B("rb_generate"),
           B("rb_reflect", CRITERIA=L("every action in the minutes is listed; owners and dates are exactly as the minutes say, never guessed; "
                                      "anything without an owner or date is flagged; decisions that aren't actions are left out"),
             ROUNDS=3, FIX=B("rb_revise")),
           B("rb_ask_first", {"WHAT": "files"}),
           B("rb_file_save", {"EXT": "md"}, VALUE=B("rb_draft"), NAME="actions"),
           B("rb_result"))]))

# ----- Small professional practices, admin not advice (#200): a deadline, a checklist, a reply-by date -----
add(program(
    "sar-triage", "Subject access requests", "calendar",
    "Each weekday morning, finds emails that look like subject access requests (someone asking for the personal data you hold "
    "about them) and emails you a list with the date each arrived and its one-month deadline. Admin help, not legal advice.",
    "The one-month deadline can be extended in some cases. Check each request yourself; this only makes sure none is missed.",
    start_and(when_time(8, 30, "weekdays"), msg="sar") + [receive(
        "sar",
        agent(L("Search my email from the last 35 days for subject access requests: anyone asking for a copy of the personal data or "
                "information we hold about them, however they word it. Read the likely ones. For each real one: who, the date it "
                "arrived, the deadline one calendar month later (use time_plus), and how many days are left. Soonest deadline first. "
                "Leave out anything that isn't a request for someone's own data. If there are none, say so in one line. End with: "
                "'This is an admin reminder, not legal advice.'"), ["email", "time"], steps=14),
        B("rb_ask_first", {"WHAT": "messages"}),
        email_me("Subject access requests: deadlines", B("rb_draft")),
        B("rb_result"))]))

v = Vars("checklist")
add(program(
    "clause-checklist", "Clause checklist", "odds",
    "Choose a contract. Claude checks it against your clause checklist and lists, for each item, whether it's there (quoting it), "
    "unclear or missing, for a professional to review. It isn't advice, and it says so.",
    "Put your own checklist in the first block. Use it to prepare for a review, never instead of one.",
    [chain(hat("rb_start"),
           v.set("checklist", B("rb_longtext", {"TEXT": "Parties named in full\nTerm and how to end it\nPayment terms and late payment\n"
                                                 "Limitation of liability\nConfidentiality\nData protection\nGoverning law\n"
                                                 "Dispute resolution"})),
           B("rb_task", TEXT=join("For each item on this checklist, say whether this contract has a clause covering it: PRESENT (quote "
                                  "the clause and give its number), UNCLEAR (say why) or MISSING. Don't give an opinion on whether a "
                                  "clause is good. End with: 'For a professional to review. This is not legal advice.'\n\nChecklist:\n",
                                  v.get("checklist"), "\n\nContract:\n", B("rb_file_choose"))),
           B("rb_generate"),
           B("rb_reflect", CRITERIA=L("every checklist item has a verdict; every PRESENT quotes the contract word for word with its clause "
                                      "number; no opinion on whether terms are fair or wise; ends with the not-advice line"),
             ROUNDS=3, FIX=B("rb_revise")),
           B("rb_result"))], v))

add(program(
    "reply-deadlines", "Reply deadlines", "calendar",
    "Each Monday morning, finds client emails that still need a reply, with the date each one asked for or the date you'd "
    "reasonably owe one, soonest first. Emailed to you; it never replies.",
    "Tell it who your clients are in the agent's goal (a domain, or the words in their signatures) to cut out newsletters.",
    [*start_and(msg="replies"), on_day("Monday", 8, 0, "replies"), receive(
        "replies",
        agent(L("Search my email from the last 14 days for messages from clients that ask for something and haven't had a reply from "
                "me yet. Read them. For each: who, what they need, and the reply-by date: the date they asked for, or else five working "
                "days after it arrived (use time_plus). Soonest first, overdue ones marked OVERDUE. Leave out newsletters, receipts and "
                "anything already answered. Don't reply to anything."), ["email", "time"], steps=16),
        B("rb_ask_first", {"WHAT": "messages"}),
        email_me("Replies due this week", B("rb_draft")),
        B("rb_result"))]))

# ----- Local news and civic groups (#201): a postcode, a source for every claim, two versions of a document -----
v = Vars("postcode")
add(program(
    "planning-digest", "Planning digest", "news",
    "Each Friday, a digest of new planning applications near a postcode: what's proposed, where, and the date comments close, "
    "with a link for each. Nothing without a source.",
    "Change the postcode in the first block. Councils publish differently, so check the first digest against your council's portal.",
    [*start_and(msg="planning"), on_day("Friday", 7, 30, "planning"), receive(
        "planning",
        v.set("postcode", B("text", {"TEXT": "SE1 7PB"})),
        agent(join("Find planning applications submitted in the last week within about a mile of ", v.get("postcode"), ". Search the "
                   "web (the local council's planning portal, and planning news sites) and read the pages. For each: the address, what's "
                   "proposed in one plain sentence, the reference, the date comments close, and the link. Recall the note 'planning "
                   "seen' and leave out applications already in it, then remember this week's references as 'planning seen'. Check it "
                   "with review_text against: every application has a link; nothing invented; plain English."),
              ["web", "memory", "review"], steps=16),
        email_me("Planning applications near you", B("rb_draft")),
        B("rb_result"))], v))

v = Vars("claim")
add(program(
    "sourced-check", "Sourced check", "news",
    "Type a claim. Claude searches the web and says whether good sources support it, contradict it or don't say, with a link "
    "for every point. It refuses to give a verdict it can't source.",
    "Uses web search, which only works in exported Python; on the page Claude says what it would look up.",
    [chain(hat("rb_start"),
           B("rb_ask_me", TEXT=L("Type the claim to check")),
           v.set("claim", B("rb_answer")),
           B("rb_task", TEXT=join("Check this claim against these search results. Verdict first: SUPPORTED, CONTRADICTED, MIXED or NOT "
                                  "ENOUGH TO SAY. Then the evidence, each point with its link. If the results don't settle it, say NOT "
                                  "ENOUGH TO SAY and what a reader could check.\n\nClaim: ", v.get("claim"), "\n\nSearch results:\n",
                                  B("rb_web_search", TEXT=v.get("claim")))),
           B("rb_generate"),
           B("rb_reflect", CRITERIA=L("every point has a link from the search results; no link is invented; the verdict follows from the "
                                      "sourced points only; NOT ENOUGH TO SAY if the sources don't settle it"),
             ROUNDS=3, FIX=B("rb_revise")),
           B("rb_result"))], v))

v = Vars("before", "after")
add(program(
    "consultation-diff", "Consultation changes", "news",
    "Choose two versions of a consultation or policy document. Claude lists what changed between them, in plain English, most "
    "important first, quoting both versions for each change.",
    "Choose the older version first. Works with PDFs, Word files and text files.",
    [chain(hat("rb_start"),
           B("rb_say", TEXT="Choose the older version first."),
           v.set("before", B("rb_file_choose")),
           v.set("after", B("rb_file_choose")),
           B("rb_task", TEXT=join("List what changed between these two versions of a document: what was added, removed or reworded in a way "
                                  "that changes its meaning. Most important first. For each, quote the old and the new wording, then one "
                                  "plain sentence on what the change means. Leave out changes to layout, spelling and numbering.\n\nOLDER "
                                  "VERSION:\n", v.get("before"), "\n\nNEWER VERSION:\n", v.get("after"))),
           B("rb_generate"),
           B("rb_reflect", CRITERIA=L("every change quotes both versions word for word; nothing listed that didn't change; changes of "
                                      "meaning only; the most important first; plain English"),
             ROUNDS=3, FIX=B("rb_revise")),
           B("rb_result"))], v))


# ----- Archives and family history (#202): transcription conventions, the calendar change, a cataloguing standard -----
add(program(
    "letter-transcriber", "Letter transcriber", "odds",
    "Choose a scan or photo of a handwritten letter. Claude transcribes it as written, old spellings and all, marks every word "
    "it isn't sure of, and checks the transcription against the usual conventions. Asks before saving it.",
    "Use a clear, flat scan. Read it against the original: every [word?] is a guess to check.",
    [chain(hat("rb_start"),
           B("rb_set_draft", TEXT=B("rb_img_ask", TEXT=L(
               "Transcribe this handwritten document exactly as written. Keep the original spelling, capitals, punctuation and "
               "abbreviations; don't modernise or correct anything. Keep the line breaks. Put a word you're unsure of in square "
               "brackets with a question mark, like [Thomas?]; write [illegible] for anything you can't read, and [torn] or "
               "[blot] for damage. Put words written above the line in ^carets^. After the transcription, a line '---' and a "
               "short note: the likely date and writer if the letter says, and how confident you are overall."),
               IMG=B("rb_img_choose"))),
           B("rb_reflect", CRITERIA=L("spelling, capitals and punctuation are as written, not modernised; abbreviations are kept, not "
                                      "expanded; every uncertain word is marked [word?]; unreadable parts say [illegible]; line breaks "
                                      "are kept; nothing is added that isn't on the page; the note after '---' says how confident it is"),
             ROUNDS=2, FIX=B("rb_revise")),
           if_(B("rb_approve", TEXT=join("Save this transcription?\n\n", B("rb_draft"))),
               chain(B("rb_ask_first", {"WHAT": "files"}), B("rb_file_save", {"EXT": "md"}, VALUE=B("rb_draft"), NAME="transcription"),
                     B("rb_result")),
               B("rb_finish_with", TEXT=join("Not saved. The transcription, to edit yourself:\n\n", B("rb_draft")))))]))

v = Vars("text")
add(program(
    "old-dates", "Old dates", "odds",
    "Paste a passage from an old document. Claude finds every date in it and gives each in today's form: abbreviations like "
    "inst. and 7ber expanded, regnal years worked out, and Old Style dates before 1752 given in both styles.",
    "It shows its working for each date. Check regnal years against a list of reigns before you rely on one.",
    [chain(hat("rb_start"),
           B("rb_ask_me", TEXT=L("Paste the passage with the dates in it")),
           v.set("text", B("rb_answer")),
           B("rb_task", TEXT=join(
               "Find every date in this passage from an old English document and give each in today's form (day month year). For "
               "each: quote it as written, then the modern date, then one line of working. Expand abbreviations: inst. (this month), "
               "ult. (last month), prox. (next month), 7ber, 8ber, 9ber, Xber (September to December). Work out regnal years (like "
               "'the 3rd year of the reign of George III') from the date the reign began. In England before 1752 the year began on "
               "25 March, so a date from 1 January to 24 March is given as both years, like 10 February 1720/21; the Julian "
               "calendar was used until 2 September 1752, so also give the Gregorian date: 11 days later from 1 March 1700, 10 days before that. "
               "Say when a date can't be worked out exactly, and why.\n\n", v.get("text"))),
           B("rb_generate"),
           B("rb_reflect", CRITERIA=L("every date in the passage is listed, quoted as written; each has a modern date and a line of "
                                      "working; dates between 1 January and 24 March before 1752 show both years, like 1720/21; Julian "
                                      "dates before 1752 also give the Gregorian date; regnal years name the reign and when it began; "
                                      "anything uncertain says so"),
             ROUNDS=3, FIX=B("rb_revise")),
           B("rb_result"))], v))

v = Vars("item", "reference")
add(program(
    "catalogue-entry", "Catalogue entry", "odds",
    "Choose a transcription or description of an archive item. Claude drafts a catalogue entry with the elements ISAD(G) needs, "
    "checks it against them, and asks before saving. It never invents a date or a creator the item doesn't give.",
    "Put your own reference code and repository in the answer to the first question.",
    [chain(hat("rb_start"),
           B("rb_ask_me", TEXT=L("The reference code and repository, like 'ABC/1/2, Anytown Record Office'")),
           v.set("reference", B("rb_answer")),
           v.set("item", B("rb_file_choose")),
           B("rb_task", TEXT=join(
               "Draft an archive catalogue entry for this item, following ISAD(G). Give these elements, each on its own line with "
               "its name: Reference code; Title; Date(s); Level of description; Extent and medium; Name of creator(s); Scope and "
               "content; Conditions governing access; Language/scripts of material. Use only what the item shows: write 'not "
               "known' rather than guess, and give dates as the item states them, with any you've inferred in square brackets. "
               "Scope and content is a few plain sentences: who, what, where, when.\n\nReference and repository: ",
               v.get("reference"), "\n\nThe item:\n", v.get("item"))),
           B("rb_generate"),
           B("rb_reflect", CRITERIA=L("all nine ISAD(G) elements are there, each named; nothing is invented: unknowns say 'not known' and "
                                      "inferred dates are in square brackets; dates are as the item gives them; scope and content says "
                                      "who, what, where and when in plain sentences; the reference code is the one given"),
             ROUNDS=3, FIX=B("rb_revise")),
           if_(B("rb_approve", TEXT=join("Save this catalogue entry?\n\n", B("rb_draft"))),
               chain(B("rb_ask_first", {"WHAT": "files"}), B("rb_file_save", {"EXT": "md"}, VALUE=B("rb_draft"), NAME="catalogue-entry"),
                     B("rb_result")),
               B("rb_finish_with", TEXT=join("Not saved. The entry, to edit yourself:\n\n", B("rb_draft")))))], v))


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
