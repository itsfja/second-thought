# Second Thought

### A Ladybird-style book about a clever helper

---

## Page 1: Hello

*Picture: a child at a table with a computer. A friendly ladybird sits on the screen.*

This is a computer.

A computer is a machine that follows instructions.

An instruction is a thing you ask someone to do. "Please shut the door" is an instruction.

The computer can follow lots of instructions, one after another, very fast.

This book is about a program called **Second Thought**.

A program is a list of instructions for a computer.

---

## Page 2: Meet Claude

*Picture: a speech bubble coming out of the computer, saying "How can I help?"*

This is Claude.

Claude lives inside the computer. Claude can read and write.

You can ask Claude to write a story, answer a question, or explain something hard in an easy way.

Claude is very helpful. But Claude is not perfect. Sometimes Claude makes mistakes, just like people do.

---

## Page 3: Having a second thought

*Picture: a child writing in an exercise book, then crossing something out and writing it again, neater.*

When you write a story at school, you write it once.

Then you read it again. You spot a spelling mistake. You see a part that is muddled. You fix them.

Now the story is better.

Reading your work again and making it better is called **having a second thought**.

Second Thought helps Claude do the same thing. Claude writes something. Then Claude checks it. Then Claude makes it better.

---

## Page 4: Building blocks

*Picture: bright, coloured blocks that click together like toy bricks. Each block has words on it.*

In Second Thought, you do not need to type long instructions.

Instead, you use **blocks**.

Each block is one instruction. One block says "write a first draft". Another block says "check the draft". Another says "make it better".

You pick up a block with the mouse and drag it to the big space on the screen. You click the blocks together, one under another, like building a tower.

The computer follows the blocks from top to bottom.

If you have used Scratch at school, this will feel familiar. It is very like Scratch.

---

## Page 5: The colours

*Picture: a box of blocks sorted into coloured piles.*

The blocks come in different colours. Blocks of the same colour do the same sort of job.

- **Yellow blocks** start things. The yellow block "when Run is clicked" always goes at the very top.
- **Orange blocks** repeat things, or choose between things.
- **Blue blocks** ask Claude to write.
- **Purple blocks** ask Claude to check the writing.
- **Teal blocks** ask *you* a question and wait for your answer.
- **Olive blocks** make an **agent**: a helper that decides its own steps. Its **tools** are a darker olive, in their own **Tools** pile.
- **Pink blocks**, under **Connections**, talk to Telegram, email, your calendar and news feeds.
- **Green blocks** show the result at the end.

There are more colours too. You will find them all down the left side of the screen.

---

## Page 6: Pressing Run

*Picture: a big blue button with the word "Run" on it, and a finger about to press it.*

When your blocks are ready, press the blue **Run** button.

On the right-hand side of the screen there is a list called the **run log**. A log is a diary of what happened.

Each time a block does its job, a new line appears in the run log. You can watch Claude working, step by step.

At the end, a green box shows the **result**. The result is what your program made.

Under the result, a small line says roughly how many **tokens** the run used. Tokens are the little pieces of words that Claude reads and writes. Every token uses a tiny bit of your Claude allowance. On the page this number is a good guess, worked out from how long the words are.

Under each step that asks Claude something, a small grey line says which helper answered, how long it took and roughly how many tokens it used. Click **Prompt sent** to see exactly what Claude was asked.

Press **Save log** at the top of the run log to keep a copy of the diary. It saves every step, how long each one took, and the result, as a file you can read later.

If something goes wrong, press **Stop**. Everything will stop straight away.

Next to the **Model** menu is a button called **Backups**. The model you choose in the menu is your main helper. Backups are spare helpers, like substitutes in a football team. If the main helper can't come (perhaps its key is missing, or its computers are having a bad day), the first spare helper does that job instead. The run log tells you when that happens.

---

## Page 7: Things Second Thought can do

*Picture: a ladybird holding a long scroll, with a list written on it.*

Second Thought can do many things. Here are some of them.

- It can ask Claude to write, then check, then try again until the writing is good.
- If it runs out of tries, it keeps the best try, not just the last one. And each time it checks, it makes sure old mistakes haven't crept back in.
- It can **save a checkpoint** when the draft is good, and **go back to the checkpoint** if later changes make it worse.
- It can ask you questions and wait for your answer.
- It can look at a picture you give it and tell you about it.
- It can draw simple pictures, like a cartoon loaf of bread.
- It can read a document, such as a PDF or a Word file, and tell you what is in it.
- It can save its work as a file, so you can keep it.
- It can **remember** things for next time, like a notebook it keeps in a drawer.
- It can do several jobs at the same time.
- It can wait until a certain time of day, and then start a job by itself.
- If something goes wrong, it can try again.
- It can stop itself before it uses too many tokens. Put the block **limit this run to … tokens** near the top.
- It can ask you first, before it sends a message, says something out loud, saves a file or changes something at home. Use the block **ask me before …**.
- It can use one of your saved programs as a single block inside another program. Use **run program … with …** from the **Programs** colour.
- It can ask **Gemini** to help too. Gemini is another clever helper, made by a company called Google. Claude can write something, and Gemini can check it. Two helpers spot more mistakes than one.
- It can ask **Llama**, a helper that can live on your own computer and keep everything private.
- It can ask **DeepSeek** and **Grok** too. Grok is made by a company called xAI.
- It can ask **GPT**, the helper made by **OpenAI**. Lots of people know it from ChatGPT.
- It can ask helpers from all round the world: **Mistral** from France, **Qwen** from Alibaba and **Kimi** from Moonshot.
- It can ask **Perplexity**, a helper that looks things up on the internet every time, and tells you where it found them.
- It can ask open helpers from **Hugging Face**, super-speedy ones from **Groq**, and **GLM** and **MiniMax** too.
- With **OpenRouter**, it can ask almost *any* helper in the world, using just one key.

---

## Page 7½: The agent

*Picture: the ladybird standing in front of a toolbox, choosing a spanner.*

Most programs do exactly what the blocks say, in order. You decide every step.

An **agent** is different. You give it a **goal** and some **tools**, and Claude decides what to do next. It picks a tool, looks at what happened, and picks again. When the goal is met, it writes its answer into the draft.

The olive block **agent: work toward …** holds the tools. The tools have their own pile, called **Tools**, just below **Agent**. Drop as many as you like inside the agent. You can give it:

- **ask me a question**, so it can ask you things only you know.
- **remember and recall notes**, so it can keep what it learns for next time.
- **search the web and read pages**, for things that change. It can search, then read a source page in full. Reading pages only works in exported Python, and only public pages, never addresses on your own network.
- **work out sums**, so numbers are worked out exactly, not guessed. It knows + − × ÷, powers, brackets and rounding, like `round(350 / 500 * 100, 1)`.
- **clock times and dates**, for the time now and for adding or taking away minutes, like 09:30 plus 270 minutes. Good for working backwards from when you want bread out of the oven.
- **read a file I choose**: the agent asks you for a PDF, a Word file or a text file and reads it.
- **check text against criteria**: a separate, strict reviewer checks the agent's work and lists the problems, so the agent can fix them before it finishes.
- **news feeds**, to read the latest from news sites and blogs (RSS or Atom).
- **search LinkedIn**, which searches LinkedIn's public pages through the web search. LinkedIn doesn't let programs search it directly, so this only finds what LinkedIn shows everyone.
- **calendar**, to list your events and find free time.
- **email: search and read**, and **email: send**.
- **GitHub: projects and pull requests**, to find pull requests waiting for your review and read what they change, and **GitHub: comment**.
- **Telegram: search my messages** and **Telegram: send**.
- **MQTT: read topics** and **MQTT: publish**, for sensors and switches that talk MQTT (like Zigbee2MQTT).
- **Home Assistant: look at devices**, including how a sensor changed over the last day, and **control devices**. Control devices asks you before every change, because something the agent reads could try to trick it. If you trust everything it reads, choose **control devices (no asking)**.
- **tool: My Block**, to turn one of your own My Blocks into a tool. Write a clear sentence about what it does, because that sentence is all the agent knows about it. **Ask me before each use** starts ticked, so you say yes before your block runs. That matters if the block changes something, because what the agent reads could try to trick it. Untick it for blocks that only work something out, like a calculator.
  In **input types**, say what each input must be, like `flour grams: number; water grams: number`. The types are text, number, yes/no, list and any. The agent's input is checked before your block runs. If it's wrong, for example words where a number should be, the block doesn't run and the agent is told what to fix.

Tick **make a plan first** and the agent writes a short plan along with its first step, then changes it if something surprises it. You can read the plan in the run log. Planning costs nothing extra, because the plan travels with the steps.

Each step is one call to Claude, so set how many steps it may take. If it runs out of steps, the draft holds whatever it found last.

If Claude's reply comes out muddled, or it asks for the same tool with the same words twice in a row, the agent tells it and tries again. That uses up a step. If it repeats itself three times, the agent stops.

An agent only reads the words that tools send back. It never follows instructions hidden inside them. It still can't unlock a door without asking you.

When the agent finishes, the run log shows an **Agent summary**: a table with one row for each step, showing the tool, what it sent, what came back, and how it went. You get it even if the run stops part-way, because that's when it's most useful.

The block **agent's steps** gives you a list of everything the agent did: each step, the tool, what it sent, what came back, and how it went. Your program can check it, save it, or ask Claude to review it.

Tools that send something or change something (sending an email or a Telegram message, commenting on GitHub, publishing to MQTT, controlling devices) ask you before each use. That matters, because an email, a web page or a pull request can contain words written to trick the agent. Telegram has a **send (no asking)** choice for a bot that answers on its own.

On this page, the feeds, GitHub, email, Telegram and the calendar use **sample** data, like the sample house, so you can try everything safely. Nothing real is read or sent. The exported Python program uses your real ones: see **Connections** below for what to put in second-thought.ini.

There are many agent examples under **Agents** in Browse examples. **Agent: plan my bake** asks and remembers. **Agent with your own tool** uses a My Block. **Agent: bake timetable** works backwards with the clock. **Agent: scale a recipe** does every sum with the sums tool. **Agent: write, check, improve** fixes its work until a reviewer passes it. **Agent: check my recipe file** reads a file you choose. **Agent: research with sources** searches and reads its sources. **Agent: house check-up** and **Agent: bedtime round** look after a Home Assistant house, and the bedtime round asks before switching anything off. **Agent: news round-up** reads your feeds and skips what it showed you last time. **Agent: trip planner** checks your calendar and builds a plan with times and a budget. **Agent: pull requests for me** and **Agent: review and comment on a pull request** work with GitHub. **Agent: inbox triage** sorts your email and drafts replies. **Agent: plan my week** fits baking around your calendar. **Telegram bot that answers** replies to messages you send your bot. **Agent: find people on LinkedIn** searches LinkedIn's public pages.

### Connections

The pink **Connections** blocks work without an agent too:

- **Listeners** start a script when something arrives:
  - **when a Telegram message arrives**, for messages to your bot.
  - **when an MQTT message arrives on …**, for a sensor or switch. `+` stands for one level of the topic and `#` for everything below, like `zigbee2mqtt/#`.
  - **when a web request arrives at /…**, for Home Assistant automations, IFTTT, or a shortcut on your phone. Every request must carry your `WEBHOOK_SECRET`, or it's refused. Until you set one, the program doesn't listen for web requests at all.
  - **when an email arrives containing …**, checked every 2 minutes.
  - **when there's something new in feed …**, checked every 15 minutes.
  - **when a file appears in folder …**, for scans, downloads or recipes you drop in. It reads the words in PDFs, Word files and text files.
  - **when a pull request asks for my review**, checked every 5 minutes.
  - **when a calendar event starts in … minutes**, for reminders.

  **what arrived** gives what started the script. Every listener gives `text`, which sums it up. Each block's tooltip lists its other fields, like `subject` for an email or `topic` for MQTT. **Telegram message** gives a Telegram message's words, sender or chat. On the page, right-click a listener and choose **Run this script** to try it with a sample of what arrives. Listeners only listen while the exported program runs on schedule.
- **latest MQTT message on …** reads a topic, and **publish MQTT … to topic …** sends one. With **ask me before any smart home action**, publishing asks you first.
- **send Telegram message** and **send email** send something. With **ask me before sending messages and announcements**, they ask you first.
- **news from feed** gives a list of the latest items. Leave it empty for your own feeds.
- **calendar for the next … days** gives a list of your events.

Try **Morning briefing on Telegram** and **Email me a news digest** under Automation. Also try the listeners: **Proofer too warm? (MQTT)**, **When the bread is done (web request)**, **When the flour shop emails**, **Tell me when a feed posts something useful**, **Convert recipes dropped in a folder**, **When someone asks for my review (GitHub)** and **A reminder before each event**. Press Run to try each one with something you type. Under Agents, **Agent: check the sensors (MQTT)** looks over your MQTT devices.

In the exported program, second-thought.ini asks only for what your program uses:

- **GitHub:** `GITHUB_TOKEN`, from github.com/settings/tokens. Reading is enough to look. To comment, it needs to write to pull requests too.
- **Telegram:** in Telegram, message **@BotFather** and send `/newbot`. It gives you `TELEGRAM_BOT_TOKEN`. Then message your bot and run the program: it tells you your chat number for `TELEGRAM_CHAT_ID`. Anyone can message a bot, so it only listens to, and searches, the chats you list there. A bot only sees messages sent to it, so it can't search your other chats.
- **Email:** `EMAIL_ADDRESS` and an **app password**, not your normal password (in Gmail, it's in your Google account under Security). Gmail, iCloud, Yahoo and Fastmail find their own mail servers. For anything else, fill in `EMAIL_IMAP_HOST` and `EMAIL_SMTP_HOST`.
- **Calendar:** `CALENDAR_URL`, your calendar's private iCal address. In Google Calendar it's under Settings, your calendar, **Secret address in iCal format**. It can read your calendar, but not add to it.
- **News feeds:** `feeds = ` and the feed addresses, with spaces between them.
- **MQTT:** `MQTT_HOST`, your broker's address (for Mosquitto in Home Assistant, that's your Home Assistant), plus `MQTT_USERNAME` and `MQTT_PASSWORD` if it needs them. `MQTT_TLS = yes` makes it encrypted. The program needs the paho-mqtt library, which run.bat and run.sh install.
- **Web requests:** `WEBHOOK_SECRET`, a long password, and `WEBHOOK_PORT` if 8765 is taken. Call `http://<this computer>:8765/<address>?key=<your secret>`, or put the secret in an `X-Second-Thought-Key` header.

The agent only reads **public** web pages and feeds, never addresses on your own network, in case something it reads tries to steer it there. Your own feeds and calendar address are fine wherever they are. If you want the agent to read pages on your own network, add `local_pages = yes`.

To keep listening all the time, run the program with **run-on-schedule** (see Page 10). Things that arrived while it was off don't start the script: Telegram messages are kept for searching, and the email, feed, GitHub and folder listeners start from what's new after the program starts.

---

## Page 8: Examples to try

*Picture: a shelf of little books, each with a different title.*

You do not have to start from nothing.

At the top of the screen there is a box called **Example**. Choose an example, then press **Load**. Now press **Run** and watch what happens.

There are nearly fifty examples, sorted into groups: **Writing, Research, Design, Learning, Work, Home and baking, Code and data,** and **Automation**. Press **Browse examples** to see them all, with a sentence about each one and an idea for something to change.

Try the example called **Review loop** first. Claude writes about bread, checks its own work, and makes it better.

Then try your own ideas. Change the words on the blocks. Add new blocks. See what happens.

You cannot break anything. If you get in a muddle, just load an example again.

---

## Page 9: Saving your programs

*Picture: a child putting a drawing carefully into a folder.*

When you make a program you like, you will want to keep it.

Press the **Programs** button at the top of the screen. Type a name for your program and press **Save**.

Next time, open the same box and press **Open** to get your program back.

You can also keep a copy as a file on your computer. Press **Import / export** to do that.

A saved program can be a building block, too. Put **run program "my program" with …** inside another program. The saved program runs, then hands back its result. Inside it, the block **message value** holds whatever you gave it. It has its own draft and its own result, so it can't muddle up yours.

There are two rules. A program can't run itself, because that would never end. And a program that uses **broadcast** blocks can't be used this way: run it on its own instead.

---

## Page 10: Making a program run on its own

*Picture: a small computer in a cupboard, quietly working while everyone is asleep.*

Second Thought can turn your blocks into **Python**.

Python is a language that computers understand. It is written with words and symbols instead of blocks.

Once your program is in Python, it can run on another computer by itself, even when the Second Thought page is closed.

This part needs a grown-up, because the Python program needs a special key to talk to Claude. The key is a bit like a library card. It tells Claude who is asking, and it costs a little money each time it is used.

**Grown-ups, here is how:**

Press **Import / export**, then **Save Python (.zip)**. Unzip the file into a folder of its own. Inside you will find:

| File | What it is |
|---|---|
| `my-program.py` | The program. |
| `second-thought.ini` | The settings: this is where the keys go. |
| `run.bat` | For Windows. Double-click it to run the program. |
| `run.sh` | For Linux or a Mac. It does the same job as `run.bat`. |
| `requirements.txt` | The list of parts Python needs. `run.bat` and `run.sh` install them for you. |

Open `second-thought.ini` in Notepad (or any text editor). It lists only the keys *this* program needs. Put each key after its `=` sign, like this, then save:

```
[keys]
ANTHROPIC_API_KEY = sk-ant-your-key-here
```

Keep this file private. It holds your keys, so don't email it or put it on the internet.

**On Windows:** you need Python, from python.org (tick **Add python.exe to PATH** when you install it). Then double-click `run.bat`. The first time, it installs what the program needs.

**On Linux or a Mac:** open a terminal in the folder and type:

```
sh run.sh
```

The first time, it makes a private Python folder called `.venv` next to the program and installs what it needs in there, so nothing is installed for the whole computer. (On Debian or Ubuntu, if it says it can't set up Python, run `sudo apt install python3-venv` first.)

If a program has timed jobs, the zip also has `run-on-schedule.bat` and `run-on-schedule.sh`. These keep running, so the jobs start by themselves. If the program stops with a problem, they start it again 30 seconds later.

There are also two ways to make the program start all by itself:

- **Windows:** double-click `install-startup.bat` once. From then on, the program starts in a small window each time you log in. To stop that, press Windows+R, type `shell:startup`, and delete the file called "Second Thought - my-program".
- **Linux or a Mac:** type `sh install-service.sh` once. On Linux it starts whenever the computer starts (it asks for your password to set this up). On a Mac it starts whenever you log in. It tells you how to watch what the program is doing, and how to turn it off.

The ini file has a `[run]` part, too. Take the `;` off the front of a line to switch it on:

```
[run]
budget = 50000
save_log = yes
```

`budget` stops each run before a model call once it has used that many tokens. In Python the count is exact, because every company says how many tokens it used. A **limit this run** block in the program wins over this line.

`stream` shows Claude writing as it goes, on one line that counts the letters. Normally this only happens when you run the program in a terminal yourself.

`resume` is for runs that stop part-way, for example because the internet dropped out or you pressed Ctrl+C. The program keeps a note of each finished step. Next time it can pick up where it stopped: Claude's answers, your answers and the messages already sent are reused, not asked or sent again. In a terminal it asks you first. Set `resume = yes` or `resume = no` to decide for programs that run on their own. If you change the program, it starts afresh.

`max_seconds` stops any run that takes longer than that many seconds, whatever it's doing, so a slow helper can't keep a program busy for ages. `call_timeout` gives up on a single call to a helper after that many seconds (300 if you don't say).

Helpers rename their models from time to time. To use a different model without editing the program, add `MODEL_` and the tier's name in capitals, like `MODEL_OPENAI_DEFAULT = gpt-6.2-sol` or `MODEL_QUICK = claude-haiku-4-5-20251001`. `second-thought.example.ini` shows the pattern.

`save_log` keeps a diary of every run in a folder called `logs`, next to the program. Each step in the diary says which helper answered, how long it took and the exact tokens, and the prompts are tucked under **Prompt sent**. This is handy for programs that run on their own while you sleep.

If a program has an **ask me before** block, Python asks you in the terminal and waits for `y` or `n`. When a program runs by itself on a schedule, with nobody there to answer, it says no and carries on.

Memories saved "forever" live in `memory.json`, next to the program. Two programs can share one memory file (`RB_MEMORY_FILE`): they take turns to save, so neither loses the other's changes, and a save is never left half-written if a program stops part-way. Two programs using the same Telegram bot share `telegram-messages.json` the same way, and a message is only handled once.

Everything in `second-thought.ini` can also be set as an environment variable with the same name, if you prefer. An environment variable wins over the file.

**Every setting in one place:** `second-thought.example.ini`, next to this README, lists every setting a program understands, with a note on each. That covers the keys for every helper, models and backups, run settings, Home Assistant, Homey, MQTT, Telegram, email, calendar, GitHub, web requests and feeds. Copy it to `second-thought.ini` and fill in what you use. Put that copy in your home folder and every program you export can share it, because a program looks for `second-thought.ini` next to itself first, then in the folder you run it from, then in your home folder.

If your program uses Gemini, it needs a second key, from Google. The ini file will have a line ready for it: `GEMINI_API_KEY =`.

There is a third helper too, called **Llama**. Llama is special because it can live on *your own computer*, so nothing you ask it ever leaves the house. To use it, install a free program called **Ollama** and download a Llama model:

```
ollama pull llama3.2-vision:11b
```

If Llama lives on a different computer, change this line in the ini file to tell the program where to find it:

```
LLAMA_BASE_URL = http://that-computer:11434/v1
```

A fourth helper, **DeepSeek**, is very cheap to use. It lives on DeepSeek's own computers in China, so it needs its own key, and it's best kept for things that aren't private:

```
DEEPSEEK_API_KEY = your-deepseek-key
```

A fifth helper, **Grok**, is made by a company called **xAI**. It lives on xAI's own computers, and it needs its own key too:

```
XAI_API_KEY = your-xai-key
```

A sixth helper, **GPT**, is made by **OpenAI**, the company behind ChatGPT. A ChatGPT subscription is not the same as an API key, so you need a key from OpenAI's developer site:

```
OPENAI_API_KEY = your-openai-key
```

There are lots more helpers. Each one needs its own key, from its own company:

| Helper | Made by | Lives in | The line in the ini file |
|---|---|---|---|
| **Mistral** | Mistral AI | France | `MISTRAL_API_KEY = your-key` |
| **Qwen** | Alibaba | Singapore, for people outside China | `DASHSCOPE_API_KEY = your-key` |
| **Kimi** | Moonshot AI | China | `MOONSHOT_API_KEY = your-key` |
| **Perplexity** | Perplexity | America | `PERPLEXITY_API_KEY = your-key` |
| **Hugging Face** | lots of different people | all over the world | `HF_TOKEN = your-token` |
| **Groq** | Groq | America | `GROQ_API_KEY = your-key` |
| **GLM** | Z.ai | China | `ZAI_API_KEY = your-key` |
| **MiniMax** | MiniMax | China | `MINIMAX_API_KEY = your-key` |

Perplexity is different from the others. It searches the internet for every question, then lists the pages it read at the end of its answer. That makes it good for things that change, like prices and opening times. It can't look at photos, though.

**Hugging Face** is like a huge library of free, open helpers that anyone can share. Second Thought starts you off with Google's Gemma, but you can choose almost any helper in the library.

**Groq** (spelt with a q, so it is not the same as Grok) is very, very fast. It is good for jobs with lots of little steps.

**OpenRouter** is like a big switchboard. One key reaches hundreds of helpers from lots of different companies. Choose **OpenRouter, auto-pick** and it chooses a good helper for each job. Or use the block called **with OpenRouter model**, and type in the name of any helper you like from openrouter.ai/models:

```
OPENROUTER_API_KEY = your-openrouter-key
```

All the helpers except Claude only work in the Python program. On the Second Thought page, Claude does their jobs instead, and the run log says so.

---

## Page 10½: A clever house

*Picture: a cosy house at night. A little light glows in every window, and the ladybird waves from the doorstep.*

Some homes have a helper called **Home Assistant**. It knows which lights are on, whether the doors are shut, and how warm each room is. It can switch things on and off, too.

Second Thought can talk to Home Assistant. It has its own blue blocks for this.

- One block asks "Is the back door open?"
- One block takes a photo from a camera, so Claude can say who is at the door.
- One block turns a light off, or sends a message to a phone.
- A special yellow block starts a script by itself when something changes, like the doorbell ringing.

On the Second Thought page, these blocks use a **pretend house**, so you can try everything safely. Press the **Home Assistant** button to see the pretend house. Change something, like the doorbell, and watch your program spring into action.

There are more than sixty Home Assistant examples to try. You will find them in **Browse examples**.

**A safety rule:** Second Thought will never unlock a door, open the garage or switch off the alarm without asking you first.

**Grown-ups, here is how to use your real Home Assistant:**

Export the program as a zip and unzip it on a computer at home, on the same network as Home Assistant. Make a long-lived access token in Home Assistant (your profile, then the Security tab), and put it in `second-thought.ini`:

```
[home assistant]
HA_URL = http://homeassistant.local:8123
HA_TOKEN = your-long-lived-token
```

Then double-click `run-on-schedule.bat` (Windows), or type `sh run-on-schedule.sh` (Linux or Mac). On an always-on Linux computer, `sh install-service.sh` keeps it running for good.

`--schedule` keeps it running, so timed jobs and "when it changes" scripts start by themselves. A small virtual machine or container that's always on is a good home for it.

### Homey

Some homes have a **Homey** instead, or as well. Second Thought talks to Homey Pro too, with its own green blocks in the **Homey** pile:

- **when Homey device … … changes** starts a script when a device's value changes, like the washing machine's power dropping. **what arrived** says which device, what changed, and from what to what.
- **… of Homey device …** reads one value, like `measure_temperature` of the Proofing box.
- **Homey devices matching …** lists devices and everything they report.
- **set Homey device … … to …** switches something, like `onoff` to `off` or `dim` to `0.5`.
- **run Homey flow …** starts one of your flows. A flow can do anything your Homey can, like sending a Homey notification.
- **Homey variable …** and **set Homey variable … to …** read and change your Logic variables, so your flows can use them.

There are agent tools too, in the **Tools** pile: **Homey: look at devices, flows and variables**, and **Homey: control devices and start flows**, which asks you before each change.

On the page these blocks use a **pretend Homey home**. Try the examples under **Homey** in Browse examples.

**The same safety rule:** unlocking, opening the garage and switching off the alarm always ask you first.

**Grown-ups, here is how to use your real Homey:** in the Homey Web App (my.homey.app), open Settings, then API Keys, and make a new key. Give it only the permissions the program needs: view devices, control devices, view and start flows, and view and edit Logic. Put it in `second-thought.ini` with your Homey's address on your network:

```
[homey]
HOMEY_URL = http://homey-XXXXXXX.local
HOMEY_API_KEY = your-api-key
```

The address is in the Homey app under Settings, General. The computer running the program must be on the same network as your Homey. API keys work with Homey Pro (2023 and later) and Homey Pro mini.

**Homey Self-Hosted Server** serves the same API on port **4859**, so use the address of the computer it runs on, with `:4859` on the end:

```
HOMEY_URL = http://192.168.1.20:4859
```

Make the API key in the Homey Web App the same way. A **Homey Bridge** connected to a Self-Hosted Server doesn't need anything of its own: its devices show up through the server. To check it all works, run `python tools/smoke_test.py homey`. It only reads, so nothing is switched.

---

## Page 11: What is in this folder

*Picture: an open toy box with labelled compartments.*

This folder is where all the parts of Second Thought are kept. Each part has its own place.

| Name | What it is |
|---|---|
| `second-thought.html` | The Second Thought page itself. This is the part you see on the screen. |
| `python/runtime.py` | The helper that comes with every Python program. It knows how to do each block's job. |
| `prompts/convert-guide.txt` | The instructions Claude reads when it turns Python back into blocks. |
| `ha/sample-house.json` | The pretend house that the Home Assistant blocks use on the page. |
| `samples/connections.json` | The pretend feeds, GitHub projects, Telegram messages, emails and calendar that the page uses. |
| `tools/sync.py` | A little tool that copies the parts above into the page, so they always match. |
| `tests/` | Checks that make sure everything still works. |
| `second-thought.example.ini` | Every setting a program understands, with a note on each. Copy it to `second-thought.ini` to use it. |
| `README.md` | This book! |

---

## Page 12: Checking it still works

*Picture: a doctor with a stethoscope, listening to a computer.*

When somebody changes Second Thought, they must check it still works.

The `tests` folder does this. It pretends to be Claude, so the checks do not cost anything. Then it tries every example, one by one, and makes sure each one finishes properly.

**Grown-ups, here is how:**

```
bash tests/setup.sh
python tests/run_tests.py
```

You only need the first line once. It fetches the things the checks need.

The second line runs the checks. At the end it says **All checks passed**, or it tells you which check went wrong.

If you change `python/runtime.py` or `prompts/convert-guide.txt`, run `python tools/sync.py` first, so the page has your changes too.

The checks use pretend helpers, so they never cost anything. To check the real helpers with your own keys, run:

```
python tools/smoke_test.py
```

It asks each helper you have a key for a few short questions and says what works. That covers Claude's tidy answers, streaming, carrying on after a long answer is cut off, and the agent using a tool, plus which kind of tidy answer every other helper understands. It costs a few pence and prints the tokens used. Add a name to check only one helper, like `python tools/smoke_test.py claude`.

---

## Page 13: A few things to know

*Picture: a ladybird holding up one finger, as if to say "Remember this".*

- Second Thought keeps its secrets safe. Things it remembers are only seen by you.
- Inside the page, Claude cannot look things up on the internet. A Python program can.
- Timed jobs on the page only work while the page is open. For jobs that run while you sleep, use Python.
- Every answer has a length limit. If Claude runs out of room part-way, the program asks it once to carry on from where it stopped, and joins the two parts. If it's still too long, the run log says **Cut short**, and the result is marked best effort.
- The page can't see exactly how many tokens Claude used, so it makes a careful guess. Python knows the exact number.
- Some blocks need an answer in a particular shape, like a number or a yes or no. In Python, Claude is made to write exactly that shape. Most other helpers are asked to write in that shape too, or at least to write tidy JSON. If a helper can't do that, the program remembers and stops asking. Every answer is still checked when it arrives, on the page as well. If an answer comes back muddled, the program sends it back once and says what was wrong. If it's still muddled, that step stops with a clear message, so put it inside **retry** if you'd like another go.
- On the page, your browser already asks before saving any file. So **ask me before saving files** only adds a question in Python.
- Some hidden names inside the page still say `reflection-blocks`. That was Second Thought's name when it was very young. They stay the same so that old saved programs still work.

---

## The end

*Picture: the ladybird flying away over a field, towards the sunset.*

Now you know all about Second Thought.

Have fun building. And remember: a second thought is often a better one.
