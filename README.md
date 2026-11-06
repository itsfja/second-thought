# Second Thought

[![CI](https://github.com/itsfja/second-thought/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/itsfja/second-thought/actions/workflows/ci.yml)
[![Runtime](https://img.shields.io/badge/runtime-3.9.2-blue)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.9%E2%80%933.13-blue)](.github/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Scratch-style blocks for building AI workflows that check their own work.** Snap together steps like *draft*, *review against these rules*, *revise* and *use these tools*, press Run, and watch each block do its job. When a program does what you want, export it as a single Python file that runs on its own: on a schedule, from a webhook, in Telegram or Home Assistant. It works with Claude, Gemini, GPT, Llama on your own computer, and a dozen other models.

![Building and running a review loop, then exporting it to Python](screenshots/demo.gif)

**Try it in three steps**

1. **Open [Second Thought](https://claude.ai/artifact/XmNRmDbYLY3bo7o31nvdzN)** in claude.ai. Nothing to install, and runs on the page use your claude.ai account.

   There's also a copy at **[itsfja.github.io/second-thought](https://itsfja.github.io/second-thought/)**, updated with each release. It builds programs, tries them on sample data, explains and exports them. To run them with Claude there, press **Use your own API key** and paste an Anthropic API key (from [console.anthropic.com](https://console.anthropic.com)): runs are charged to that key's account. The key goes only from your browser to api.anthropic.com, is kept until you close the tab unless you tick **Remember on this browser**, and is never put in a saved program, an export or the run log; **Forget my key** removes it. Or use the page on claude.ai, which needs no key. Exported Python runs anywhere either way.
2. **Pick an example and press Run.** There are over 150, from a simple review loop to agents that plan a bake or check on the house. Change the text in any block and run it again.
3. **Export it.** *Import / export → Save Python (.zip)*, unzip, put your API key in `second-thought.ini`, then run `run.bat` (Windows) or `sh run.sh` (Linux, Mac). [Exporting to Python](#exporting-to-python) has the details.

New to all this? [**The picture book**](docs/ladybird-book.md) is a gentle, Ladybird-style introduction to what Second Thought is and why it checks its own work.

**Contents:** [Using the page](#using-the-page) · [What a program can do](#what-a-program-can-do) · [The agent](#the-agent) · [Connections](#connections) · [Examples and the gallery](#examples-and-the-gallery) · [Saving programs](#saving-programs) · [Exporting to Python](#exporting-to-python) · [Models](#models) · [Home Assistant](#home-assistant) · [Homey](#homey) · [MCP tools](#mcp-tools) · [Languages](#languages) · [Versions and --doctor](#versions-and---doctor) · [Good to know](#good-to-know) · [Repository layout](#repository-layout) · [Development and tests](#development-and-tests)

---

## Using the page

Each block is one instruction, like *write a first draft*, *review the draft against …* or *revise to fix the review's problems*. Drag blocks from the categories on the left and click them together. Only blocks under a **when Run is clicked** or **when I receive** hat run, top to bottom; separate scripts run side by side. Click any white slot to type into it. Round slots take values, hexagon slots take yes/no conditions.

The blocks are colour-coded by job:

- **Yellow** starts things. **when Run is clicked** goes at the top.
- **Orange** repeats or chooses.
- **Blue** asks Claude to write.
- **Purple** asks Claude to check the writing.
- **Teal** asks *you* a question and waits for your answer.
- **Olive** makes an [agent](#the-agent), a helper that decides its own steps. Its tools are a darker olive, in their own **Tools** category.
- **Pink**, under **Connections**, talks to Telegram, email, your calendar and news feeds.
- **Green** shows the result.

There are more categories down the left side of the screen.

**Describing a program.** Instead of dragging blocks, type what you want in the box above the canvas, like *every Friday at 6pm, find the best two hours this weekend to dry washing and send it to me on Telegram*, and press **Build it**. Claude builds the blocks. Before anything loads, the page says what the program does, how many blocks it has, what it can do (send messages, control devices and so on, worked out from the blocks), and anything it left out. **Load it** puts it on the canvas, and **Undo** puts your old program back. To change the program on the canvas, describe the change (*also email it to me*) and press **Change this program**. Claude uses the same block list as converting code, and a program with blocks the page doesn't have is refused. It uses your Claude usage, like any run.

**Running.** Press **Run**. The **run log** on the right adds an entry as each block does its job, and a green box at the end shows the result. Under each step that asks a model something, a grey line says which model answered, how long it took and roughly how many tokens it used; click **Prompt sent** to see exactly what it was asked. Under the result is an estimate of the run's total tokens (on the page this is estimated from the length of the text; exported Python reports exact counts), and what that would cost at the models' list prices, in US dollars. On the page the run counts toward your Claude usage instead; exported Python's last line gives the cost from the exact counts, like *about $0.03 at list prices*. Prices are kept for the services whose prices have been checked; a run using any other model shows no cost rather than a wrong one, and web searches and other per-request charges aren't included. **Save log** keeps every step, its timing and the result as a file. **Stop** stops everything at once.

**With the keyboard, or a screen reader.** Every button, menu and panel works with **Tab** and **Enter**. When a run asks you something, the answer box takes the focus and a screen reader reads the question; **Ctrl+Enter** sends a typed answer. New steps in the run log, and the run's status, are read out as they happen. Programs can be built without a mouse too, using Blockly's own keyboard navigation, always on: **Tab** to the block editor, **T** opens the blocks, the arrow keys move, **Enter** adds a block or edits a field, and **M** moves a block. The **?** button by the zoom buttons lists every key. A screen reader reads out each block, field and category as you reach it.

**Backups.** The **Model** menu picks the main model. **Backups**, next to it, lists spare models: if the main one can't answer (its key is missing, or the service is down), the first backup does that step instead, and the run log says so.

---

## What a program can do

- Write, check, then try again until the writing passes. If it runs out of tries, it keeps the best attempt, not the last, and each check makes sure earlier problems haven't come back.
- **Save a checkpoint** when the draft is good, and **go back to the checkpoint** if later changes make it worse.
- Ask you questions and wait for your answer.
- Look at a picture you give it and describe it, or draw simple pictures.
- Read a document, such as a PDF or a Word file.
- Save its work as a file.
- **Remember** things for next time.
- Do several jobs at the same time.
- Wait until a time of day, then start a job by itself.
- Retry when something goes wrong.
- Stop itself before it uses too many tokens, or spends too much: put **limit this run to …** near the top, in tokens or US dollars.
- Ask you first before it sends a message, says something out loud, saves a file or changes something at home: use **ask me before …**.
- Use one of your saved programs as a single block: **run program … with …**, from **Programs**.
- Use other models alongside Claude, for example Claude writes and Gemini reviews. See [Models](#models).

---

## The agent

Most programs do exactly what the blocks say, in order. An **agent** is different: you give it a **goal** and some **tools**, and Claude decides what to do next. It picks a tool, looks at what happened, and picks again. When the goal is met, it writes its answer into the draft.

The olive block **agent: work toward …** holds the tools, which have their own category, **Tools**, just below **Agent**. Drop in as many as you like:

- **ask me a question**, for things only you know.
- **remember and recall notes**, to keep what it learns for next time. It can also **search its notes**, so even among hundreds it finds the right one by its content, without knowing its exact name.
- **search the web and read pages**, for things that change. It can search, then read a source page in full. Reading pages only works in exported Python, and only public pages, never addresses on your own network.
- **work out sums**, so numbers are calculated exactly, not guessed: + − × ÷, powers, brackets and rounding, like `round(350 / 500 * 100, 1)`.
- **clock times and dates**, for the time now and for adding or taking away minutes, like 09:30 plus 270 minutes. Good for working backwards from when you want bread out of the oven.
- **read a file I choose**: the agent asks you for a PDF, a Word file or a text file and reads it.
- **check text against criteria**: a separate, strict reviewer checks the agent's work and lists the problems, so the agent can fix them before it finishes.
- **news feeds**, to read the latest from news sites and blogs (RSS or Atom).
- **search LinkedIn**, through the web search. LinkedIn doesn't let programs search it directly, so this only finds what LinkedIn shows everyone.
- **calendar**, to list your events and find free time.
- **email: search and read**, and **email: send**.
- **GitHub: projects and pull requests**, to find pull requests waiting for your review and read what they change, list a project's branches and commits, and read its files. **GitHub: comment, open and label issues** comments on pull requests and issues, opens new issues, and adds labels the project already has.
- **Telegram: search my messages** and **Telegram: send**.
- **Discord: search my channels** and **Discord: send**, and the same for **Slack**. They only read and post in the channels in your settings.
- **MQTT: read topics** and **MQTT: publish**, for sensors and switches that talk MQTT (like Zigbee2MQTT).
- **Home Assistant: look at devices**, including how a sensor changed over the last day, and **control devices**. Control devices asks you before every change, because something the agent reads could try to trick it. If you trust everything it reads, choose **control devices (no asking)**.
- **tool: My Block**, to turn one of your own My Blocks into a tool. Write a clear sentence about what it does, because that sentence is all the agent knows about it. **Ask me before each use** starts ticked, so you approve before your block runs. That matters if the block changes something. Untick it for blocks that only work something out, like a calculator.
  In **input types**, say what each input must be, like `flour grams: number; water grams: number`. The types are text, number, yes/no, list and any. The agent's input is checked before your block runs; if it's wrong, for example words where a number should be, the block doesn't run and the agent is told what to fix.

Tick **make a plan first** and the agent writes a short plan with its first step, then changes it if something surprises it. The plan shows in the run log, and costs nothing extra, because it travels with the steps.

Each step is one model call, so set how many steps it may take. If it runs out of steps, the draft holds whatever it found last. If a reply comes back unreadable, or it asks for the same tool with the same input twice in a row, the agent tells it and tries again; that uses a step. Three repeats in a row and the agent stops.

An agent only reads the words tools send back. It never follows instructions inside them, and it can't unlock a door without asking you. Tools that send or change something (email, Telegram, GitHub comments, MQTT publish, controlling devices) ask you before each use, because an email, a web page or a pull request can contain words written to trick the agent. Telegram has a **send (no asking)** choice for a bot that answers on its own. Even with the no-asking tools, unlocking, opening and disarming always ask, and so do the things that could do anything when the agent chooses them: Home Assistant scripts, scenes, automations and buttons, Homey flows, and MQTT messages that say unlock, open or disarm. An agent that can see private things (email, messages, your home, memory) also asks before reading a page address it made up, since the address could carry your data away. [SECURITY.md](SECURITY.md) has the details.

When the agent finishes, the run log shows an **Agent summary**: one row per step, with the tool, what it sent, what came back, and how it went. You get it even if the run stops part-way. The block **agent's steps** gives the same as a list, for your program to check, save or have reviewed.

On the page, the feeds, GitHub, email, Telegram and the calendar use **sample** data, so you can try everything safely; nothing real is read or sent. Exported programs use your real accounts: see [Connections](#connections) for the settings.

There are 19 agent examples under **Agents** in **Browse examples**. **Agent: plan my bake** asks and remembers. **Agent with your own tool** uses a My Block. **Agent: bake timetable** works backwards with the clock. **Agent: scale a recipe** does every sum with the sums tool. **Agent: write, check, improve** fixes its work until a reviewer passes it. **Agent: check my recipe file** reads a file you choose. **Agent: research with sources** searches and reads its sources. **Agent: house check-up** and **Agent: bedtime round** look after a Home Assistant house, and the bedtime round asks before switching anything off. **Agent: news round-up** reads your feeds and skips what it showed you last time. **Agent: trip planner** checks your calendar and builds a plan with times and a budget. **Agent: pull requests for me** and **Agent: review and comment on a pull request** work with GitHub. **Agent: inbox triage** sorts your email and drafts replies. **Agent: plan my week** fits baking around your calendar. **Telegram bot that answers** replies to messages you send your bot. **Agent: find people on LinkedIn** searches LinkedIn's public pages.

---

## Connections

The pink **Connections** blocks work without an agent too.

**Listeners** start a script when something arrives:

- **when a Telegram message arrives**, for messages to your bot.
- **when a Discord message arrives** and **when a Slack message arrives**, for messages in your channels, checked every 10 seconds. Only the channels in `DISCORD_CHANNEL_ID` or `SLACK_CHANNEL_ID` count, because anyone in a server or workspace can post; the bot's own messages never count. Discord needs the bot's *Message Content Intent* turned on.
- **when an MQTT message arrives on …**, for a sensor or switch. `+` stands for one level of the topic and `#` for everything below, like `zigbee2mqtt/#`.
- **when a web request arrives at /…**, for Home Assistant automations, IFTTT, or a shortcut on your phone. Every request must carry your `WEBHOOK_SECRET`, or it's refused. Until you set one, the program doesn't listen for web requests at all. By default only the same computer can reach it; see `WEBHOOK_HOST` below to let other devices in.
- **when an email arrives containing …**, checked every 2 minutes.
- **when there's something new in feed …**, checked every 15 minutes.
- **when a file appears in folder …**, for scans, downloads or recipes you drop in. It reads the words in PDFs, Word files and text files. For a picture (PNG, JPEG, WebP or GIF), **what arrived: picture** gives the picture itself, for the picture blocks.
- **when a pull request asks for my review**, checked every 5 minutes.
- **when a new issue is opened in** `owner/name`, checked every 5 minutes (pull requests don't count), and **when a release is published in** `owner/name`, checked every 15 minutes. **what arrived** gives the issue's `number`, `title`, `body`, `author` and `labels`, or the release's `tag`, `name`, `previous_tag` and `notes`.
- **when a calendar event starts in … minutes**, for reminders.
- **when the web page … changes**, for a price, a stock notice, opening times or the council's bin page. Fill in **only the part containing …** (like `Price`) to watch just the lines with those words and the two lines after each, so adverts and visitor counters elsewhere on the page don't count. It checks every 60 minutes unless you say otherwise. The first check only remembers the page. What changed is in `changed`, with `before` and `after`. The last copy of each page is kept in `watched-pages.json`, next to the program, so a restart doesn't count every page as changed. Pages that need a browser to show their words can't be watched.

**what arrived** gives what started the script. Every listener gives `text`, which sums it up; each block's tooltip lists its other fields, like `subject` for an email or `topic` for MQTT. **Telegram message** gives a Telegram message's words, sender or chat. On the page, right-click a listener and choose **Run this script** to try it with a sample of what arrives. Listeners only listen while the exported program runs on schedule.

**Other blocks:**

- **latest MQTT message on …** reads a topic, and **publish MQTT … to topic …** sends one. With **ask me before any smart home action**, publishing asks you first.
- **send Telegram message**, **send Discord message**, **send Slack message** and **send email** send something. The Discord and Slack ones reply in the channel a message came from, or post in your first channel. With **ask me before sending messages and announcements**, they ask you first.
- **news from feed** gives a list of the latest items. Leave it empty for your own feeds.
- **calendar for the next … days** gives a list of your events.
- **files in folder … matching …** gives a list of the files in a folder, newest first (name, path, modified, size), like every `*.pdf`. It only looks; it doesn't read them.

Try **Morning briefing on Telegram** and **Email me a news digest** under Automation, and the listener examples: **Proofer too warm? (MQTT)**, **When the bread is done (web request)**, **When the flour shop emails**, **Tell me when a feed posts something useful**, **Convert recipes dropped in a folder**, **When someone asks for my review (GitHub)** and **A reminder before each event**. Press Run to try each with something you type. Under Agents, **Agent: check the sensors (MQTT)** looks over your MQTT devices.

**Settings.** An exported program's `second-thought.ini` asks only for what it uses:

- **GitHub:** `GITHUB_TOKEN`, from github.com/settings/tokens. Read access is enough to look; to comment, it also needs write access to pull requests.
- **Telegram:** in Telegram, message **@BotFather** and send `/newbot`. It gives you `TELEGRAM_BOT_TOKEN`. Then message your bot and run the program: it tells you your chat number for `TELEGRAM_CHAT_ID`. Anyone can message a bot, so it only listens to, and searches, the chats you list there. A bot only sees messages sent to it, so it can't search your other chats.
- **Email:** `EMAIL_ADDRESS` and an **app password**, not your normal password (in Gmail, it's in your Google account under Security). Gmail, iCloud, Yahoo and Fastmail find their own mail servers. For anything else, fill in `EMAIL_IMAP_HOST` and `EMAIL_SMTP_HOST`.
- **Calendar:** `CALENDAR_URL`, your calendar's private iCal address. In Google Calendar it's under Settings, your calendar, **Secret address in iCal format**. It can read your calendar, but not add to it.
- **News feeds:** `feeds = ` and the feed addresses, separated by spaces.
- **MQTT:** `MQTT_HOST`, your broker's address (for Mosquitto in Home Assistant, that's your Home Assistant), plus `MQTT_USERNAME` and `MQTT_PASSWORD` if it needs them. `MQTT_TLS = yes` makes it encrypted. It needs the paho-mqtt library, which run.bat and run.sh install.
- **Web requests:** `WEBHOOK_SECRET`, a long password, and `WEBHOOK_PORT` if 8765 is taken. Call `http://127.0.0.1:8765/<address>?key=<your secret>` from the same computer, or put the secret in an `X-Second-Thought-Key` header. The program only listens on this computer unless you add `WEBHOOK_HOST = 0.0.0.0`, which lets Home Assistant on another machine, IFTTT or your phone reach it at `http://<this computer>:8765/…`.

The agent only reads **public** web pages and feeds, never addresses on your own network, in case something it reads tries to steer it there. Your own feeds and calendar address are fine wherever they are. To let the agent read pages on your own network, add `local_pages = yes`.

To keep listening all the time, run the program with **run-on-schedule** (see [Running on a schedule](#running-on-a-schedule)). Things that arrived while it was off don't start the script: Telegram messages are kept for searching, and the email, feed, GitHub and folder listeners start from what's new after the program starts.

---

## Examples and the gallery

Choose an example from **Example** and press **Load**, or press **Browse examples** to see them all with a sentence about each and an idea for something to change. There are over 150, grouped into Writing, Research, Design, Learning, Work, Home and baking, Agents, Homey, Code and data, Automation, and ten groups of Home Assistant examples. **Review loop** is a good first one. You can't break anything: if you get in a muddle, load the example again.

The **Community** groups, straight after Writing and Research, hold programs other people made and shared, grouped by topic (GitHub, code and data, news, money, calendar and email, home and baking, teaching, odds and ends). Each says who shared it and what it can do: whether it only talks to a model, or can also send messages, keep notes or control things. The page works that out from the blocks, so it's always accurate. To share your own, see [`gallery/README.md`](gallery/README.md).

---

## Saving programs

Press **Programs**, type a name and press **Save**. Open the same panel and press **Open** to get it back. To keep a copy as a file, use **Import / export**.

A saved program can be a block, too. Put **run program "my program" with …** inside another program. The saved program runs, then hands back its result. Inside it, **message value** holds whatever you gave it. It has its own draft and its own result, so it can't interfere with yours.

There are two rules. A program can't run itself, because that would never end. And a program that uses **broadcast** blocks can't be used this way; run it on its own instead.

---

## Exporting to Python

An exported program runs on any computer by itself, with the page closed. It talks to the model services directly, so it needs an API key, and calls are billed by the service, separately from claude.ai.

Press **Import / export**, then **Save Python (.zip)**, and unzip it into a folder of its own:

| File | What it is |
|---|---|
| `my-program.py` | The program, with the runtime built in. |
| `second-thought.ini` | Settings, including keys. It lists only what *this* program needs. |
| `run.bat` | Windows: double-click to run. |
| `run.sh` | Linux or Mac: the same job as `run.bat`. |
| `requirements.txt` | The packages it needs. `run.bat` and `run.sh` install them for you. |

Open `second-thought.ini` in any text editor, put each key after its `=` sign, and save:

```
[keys]
ANTHROPIC_API_KEY = sk-ant-your-key-here
```

Keep this file private: it holds your keys.

**On Windows:** install Python from python.org (tick **Add python.exe to PATH**), then double-click `run.bat`. The first time, it installs what the program needs.

**On Linux or a Mac:** in a terminal in the folder, run:

```
sh run.sh
```

The first time, it makes a private `.venv` next to the program and installs into that, so nothing is installed for the whole computer. (On Debian or Ubuntu, if it can't set up Python, run `sudo apt install python3-venv` first.)

### Running on a schedule

If a program has timed jobs or listeners, the zip also has `run-on-schedule.bat` and `run-on-schedule.sh`. These keep running, so the jobs start by themselves, and if the program stops with a problem they start it again 30 seconds later.

To start it automatically:

- **Windows:** double-click `install-startup.bat` once. The program then starts in a small window each time you log in. To undo it, press Windows+R, type `shell:startup`, and delete "Second Thought - my-program".
- **Linux or a Mac:** run `sh install-service.sh` once. On Linux it starts whenever the computer starts (it asks for your password to set this up); on a Mac, whenever you log in. It tells you how to watch what the program is doing, and how to turn it off.

### Running on GitHub Actions

A program whose scripts start at set times ('when it's …' and 'every …') can run on GitHub's computers instead, so yours doesn't need to be on. In Import / export, choose **Save as GitHub Actions (.zip)**. The zip has the program, a workflow in `.github/workflows/`, and `SETUP.md`, which lists the repository secrets to add (your keys). Put the files in a **private** repository, add the secrets, and the scripts run at their times. The **Run workflow** button on the Actions tab runs one now.

If the program has test cases (**Save as test case** after a good run), the workflow runs them too: whenever you push a change to the program, its tests or the workflow, and from **Run workflow**. They never run on the schedule, since they call the real models. A failed case shows on the run's page, and the run's summary has a table of every case and what the tests cost. `SETUP.md` shows how to make the scheduled runs wait while the last test run has failed.

- **Times:** GitHub's schedules are in UTC. The workflow is worked out for your time zone. Where the clocks change, each time has a winter line and a summer line, and the program only runs a script within an hour after its time, so the other line does nothing. GitHub often starts runs a few minutes late, sometimes skips one when it's busy, and runs 'every' scripts at most every 5 minutes.
- **What it remembers:** after each run, `memory.json` and `outputs/` are committed back to the repository. That's why the repository should be private. To keep them out of it, the workflow says how to use `actions/cache` instead, but GitHub deletes a cache it hasn't used for 7 days.
- **Approval:** adding the workflow is your yes to what the program can do (`SETUP.md` lists it), so it runs with `approve = no`. An agent tool that asks first still gets no answer there, so it says no.
- **What can't run there:** programs that wait for things to happen (messages, web requests, changes, new files); programs that use Llama, MCP servers or folders on your computer; and programs whose scheduled scripts ask you questions. The page says which, and why. Home Assistant, Homey and MQTT have to be reachable from the internet.
- **Free minutes:** on GitHub's free plan, private repositories get 2,000 a month, and a run takes about a minute.
- **When it fails:** the reason is on the run's page on GitHub, under Annotations, as well as in the log.
- **Claude keys:** make the key inside a workspace (the Console's Workspaces page). A key made for the whole organisation also needs the `ANTHROPIC_WORKSPACE_ID` secret.

**Checked on GitHub** (October 2026, #226). The *Rain window* gallery program, saved as GitHub Actions for Europe/London into a private repository with its three secrets, ran from the Run workflow button: the secrets reached the program, the time zone was London's, the right script ran, the forecast was looked up and the answer arrived on Telegram, in 27 seconds. The scheduled runs start from the cron lines as above. That first real run found what's now fixed: a Claude key made for a whole organisation was refused (so `ANTHROPIC_WORKSPACE_ID` and a plain explanation), the reason for a failure was only in the log, the end of a failed run said to run it again to carry on (which can't happen there), the actions were the old Node.js 20 ones, and Telegram showed the reply's Markdown asterisks instead of bold. What it remembers being committed back is checked by the tests with stand-in services, since the program used doesn't remember anything.

The workflow runs `python my-program.py --run-schedule 2`, which runs scheduled script 2 once, if it's due. You can use the same thing with any scheduler, such as cron or Windows Task Scheduler: add `--now` to run it whatever the time.

### Approving what a program can do

A program that does real things (sends email or messages, switches lights, posts on GitHub) asks you before it runs the first time:

```
This program can:
  - send email
  - read your calendars
It sends what it reads and writes to Claude.

Approve? [y/n] >
```

It remembers your answer until the program changes; a changed program might do different things, so it asks again. The same list is written at the top of the program, and the page shows it when you import one.

A scheduled program, with nobody there to answer, won't start until you've approved it once, so run it yourself first. If you're sure, and the computer is unattended, put `approve = no` in `second-thought.ini`.

If a program has an **ask me before** block, Python asks in the terminal and waits for `y` or `n`. With nobody there to answer, it says no and carries on.

### Test cases

A program that checks its own work deserves a check of its own, especially after you change its model.