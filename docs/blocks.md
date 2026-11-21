# Blocks

[← Second Thought](../README.md) · [Using the page](using-the-page.md) · **Blocks** · [The agent](agent.md) · [Connections](connections.md) · [MCP tools](mcp.md) · [Running exported programs](running.md) · [Program format](program-format.md) · [Settings and models](settings.md)

*Every block on the page — 207 of them — grouped as the palette groups them: what each does, what it lets a program do, and whether an exported program asks you first.*

<!-- Made by tools/sync.py from tools/blocks.json: edit the blocks in web/editor/, not this. -->

**Asks first:** *every time* means the block asks before each action, even when nothing else asks, and doesn't run with nobody there to say yes. *Before its first run* means a program that uses it asks you once, the first time it runs. Unlocking, opening and disarming always ask. [The agent](agent.md) has more on what always asks.

[Events](#events) · [Control](#control) · [Wait & time](#wait--time) · [Operators](#operators) · [Text](#text) · [Programs](#programs) · [Draft](#draft) · [Ask Claude](#ask-claude) · [Review](#review) · [Agent](#agent) · [Tools](#tools) · [Connections](#connections) · [You](#you) · [Records](#records) · [Files](#files) · [Memory](#memory) · [Pictures](#pictures) · [Radarr and Sonarr](#radarr-and-sonarr) · [Calendar](#calendar) · [Discord and Slack](#discord-and-slack) · [Coinbase](#coinbase) · [Docker](#docker) · [Email](#email) · [News feeds](#news-feeds) · [Files and folders](#files-and-folders) · [GitHub](#github) · [Home Assistant](#home-assistant) · [Homey](#homey) · [MikroTik](#mikrotik) · [MQTT](#mqtt) · [NZBGeek](#nzbgeek) · [Pi-hole](#pi-hole) · [Plex](#plex) · [Powerwall](#powerwall) · [Proxmox](#proxmox) · [SABnzbd](#sabnzbd) · [Solax](#solax) · [Telegram](#telegram) · [UniFi](#unifi) · [Unraid](#unraid) · [Web](#web) · [Output](#output)

## Events

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| broadcast *msg*<br>`rb_broadcast` | Starts every 'when I receive' script for this message, then carries straight on. | nothing to declare | no |
| broadcast *msg* and wait<br>`rb_broadcast_wait` | Starts every 'when I receive' script for this message and waits until they have all finished. | nothing to declare | no |
| broadcast *msg* with *value*<br>`rb_broadcast_with` | Starts every 'when I receive' script for the message. Each one gets the value as its 'message value'. | nothing to declare | no |
| broadcast *msg* with *value* and wait<br>`rb_broadcast_with_wait` | — | nothing to declare | no |
| every *n* *unit*<br>`rb_every` | Runs repeatedly while Schedules is on and this page is open. The first run is one interval after you turn Schedules on. | nothing to declare | no |
| message value<br>`rb_msg_value` | The value sent with the broadcast that started this script (or woke this 'wait until I receive'). In a program run by 'run program', the value it was given. | nothing to declare | no |
| when I receive *msg*<br>`rb_receive` | Runs the blocks below whenever this message is broadcast. Several scripts can listen for the same message. | nothing to declare | no |
| when Run is clicked<br>`rb_start` | Every program starts here. Blocks below it run top to bottom. Several of these run side by side. | nothing to declare | no |
| when it's *hour* : *minute* *days*<br>`rb_when_time` | Runs at this time (24-hour clock) while Schedules is on and this page is open. | nothing to declare | no |

## Control

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| limit this run to *tokens* *unit*<br>`rb_budget` | Before each model call, checks how many tokens this run has used, or what it has spent at the models' list prices. Once it reaches this amount, the run stops. 0 means no limit. In dollars, a model with no known price can't be counted, so the run stops rather than going on with no limit. On this page the counts are estimates; exported Python uses the exact counts. | nothing to declare | no |
| the error<br>`rb_error` | What went wrong in the most recent failure. | nothing to declare | no |
| retry up to *times* times<br>`rb_retry` | If something inside fails in a way a second try could fix (a dropped connection, a garbled reply), waits a little and runs it again. | nothing to declare | no |
| this program's setup check<br>`rb_setup_check` | The same checks as running the program with --doctor, as text: each key, package and connection it uses, with ok, FAIL or NOTE. It only reads: nothing is sent, switched or charged. Only in exported Python; on this page it says so. | nothing to declare | no |
| stop the run<br>`rb_stop` | End the run here. Anything already in the result is shown. | nothing to declare | no |
| tokens used so far<br>`rb_tokens_used` | Tokens this run has used: sent plus received. An estimate on this page, exact in exported Python. | nothing to declare | no |
| try<br>`rb_try` | Runs the first part. If anything in it fails, runs the second part instead of stopping the run. | nothing to declare | no |
| use model *tier*<br>`rb_use_model` | Switch model for the AI blocks after this one. Models other than Claude run in exported Python; in this page Claude stands in for them. | nothing to declare | no |
| wait *secs* *unit*<br>`rb_wait` | Pause this script (up to 24 hours). | nothing to declare | no |
| wait until *cond*<br>`rb_wait_until` | Pause until the condition is true. Checked twice a second, or every 10 seconds if it asks Claude. | nothing to declare | no |
| with OpenRouter model *model*<br>`rb_with_any_model` | Runs just the blocks inside on any model OpenRouter offers. Type its name from openrouter.ai/models, for example mistralai/mistral-small or google/gemma-4-31b-it. openrouter/auto picks one for you. Runs in exported Python (needs OPENROUTER_API_KEY); in this page Claude stands in. | nothing to declare | no |
| with model *tier*<br>`rb_with_model` | Runs just the blocks inside on this model, then goes back to the model before. Models other than Claude run in exported Python; in this page Claude stands in for them. | nothing to declare | no |

## Wait & time

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| current *part*<br>`rb_now` | — | nothing to declare | no |
| pause until I click Continue: *text* (at most *mins* min)<br>`rb_pause` | A checkpoint. Shows the note in the log and waits for you. When nobody's at the keyboard and approve_by = telegram, it asks on Telegram and carries on after the minutes set, or on any reply. | nothing to declare | no |
| reset timer<br>`rb_reset_timer` | — | nothing to declare | no |
| timer<br>`rb_timer` | Seconds since the run started or the timer was reset. | nothing to declare | no |
| wait until I receive *msg*<br>`rb_wait_msg` | Pause this script until another script broadcasts the message. | nothing to declare | no |
| wait until *hour* : *minute*<br>`rb_wait_time` | Pause until this time (24-hour clock). If it has passed today, waits until tomorrow. | nothing to declare | no |

## Operators

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| *a* contains *b*<br>`rb_contains` | True if the first text includes the second (ignores case). | nothing to declare | no |

## Text

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| *text*<br>`rb_longtext` | Long text. Press Enter for a new line; lines wrap at 80 characters. | nothing to declare | no |
| word count of *text*<br>`rb_word_count` | — | nothing to declare | no |

## Programs

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| run program *name* with *value*<br>`rb_run_program` | Runs a program from your Programs list, as a step. It gets its own draft, result and variables, and gives back its result. Inside it, 'message value' is the value you pass here. Exported Python includes a copy of the program as it was when you exported. | nothing to declare | no |

## Draft

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| go back to checkpoint *name*<br>`rb_checkpoint_restore` | Puts the task, draft, review, result and variables back as they were at 'save checkpoint'. Memory, files and messages already sent aren't undone. | nothing to declare | no |
| save checkpoint *name*<br>`rb_checkpoint_save` | Remembers the task, draft, review, result and variables as they are now, under this name, for the rest of the run. | nothing to declare | no |
| draft<br>`rb_draft` | — | nothing to declare | no |
| write a first draft *web* using the web<br>`rb_generate` | Claude writes a draft that completes the task. | nothing to declare | no |
| revise to fix the review's problems *web* using the web<br>`rb_revise` | Claude fixes the problems the last review found. | nothing to declare | no |
| rework the draft: *text*<br>`rb_rework` | Claude rewrites the draft following your instruction. | nothing to declare | no |
| set draft to *text*<br>`rb_set_draft` | — | nothing to declare | no |
| set task to *text*<br>`rb_task` | Sets what the AI should produce. | nothing to declare | no |
| task<br>`rb_task_get` | — | nothing to declare | no |

## Ask Claude

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| ask Claude *text*<br>`rb_ask` | Claude answers in text. | nothing to declare | no |
| ask Claude for a list: *text*<br>`rb_ask_list` | Claude replies with a list you can loop over. | nothing to declare | no |
| ask Claude for a number: *text*<br>`rb_ask_number` | — | nothing to declare | no |
| Claude says yes to *text*<br>`rb_ask_yesno` | Claude answers a yes/no question. | nothing to declare | no |
| chat *name* : *text*<br>`rb_chat` | Sends a message in a named conversation. Claude sees the earlier turns of that conversation. | nothing to declare | no |
| start conversation *name* afresh<br>`rb_chat_reset` | — | nothing to declare | no |
| clear instructions for Claude<br>`rb_clear_instructions` | — | nothing to declare | no |
| extract *what* from *text*<br>`rb_extract` | — | nothing to declare | no |
| prompt *name*<br>`rb_prompt` | Text from your prompt library (open Programs to add prompts). | nothing to declare | no |
| rewrite *text* to *how*<br>`rb_rewrite` | For example: rewrite (draft) to (translate into French). | nothing to declare | no |
| set instructions for Claude to *text*<br>`rb_set_instructions` | Sent with every Claude call after this block, for example a role, tone or house style. | nothing to declare | no |
| search the web for *text*<br>`rb_web_search` | In exported Python this searches the live web. In this page Claude can't browse, so it answers from its own knowledge and the log says so. | read public web pages and search the web | no |

## Review

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| better of *a* and *b* for *criteria*<br>`rb_better` | — | nothing to declare | no |
| is valid JSON<br>`rb_chk_json` | Fails the review unless the draft is valid JSON. | nothing to declare | no |
| has a link<br>`rb_chk_link` | Fails the review unless the draft contains a link (http://… or www.…). | nothing to declare | no |
| at most *n* words<br>`rb_chk_max_words` | Counts the draft's words exactly — models count badly — and fails the review if there are more. The problem says the real count, like '231 words; the limit is 200'. | nothing to declare | no |
| mentions *text*<br>`rb_chk_mentions` | Fails the review unless the draft contains these words (case doesn't matter). | nothing to declare | no |
| doesn't mention *text*<br>`rb_chk_no_mention` | Fails the review if the draft contains these words (case doesn't matter). | nothing to declare | no |
| draft passed review<br>`rb_passed` | — | nothing to declare | no |
| review problems<br>`rb_problems` | — | nothing to declare | no |
| review the draft against *criteria*, checked by *reviewer*<br>`rb_reflect` | Claude critiques the draft. If it fails, the blocks inside run, then it critiques again. Each round the reviewer also checks that earlier problems haven't come back. If the rounds run out, the draft that met the most rules is kept, not just the last one. The blocks inside 'and check' are worked out by code, not by the model. 'Checked by' chooses who reviews: the same model, another maker's model when a key for one is set, or a named one; the run log says who wrote and who checked. | nothing to declare | no |
| review the draft against *criteria*, checked by *reviewer*<br>`rb_review` | One review. Use 'draft passed review' and 'review problems' afterwards. The blocks inside 'and check' are worked out by code, not by the model: they cost nothing and always give the same answer. 'Checked by' chooses who reviews: the same model, another maker's model when a key for one is set, or a named one; the run log says who wrote and who checked. | nothing to declare | no |
| score *text* out of 10 for *criteria*<br>`rb_score` | — | nothing to declare | no |

## Agent

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| agent: work toward *goal*<br>`rb_agent` | Claude decides what to do next: each step it picks one of the tools inside, sees what happened, and carries on until the goal is met or the steps run out. Its final answer goes in the draft. Each step is one model call. With 'make a plan first' ticked, it writes a short plan with its first step and keeps it up to date, at no extra cost. | nothing to declare | no |
| agent's steps<br>`rb_agent_steps` | What the most recent agent in this run did: a list of records with step, tool, input, result and status (done, bad input, tool error, refused, repeat, not a tool, unreadable, empty answer, stopped, answer). | nothing to declare | no |

## Tools

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| tool: *kind*<br>`rb_agent_builtin` | A ready-made tool for the agent. 'Work out sums' and 'clock times' get numbers and times exactly right, instead of the model guessing. 'Check text' has a separate reviewer judge the agent's work. On this page, feeds, GitHub, Telegram, email and the calendar use sample data; exported Python uses your own (put the keys in second-thought.ini), and reads web pages for real. Sending, commenting and 'control devices' ask you before each one, because what the agent reads (a web page, a note) could try to steer it. Choose 'no asking' only if you trust everything it reads. Unlocking, opening and disarming always ask. | depends on the tool chosen: each kind declares its own | depends on the tool |
| Flightradar24 tools<br>`rb_agent_fr24` | Gives the agent Flightradar24's own tools: live positions of aircraft (by area, flight number, callsign or registration), flight summaries with take-off and landing, tracks, history back to 2016, and airline and airport details. Every tool only reads. Needs Node.js installed, and FR24_API_KEY in second-thought.ini (a paid subscription from fr24api.flightradar24.com; each call costs credits, so a budget or a step limit keeps a run cheap). Only in exported Python. | read Flightradar24's flight data: live and historic positions, summaries, tracks, and airline and airport details | no |
| Kraken tools *mode*<br>`rb_agent_kraken` | Gives the agent Kraken's own tools, from kraken-cli: market prices, your balances and orders, and paper trading at live prices. Live trading also lets it place real orders, but every tool that can move money asks you first, even when nobody else does, and never runs on a schedule or on GitHub Actions. Needs kraken-cli installed, and KRAKEN_API_KEY and KRAKEN_API_SECRET in second-thought.ini for your account (prices and paper trading need no key). Only in exported Python. | depending on its fields, read your Kraken balances and orders, market prices, and trade on paper; or trade on your Kraken account with real money (asking you before every order) | depends on its fields |
| tools from MCP server *server* *ask*<br>`rb_agent_mcp` | Gives the agent every tool an MCP server offers: files, GitHub, databases, calendars and much more, from the whole MCP ecosystem. Set the server up in second-thought.ini as MCP_<NAME> = the command that starts it (like npx -y @modelcontextprotocol/server-filesystem ~/recipes) or its https:// address. Only in exported Python: on this page the agent works without these tools. | use the tools of the MCP servers you set up (they can do whatever those servers can) | before its first run |
| tool: My Block *name*<br>`rb_agent_tool` | Lets the agent run one of your My Blocks. Its inputs become the tool's inputs, and what it returns is the result the agent sees. Describe it clearly: the description is all the agent knows about it. Input types, for example 'flour grams: number; water grams: number - grams of water', say what each input must be: text, number, yes/no, list or any. The agent's input is checked before the block runs. 'Ask me before each use' starts ticked, because what the agent reads (a web page, a note) could try to steer it: untick it for blocks that only work things out and change nothing. | nothing to declare | no |

## Connections

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| what arrived: *key*<br>`rb_event` | Inside a 'when … arrives' script: one field of what arrived. Every listener gives 'text', which sums it up; the tooltip on each 'when' block lists its other fields. Leave it empty for the whole record. | nothing to declare | no |

## You

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| answer<br>`rb_answer` | — | nothing to declare | no |
| I approve *text*; if nobody answers in *mins* min, take *default*<br>`rb_approve` | Shows the text and waits for you to approve or send it back. When nobody's at the keyboard and approve_by = telegram, it asks on Telegram for the minutes set; the default (y or n) is taken if nobody answers. | nothing to declare | no |
| ask me before *what*<br>`rb_ask_first` | From here on, the program shows what it's about to do and waits for you to allow it. If you say no, it skips that step and carries on. Exported Python asks in the terminal; a scheduled run with nobody there skips it. | nothing to declare | no |
| ask me *text* and wait *mins* min; if nobody answers, use *default*<br>`rb_ask_me` | Pauses the run until you type an answer in the log. When nobody's at the keyboard and approve_by = telegram, it asks on Telegram for the minutes set, and uses the default if nobody answers. | nothing to declare | no |
| let me choose from *list*; if nobody answers in *mins* min, take *default*<br>`rb_choose` | Shows the list and waits for you to pick one. When nobody's at the keyboard and approve_by = telegram, it asks on Telegram for the minutes set; the default is taken if nobody answers. | nothing to declare | no |

## Records

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| ask Claude for a record with fields *fields* : *text*<br>`rb_ask_record` | Fields separated by commas, for example: title, score, notes. | nothing to declare | no |
| ask Claude for a list of records with fields *fields* : *text*<br>`rb_ask_records` | — | nothing to declare | no |
| *key* of *rec*<br>`rb_rec_get` | — | nothing to declare | no |
| *rec* has field *key*<br>`rb_rec_has` | — | nothing to declare | no |
| fields of *rec*<br>`rb_rec_keys` | — | nothing to declare | no |
| new record<br>`rb_rec_new` | — | nothing to declare | no |
| set *key* of *rec* to *value*<br>`rb_rec_set` | Changes one field of a record (usually a record variable). | nothing to declare | no |
| sort *list* by *key* *order*<br>`rb_sort` | Sorts a list of records by a field. Leave the field empty to sort plain items. | nothing to declare | no |

## Files

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| text of a file I choose<br>`rb_file_choose` | Pauses the run so you can pick a PDF, a Word .docx, or a text file. Gives back the file's text. | read files you choose | no |
| save *value* as file *name* . *ext*<br>`rb_file_save` | Offers the text as a download. The browser asks you to confirm. | save files in its outputs folder | no |
| the result so far<br>`rb_result_text` | Everything added to the result, as text. | nothing to declare | no |

## Memory

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| add *value* to remembered list *name* *kind*<br>`rb_mem_add` | Adds an item to a remembered list. If the list already exists it keeps its own kind and expiry. | keep notes between runs, in memory.json (when it keeps them for good) | no |
| forget *name*<br>`rb_mem_forget` | — | keep notes between runs, in memory.json | no |
| recall *name*<br>`rb_mem_get` | The remembered value, or empty text if nothing is remembered under this name. | keep notes between runs, in memory.json | no |
| I remember *name*<br>`rb_mem_has` | — | keep notes between runs, in memory.json | no |
| names I remember<br>`rb_mem_names` | — | keep notes between runs, in memory.json | no |
| remember *value* as *name* *kind*<br>`rb_mem_set` | While this page is open: kept across runs until you reload or close the page. Forever: saved until you forget it. | keep notes between runs, in memory.json (when it keeps them for good) | no |
| remember *value* as *name* for *n* *unit*<br>`rb_mem_set_for` | Saved like 'forever', but forgotten automatically after this long (up to 365 days). | keep notes between runs, in memory.json | no |

## Pictures

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| ask Claude *text* about picture *img*<br>`rb_img_ask` | Claude looks at the picture and answers. | nothing to declare | no |
| change picture *img* : *text*<br>`rb_img_change` | Claude redraws the picture with your change. A photo comes back as a new illustration. | nothing to declare | no |
| picture I choose<br>`rb_img_choose` | Pauses the run so you can pick a picture (JPEG, PNG, WebP, GIF or SVG). | read files you choose | no |
| draw a picture of *text*<br>`rb_img_draw` | Claude draws an illustration as SVG (flat shapes, diagrams, icons). It can't make photos. | nothing to declare | no |
| save picture *img* as *format*<br>`rb_img_save` | Offers the picture as a download. The browser asks you to confirm. | save files in its outputs folder | no |
| score picture *img* out of 10 for *criteria*<br>`rb_img_score` | — | nothing to declare | no |
| show picture *img*<br>`rb_img_show` | — | nothing to declare | no |

## Radarr and Sonarr

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| *which* diskspace<br>`rb_arr_diskspace` | A list of records, one for each of its folders: path, label, free_gb and total_gb. | read your Radarr and Sonarr: the download queue, the wanted list and disk space | no |
| *which* wanted list<br>`rb_arr_missing` | A list of records, one for each movie or episode with no file: title, added (when it was added) and id. | read your Radarr and Sonarr: the download queue, the wanted list and disk space | no |
| *which* queue<br>`rb_arr_queue` | A list of records, one for each download in the queue: title, status (Downloading, Importing, Failed, ...), size_mb, left_mb, quality and eta (time left, like 0:12:34). On this page it uses a sample queue. | read your Radarr and Sonarr: the download queue, the wanted list and disk space | no |
| search *which* for what's missing<br>`rb_arr_search` | Searches the whole wanted list for what has no file. It always asks you first, even when nothing else asks, and with nobody there to say yes it doesn't run. On this page nothing really searches. | search your Radarr and Sonarr for what's missing (asking you each time) | every time |

## Calendar

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| when a calendar event starts in *n* minutes<br>`rb_cal_when` | Runs the blocks below this many minutes before each event in your calendar (all-day events don't count). 'What arrived' gives title, start, end, location, minutes and text. | read your calendars | no |
| calendar for the next *days* days<br>`rb_calendar` | Your calendar's events from today, as records: day, start, end, title, location. Exported Python reads CALENDAR_URL (your calendar's private iCal address); this page uses a sample calendar. | read your calendars | no |

## Discord and Slack

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| send Discord message *text*<br>`rb_discord_send` | Posts in Discord: back in the channel a message came from, or in the first channel in DISCORD_CHANNEL_ID. 'Ask me before sending messages' makes it ask first. On this page it's only shown. | send Discord messages | before its first run |
| when a Discord message arrives containing *contains*<br>`rb_discord_when` | Runs the blocks below when someone posts in one of your Discord channels (type 'anything', or words the message must contain). Only the channels in DISCORD_CHANNEL_ID count, and the bot's own messages never do. Checked every 10 seconds. 'What arrived' gives text, sender and channel. On this page, right-click it and choose 'Run this script' to try it with a sample message. | read your Discord channels | no |
| send Slack message *text*<br>`rb_slack_send` | Posts in Slack: back in the channel a message came from, or in the first channel in SLACK_CHANNEL_ID. 'Ask me before sending messages' makes it ask first. On this page it's only shown. | send Slack messages | before its first run |
| when a Slack message arrives containing *contains*<br>`rb_slack_when` | Runs the blocks below when someone posts in one of your Slack channels (type 'anything', or words the message must contain). Only the channels in SLACK_CHANNEL_ID count, and bots' messages never do. Checked every 10 seconds. 'What arrived' gives text, sender and channel. On this page, right-click it and choose 'Run this script' to try it with a sample message. | read your Slack channels | no |

## Coinbase

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| Coinbase balances<br>`rb_coinbase_balances` | A list of records, one for each asset in your Coinbase portfolio, biggest first: asset, amount, value and currency. Values are in your currency (currency in second-thought.ini). On this page it uses a sample portfolio. | read your Coinbase balances and orders, and market prices | no |
| cancel Coinbase order *order*<br>`rb_coinbase_cancel` | Cancels one of your open orders, by its id (from 'Coinbase open orders'). It always asks you first, and doesn't run with nobody there. | trade on your Coinbase account with real money (asking you before every order) | every time |
| Coinbase *size* prices of *product* for the last *n*<br>`rb_coinbase_candles` | A list of records, oldest first, one for each day or hour (up to 350): time, open, high, low, close and volume. | read your Coinbase balances and orders, and market prices | no |
| place Coinbase order: *side* *amount* of *product*<br>`rb_coinbase_order` | Places a real market order, like 'preview Coinbase order'. It previews it first, then always asks you, with the fee and total, even when nothing else asks; with nobody there to say yes, it doesn't run. Needs a key with Trade permission. On this page nothing is bought or sold. | trade on your Coinbase account with real money (asking you before every order) | every time |
| Coinbase *which*<br>`rb_coinbase_orders` | Your open orders (id, product, side, size, price, filled and created), or your latest fills (time, product, side, size, price, fee and order). | read your Coinbase balances and orders, and market prices | no |
| preview Coinbase order: *side* *amount* of *product*<br>`rb_coinbase_preview` | What a market order would come to, without placing it: a record with size, spend, fee, total, slippage and warnings. Buy spends an amount of the second currency (50 of BTC-GBP spends £50); sell sells an amount of the first (0.01 of BTC-GBP sells 0.01 BTC). Nothing changes. | read your Coinbase balances and orders, and market prices | no |
| *what* of *product* on Coinbase<br>`rb_coinbase_price` | A trading pair's latest price, like BTC-GBP's in pounds, or how much it has changed in the last 24 hours, in percent. Spot trading pairs only. | read your Coinbase balances and orders, and market prices | no |
| Coinbase portfolio value<br>`rb_coinbase_value` | What your Coinbase portfolio is worth, in your currency. | read your Coinbase balances and orders, and market prices | no |

## Docker

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| Docker containers<br>`rb_docker_containers` | A list of records, one for each container, running or not: name, image, state, status, health (healthy, unhealthy, or empty with no health check), restarts and started. On this page it uses a sample stack. | read your Docker containers: their health, memory and logs | no |
| Docker logs of *name*, last *n* lines<br>`rb_docker_logs` | The last lines a container wrote, its output and its errors together, oldest first. | read your Docker containers: their health, memory and logs | no |
| *action* Docker container *name*<br>`rb_docker_power` | Restarts, stops or starts one container, by its name. It always asks you first, even when nothing else asks, and with nobody there to say yes it doesn't run. Containers listed in DOCKER_PROTECT are never touched. On this page nothing really restarts. | restart, stop and start your Docker containers (asking you each time) | every time |
| Docker memory and CPU<br>`rb_docker_stats` | A list of records, one for each running container: name, cpu (%), memory_mb, limit_mb (the machine's memory, for a container with no limit) and memory (% of the limit). | read your Docker containers: their health, memory and logs | no |

## Email

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| send email to *to* subject *subject* *text*<br>`rb_email_send` | Sends an email from your address (EMAIL_ADDRESS and an app password in second-thought.ini). 'Ask me before sending messages' makes it ask first. On this page it's only shown. | send email | before its first run |
| when an email arrives containing *contains*<br>`rb_email_when` | Runs the blocks below when a new email arrives in your inbox (checked every 2 minutes), if its sender, subject or words contain this. 'What arrived' gives from, subject, body and text. | read your email | no |

## News feeds

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| news from feed *url*<br>`rb_feed_news` | The latest items from a news feed (RSS or Atom), newest first, as records: feed, title, link, date, summary. Leave it empty for your own feeds (feeds = … in second-thought.ini). On this page it uses sample feeds. | read news feeds | no |
| when there's something new in feed *url*<br>`rb_feed_when` | Runs the blocks below for each new item in a news feed (checked every 15 minutes). Leave it empty for your own feeds. 'What arrived' gives feed, title, link, date, summary and text. | read news feeds | no |

## Files and folders

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| files in folder *folder* matching *match*<br>`rb_folder_files` | The files in a folder, newest first, as records: name, path, modified and size. Matching is a pattern like *.pdf; leave it empty for every file. It only looks: it doesn't read them. Exported Python looks in the folder (next to the program, unless you give a full path); this page uses sample files. | look at the files in a folder, and watch it for new ones | no |
| when a file appears in folder *folder*<br>`rb_folder_when` | Runs the blocks below when a new file lands in this folder (next to the program, unless you give a full path). 'What arrived' gives its name, path, size, and the words in it for a PDF, Word or text file. For a picture, 'picture' gives it to the picture blocks. | look at the files in a folder, and watch it for new ones | no |

## GitHub

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| when a new issue is opened in *repo*<br>`rb_gh_issue_when` | Runs the blocks below when someone opens an issue in this GitHub project (checked every 5 minutes; pull requests don't count). 'What arrived' gives repo, number, title, body, author, labels, link and text. | look at your GitHub projects | no |
| when a release is published in *repo*<br>`rb_gh_release_when` | Runs the blocks below when this GitHub project publishes a release (checked every 15 minutes). 'What arrived' gives repo, tag, name, previous_tag, notes, link and text. | look at your GitHub projects | no |
| when a pull request asks for my review<br>`rb_gh_when` | Runs the blocks below when someone asks you to review a GitHub pull request (checked every 5 minutes). 'What arrived' gives repo, number, title, user, link and text. | look at your GitHub projects | no |

## Home Assistant

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| *attr* of entity *entity*<br>`rb_ha_attr` | One attribute of an entity, for example 'current_temperature' or 'friendly_name'. | look at your Home Assistant devices | no |
| call *service* on *entity* with *data*<br>`rb_ha_call` | Calls a service, for example light.turn_off. Optional data is JSON like {"temperature": 20}. Unlocking, opening and disarming always ask you first. | control your Home Assistant devices | before its first run |
| when Home Assistant event *event* happens with *data*<br>`rb_ha_event_when` | Runs the blocks below the moment Home Assistant sends this event: a button or remote press (zha_event, deconz_event), an automation firing (automation_triggered), a phone notification action, or your own event. Type 'anything' for every event. The second box is optional words the event's data must contain, such as the remote's name. 'What arrived' gives event_type, entity, data, time and text, plus each field of the event's data. On this page, right-click it and choose 'Run this script' to try it with a sample event. | look at your Home Assistant devices | no |
| entities matching *text*<br>`rb_ha_find` | A list of records (entity, name, state, unit, area) for every entity whose id, name, area or state contains all these words. '*' means everything. | look at your Home Assistant devices | no |
| history of *entity* for the last *hours* hours<br>`rb_ha_history` | A list of records (time, state) showing how the entity changed. | look at your Home Assistant devices | no |
| notify *target* : *text*<br>`rb_ha_notify` | Sends a notification. Target is a notify service such as notify.mobile_app_my_phone, or persistent_notification for the Home Assistant sidebar. | control your Home Assistant devices | before its first run |
| snapshot from *camera*<br>`rb_ha_snapshot` | A picture from a camera entity. Use it with the Pictures blocks. | look at your Home Assistant devices | no |
| say *text* on *player*<br>`rb_ha_speak` | Speaks the text on a media player, using Home Assistant's text-to-speech. | control your Home Assistant devices | before its first run |
| state of *entity*<br>`rb_ha_state` | The entity's current state, for example 'on', 'locked' or 19.5. | look at your Home Assistant devices | no |
| readings for *text*<br>`rb_ha_summary` | A plain-text list of matching entities and their states, ready to put into a question for Claude. | look at your Home Assistant devices | no |
| what changed<br>`rb_ha_trigger` | In a 'when … changes' script: a record with entity, name, from and to. | look at your Home Assistant devices | no |
| when *entity* changes to *state*<br>`rb_ha_when` | Runs the blocks below when this entity changes. Type 'anything' to react to any change. Inside, 'what changed' says what happened. | look at your Home Assistant devices | no |

## Homey

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| Homey devices matching *text*<br>`rb_homey_find` | A list of records, one for each device whose name, zone or kind contains all these words ('*' for every device): name, zone, class, and each of its values. | look at your Homey devices, flows and variables | no |
| run Homey flow *name*<br>`rb_homey_flow` | Starts one of your Homey flows, by its name. A flow can do anything your Homey can, including sending a Homey notification. | control your Homey devices and start Homey flows | before its first run |
| set Homey device *device* *capability* to *value*<br>`rb_homey_set` | Sets a value, like onoff to off, dim to 0.5 or target_temperature to 19. 'Ask me before any smart home action' makes it ask first; unlocking, opening and disarming always ask. On this page it changes the sample home. | control your Homey devices and start Homey flows | before its first run |
| set Homey variable *name* to *value*<br>`rb_homey_set_variable` | Changes a Homey Logic variable, so your flows can use it. | control your Homey devices and start Homey flows | before its first run |
| *capability* of Homey device *device*<br>`rb_homey_value` | One value of a Homey device, by the device's name: onoff (on or off), dim (0 to 1), measure_temperature, measure_power and so on. 'Homey devices matching' shows what each device has. | look at your Homey devices, flows and variables | no |
| Homey variable *name*<br>`rb_homey_variable` | The value of a Homey Logic variable, by its name. | look at your Homey devices, flows and variables | no |
| when Homey device *device* *capability* changes<br>`rb_homey_when` | Runs the blocks below when this Homey device's value changes (checked every 10 seconds). Type 'anything' for any of its values. 'What arrived' gives device, zone, capability, from, to and text. On this page, right-click it and choose 'Run this script' to try it. | look at your Homey devices, flows and variables | no |

## MikroTik

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| MikroTik health<br>`rb_mikrotik_health` | A record about the router or switch itself: board, version, uptime, cpu_load (%), free_memory (MB), temperature (°C), and any other sensors it has. | read your MikroTik router or switch: its ports, modules, health and log | no |
| MikroTik log, last *n* lines<br>`rb_mikrotik_log` | The last lines of the router's log, oldest first, each as "time topics: message". | read your MikroTik router or switch: its ports, modules, health and log | no |
| MikroTik ports<br>`rb_mikrotik_ports` | A list of records, one for each port on your MikroTik router or switch: port, running, speed (like 10Gbps), errors, drops, link_downs and comment. Errors and drops count from when it last started. It only reads: nothing on the switch changes. On this page it uses a sample switch. | read your MikroTik router or switch: its ports, modules, health and log | no |
| MikroTik SFP modules<br>`rb_mikrotik_sfp` | A list of records, one for each SFP module plugged in: port, module, temperature (°C), rx_power and tx_power (dBm). | read your MikroTik router or switch: its ports, modules, health and log | no |

## MQTT

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| publish MQTT *text* to topic *topic* keep it *retain*<br>`rb_mqtt_publish` | Sends a message to your MQTT broker. 'Keep it' asks the broker to remember it for anyone who listens later. 'Ask me before any Home Assistant action' or 'sending messages' makes it ask first. On this page it's only shown. | publish MQTT messages | before its first run |
| latest MQTT message on *topic*<br>`rb_mqtt_read` | The latest message on an MQTT topic. Only messages the broker keeps (retained) show up straight away. With + or # in the topic, a record of each topic's latest message. On this page it uses sample topics. | read MQTT messages | no |
| when an MQTT message arrives on *topic*<br>`rb_mqtt_when` | Runs the blocks below when a message arrives on this MQTT topic. + stands for one level and # for everything below, like zigbee2mqtt/#. 'What arrived' gives its topic and text, plus the fields of a JSON message. | read MQTT messages | no |

## NZBGeek

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| fetch the NZB for *id*<br>`rb_nzbgeek_fetch` | Fetches one release's NZB file and saves it as <id>.nzb. It always asks you first, even when nothing else asks, and with nobody there to say yes it doesn't run. It never hands anything to a downloader: the file is saved, that's all. On this page nothing really fetches. | fetch an NZB file from NZBGeek and save it (asking you each time) | every time |
| search NZBGeek for *query*<br>`rb_nzbgeek_search` | A list of records, one for each release the indexer has for these words: title, id, size_mb, grabs, posted (when it was posted) and group. It only reads: nothing is ever downloaded. Needs NZBGEEK_API_KEY in second-thought.ini. On this page it uses a sample search. | search NZBGeek, the Usenet indexer, and read what it has: titles, sizes, ages and groups | no |

## Pi-hole

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| *action* *domain* on Pi-hole's allow list<br>`rb_pihole_allow` | Puts a domain on the allow list, or takes it off. It always asks you first, even when nothing else asks, and with nobody there to say yes it doesn't run. On this page nothing really changes. | disable and enable your Pi-hole's blocking, and change its allow and deny lists (asking you each time) | every time |
| disable Pi-hole blocking for *n* seconds<br>`rb_pihole_blocking` | Turns blocking off for that many seconds, then Pi-hole turns it back on itself. It always asks you first, even when nothing else asks, and with nobody there to say yes it doesn't run. On this page nothing really changes. | disable and enable your Pi-hole's blocking, and change its allow and deny lists (asking you each time) | every time |
| *action* *domain* on Pi-hole's deny list<br>`rb_pihole_deny` | Puts a domain on the deny list, or takes it off. It always asks you first, even when nothing else asks, and with nobody there to say yes it doesn't run. On this page nothing really changes. | disable and enable your Pi-hole's blocking, and change its allow and deny lists (asking you each time) | every time |
| enable Pi-hole blocking<br>`rb_pihole_enable` | Turns blocking back on. It always asks you first, even when nothing else asks, and with nobody there to say yes it doesn't run. On this page nothing really changes. | disable and enable your Pi-hole's blocking, and change its allow and deny lists (asking you each time) | every time |
| Pi-hole summary<br>`rb_pihole_summary` | One record for today: queries (how many DNS queries), blocked (how many were blocked), blocked_pct (the blocked share), gravity (how many domains the lists have), clients (how many devices asked) and blocking (whether blocking is on). Needs PIHOLE_URL and PIHOLE_PASSWORD in second-thought.ini. On this page it uses a sample Pi-hole. | read your Pi-hole: today's queries and blocked share, the top blocked domains and clients, and whether blocking is on | no |
| top *n* clients<br>`rb_pihole_top_clients` | A list of records, one for each of the devices that asked the most: name, ip and count (how many queries). It only reads. | read your Pi-hole: today's queries and blocked share, the top blocked domains and clients, and whether blocking is on | no |
| top *n* blocked domains<br>`rb_pihole_top_domains` | A list of records, one for each of the most-blocked domains: domain and count (how many times it was blocked). It only reads. | read your Pi-hole: today's queries and blocked share, the top blocked domains and clients, and whether blocking is on | no |

## Plex

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| Plex libraries<br>`rb_plex_libraries` | A list of records, one for each library: name, type (movie, show or artist) and count (how many items it has). It only reads. | read your Plex: the server, its libraries, what's playing now and the newest items; and read Tautulli's history and watch-time stats | no |
| Plex new items, last *n* days<br>`rb_plex_recent` | A list of records, one for each item added in that many days: title, library and added (when it was added). It only reads. | read your Plex: the server, its libraries, what's playing now and the newest items; and read Tautulli's history and watch-time stats | no |
| scan the *library* library on Plex<br>`rb_plex_scan` | Scans one library for new files. It always asks you first, even when nothing else asks, and with nobody there to say yes it doesn't run. On this page nothing really changes. | scan a Plex library, and stop a stream on Plex (asking you each time) | every time |
| Plex server<br>`rb_plex_server` | One record for the server: name, version and up (it answered, so it's up). Needs PLEX_URL and PLEX_TOKEN in second-thought.ini. On this page it uses a sample server. | read your Plex: the server, its libraries, what's playing now and the newest items; and read Tautulli's history and watch-time stats | no |
| Plex sessions<br>`rb_plex_sessions` | A list of records, one for each thing playing now: id (the session's id), user, title, player, state (playing or paused) and transcode (whether the server is transcoding it). It only reads. | read your Plex: the server, its libraries, what's playing now and the newest items; and read Tautulli's history and watch-time stats | no |
| stop the *id* stream on Plex<br>`rb_plex_stop` | Stops one stream (Tautulli's terminate). It always asks you first, even when nothing else asks, and with nobody there to say yes it doesn't run. On this page nothing really changes. | scan a Plex library, and stop a stream on Plex (asking you each time) | every time |
| Tautulli history, last *n* days<br>`rb_tautulli_history` | A list of records, one for each thing watched in that many days, from Tautulli: user, title, when and transcode (whether it was transcoded). It only reads. Needs TAUTULLI_URL and TAUTULLI_API_KEY in second-thought.ini. | read your Plex: the server, its libraries, what's playing now and the newest items; and read Tautulli's history and watch-time stats | no |
| Tautulli watch time, last *n* days<br>`rb_tautulli_watchtime` | A list of records, one for each person who watched in that many days, from Tautulli: user and hours. It only reads. | read your Plex: the server, its libraries, what's playing now and the newest items; and read Tautulli's history and watch-time stats | no |

## Powerwall

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| Powerwall figures<br>`rb_powerwall_now` | A record of your Tesla Powerwall's figures: battery_soc_pct (its charge), solar_power_w (making now), battery_power_w (positive is charging), grid_power_w (positive is importing), load_power_w (the house), reserve_pct (the backup reserve it keeps), mode (self_consumption, backup, ...) and grid (connected, or islanded in a power cut). It only reads. Needs POWERWALL_URL and POWERWALL_PASSWORD in second-thought.ini. On this page it uses a sample Powerwall. | read your Powerwall's figures: battery charge, solar, grid import and export, and the reserve it keeps | no |
| set Powerwall backup reserve to *n* %<br>`rb_powerwall_reserve` | Raises or lowers the backup reserve: how much of the battery the house keeps for a power cut. It always asks you first, even when nothing else asks, and with nobody there to say yes it doesn't run. Needs POWERWALL_URL and POWERWALL_PASSWORD in second-thought.ini. On this page nothing really changes. | set your Powerwall's backup reserve (asking you each time) | every time |

## Proxmox

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| Proxmox guests<br>`rb_proxmox_guests` | A list of records, one for each VM and container: vmid, name, node, type (vm or container), status, cpu and memory (%), uptime (hours), and for one that's stopped, onboot (whether it should start with the node). | read your Proxmox cluster: nodes, guests, storage and tasks | no |
| Proxmox nodes<br>`rb_proxmox_nodes` | A list of records, one for each node in your Proxmox cluster: node, status, cpu and memory (%), uptime (hours). On this page it uses a sample cluster. | read your Proxmox cluster: nodes, guests, storage and tasks | no |
| *action* Proxmox guest *vmid*<br>`rb_proxmox_power` | Starts, shuts down or reboots one VM or container, by its VMID. It always asks you first, even when nothing else asks, and with nobody there to say yes it doesn't run. Guests listed in PROXMOX_PROTECT are never touched. Needs a token with VM.PowerMgmt. On this page nothing really starts or stops. | start, shut down and reboot your Proxmox guests (asking you each time) | every time |
| Proxmox storage<br>`rb_proxmox_storage` | A list of records, one for each storage on each node: storage, node, used (%), used_gb, size_gb and status. | read your Proxmox cluster: nodes, guests, storage and tasks | no |
| Proxmox tasks of the last *n* hours<br>`rb_proxmox_tasks` | A list of records, newest first: started, node, type (vzdump is a backup), id (the guest), status (OK, or what went wrong) and user. | read your Proxmox cluster: nodes, guests, storage and tasks | no |

## SABnzbd

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| SABnzbd diskspace<br>`rb_sabnzbd_diskspace` | A list of records, one for each of SABnzbd's folders (the download folder first): folder and free_gb. | read your SABnzbd: the download queue, its history and the download disk's free space | no |
| SABnzbd history, last *n* hours<br>`rb_sabnzbd_history` | A list of records, one for each job that finished in that time: name, status (Completed or Failed), size_mb, when it finished and, for a failure, why it failed. | read your SABnzbd: the download queue, its history and the download disk's free space | no |
| *action* SABnzbd<br>`rb_sabnzbd_pause` | Pauses or resumes the whole download queue. It always asks you first, even when nothing else asks, and with nobody there to say yes it doesn't run. On this page nothing really pauses. | pause and resume your SABnzbd downloads (asking you each time) | every time |
| SABnzbd queue<br>`rb_sabnzbd_queue` | A list of records, one for each job in the download queue: name, size_mb, left_mb, percent, eta (time left, like 0:12:34) and status (Downloading, Queued, Paused). On this page it uses a sample queue. | read your SABnzbd: the download queue, its history and the download disk's free space | no |

## Solax

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| Solax figures<br>`rb_solax_now` | A record of your Solax inverter's figures, as SolaxCloud last had them (they update about every five minutes): ac_power_w (what it's making now), yield_today_kwh and yield_total_kwh (solar generated), feedin_power_w and feedin_energy_kwh (to the grid), import_energy_kwh (from the grid), battery_soc_pct, status and upload_time. It only reads: nothing on the inverter changes. Needs SOLAX_TOKEN_ID and SOLAX_SN in second-thought.ini. On this page it uses a sample inverter. | read your Solax inverter's figures from SolaxCloud: solar generation, battery charge, import and export | no |

## Telegram

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| Telegram message *part*<br>`rb_tg_message` | The Telegram message that started this script: its words, who sent it, or the chat. Empty outside a Telegram script. | read your Telegram messages | no |
| send Telegram message *text*<br>`rb_tg_send` | Sends a message from your bot: back to the chat a message came from, or to TELEGRAM_CHAT_ID. 'Ask me before sending messages' makes it ask first. On this page it's only shown. | send Telegram messages | before its first run |
| when a Telegram message arrives containing *contains*<br>`rb_tg_when` | Runs the blocks below when your bot gets a message (type 'anything', or words the message must contain). Only messages from your own chats count (TELEGRAM_CHAT_ID). In exported Python it listens all the time; on this page, right-click it and choose 'Run this script' to try it with a sample message. | read your Telegram messages | no |

## UniFi

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| UniFi clients<br>`rb_unifi_clients` | A list of records, one for each device connected to your UniFi network: name, mac, ip, type (wired, wireless or vpn), connected (since when) and uplink (the UniFi device it's connected through). It only reads: nothing is blocked or changed. On this page it uses a sample network. | read your UniFi network: who's connected, and how your UniFi devices are | no |
| UniFi devices<br>`rb_unifi_devices` | A list of records, one for each UniFi device (gateway, switches, access points): name, model, mac, ip, state, firmware, update (whether newer firmware is waiting), and for one that's online, uptime (hours), cpu and memory (%). | read your UniFi network: who's connected, and how your UniFi devices are | no |

## Unraid

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| Unraid array<br>`rb_unraid_array` | One record for the array: state (STARTED, STOPPED, ...), started (whether it's started), free_gb, total_gb and uptime. On this page it uses a sample server. | read your Unraid server: the array, its disks, its shares, its containers and its VMs | no |
| *action* Unraid container *name*<br>`rb_unraid_container_power` | Starts or stops one Docker container, by its name. It always asks you first, even when nothing else asks, and with nobody there to say yes it doesn't run. On this page nothing really starts or stops. | start and stop your Unraid's containers and VMs, and check its parity (asking you each time) | every time |
| Unraid containers<br>`rb_unraid_containers` | A list of records, one for each Docker container: name, state (running, exited, ...), status and auto_start (whether Unraid starts it with the array). | read your Unraid server: the array, its disks, its shares, its containers and its VMs | no |
| Unraid disks<br>`rb_unraid_disks` | A list of records, one for each disk in the array, parity first then data then cache: name, type, status (DISK_OK, DISK_NP, ...), temp_c, errors, size_gb and free_gb. | read your Unraid server: the array, its disks, its shares, its containers and its VMs | no |
| check Unraid's parity<br>`rb_unraid_parity` | Checks the parity disks by reading them, writing no corrections. It always asks you first, even when nothing else asks, and with nobody there to say yes it doesn't run. On this page nothing really checks. | start and stop your Unraid's containers and VMs, and check its parity (asking you each time) | every time |
| Unraid shares<br>`rb_unraid_shares` | A list of records, one for each user share: name, free_gb, used_gb and total_gb. | read your Unraid server: the array, its disks, its shares, its containers and its VMs | no |
| *action* Unraid VM *name*<br>`rb_unraid_vm_power` | Starts or stops one virtual machine, by its name. It always asks you first, even when nothing else asks, and with nobody there to say yes it doesn't run. On this page nothing really starts or stops. | start and stop your Unraid's containers and VMs, and check its parity (asking you each time) | every time |
| Unraid VMs<br>`rb_unraid_vms` | A list of records, one for each virtual machine: name and state (RUNNING, SHUTOFF, ...). | read your Unraid server: the array, its disks, its shares, its containers and its VMs | no |

## Web

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| when the web page *url* changes<br>`rb_page_when` | Runs the blocks below when the words on a web page change. Leave 'only the part containing' empty to watch the whole page, or type words (like Price) to watch just the lines with them and the two lines after each, so adverts and counters elsewhere on the page don't count. The first check only remembers the page. 'What arrived' gives url, title, before, after, changed (the lines that changed) and text. Pages that need a browser to show their words can't be watched. On this page, right-click it and choose 'Run this script' to try it with a sample page. | read public web pages and search the web | no |
| when a web request arrives at / *path*<br>`rb_webhook_when` | Runs the blocks below when something (Home Assistant, IFTTT, a shortcut on your phone) calls http://<this computer>:8765/bake-done?key=<WEBHOOK_SECRET>. Requests without the key are refused. 'What arrived' gives the text sent, and the fields of JSON or of the address. | accept web requests from other computers | before its first run |

## Output

| Block | What it does | Lets a program | Asks first |
|---|---|---|---|
| add *text* to the result<br>`rb_add_result` | — | nothing to declare | no |
| finish with *text*<br>`rb_finish_with` | — | nothing to declare | no |
| finish and show the result<br>`rb_result` | Ends the run. Shows what you added to the result, or the draft if you added nothing. | nothing to declare | no |
| say *text*<br>`rb_say` | Writes a note in the run log. | nothing to declare | no |
| show the draft in the log<br>`rb_show` | — | nothing to declare | no |
