# Connections

[← Second Thought](../README.md) · [Using the page](using-the-page.md) · [The agent](agent.md) · **Connections** · [MCP tools](mcp.md) · [Running exported programs](running.md) · [Settings and models](settings.md)

*What programs connect to: Telegram, email, calendars, feeds, web requests, GitHub, Home Assistant, Homey, Coinbase, MikroTik, UniFi and Proxmox.*

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

To keep listening all the time, run the program with **run-on-schedule** (see [Running on a schedule](running.md#running-on-a-schedule)). Things that arrived while it was off don't start the script: Telegram messages are kept for searching, and the email, feed, GitHub and folder listeners start from what's new after the program starts.

## Home Assistant

![The Home Assistant panel on the page, listing the sample house's people, weather, bins and calendar with their states](../screenshots/home-assistant.png)

Second Thought talks to [Home Assistant](https://www.home-assistant.io), with its own blue blocks:

- Read state: "Is the back door open?"
- Take a camera snapshot, so a model can say who is at the door.
- Turn a light off, or send a notification to a phone.
- A yellow block starts a script when something changes, like the doorbell ringing.
- Another starts a script the moment Home Assistant fires an **event**, like a button on a remote.

On the page, these blocks use a **sample house**, so you can try everything safely. Press **Home Assistant** to see it, change something (the doorbell, say), and watch your program react. There are more than 60 Home Assistant examples in **Browse examples**.

**Safety rule:** Second Thought never unlocks a door, opens the garage or switches off the alarm without asking you first.

**Using your real Home Assistant.** Export the program and unzip it on a computer on the same network. Make a long-lived access token in Home Assistant (your profile, then the Security tab), and put it in `second-thought.ini`:

```
[home assistant]
HA_URL = http://homeassistant.local:8123
HA_TOKEN = your-long-lived-token
```

Then run `run-on-schedule.bat` (Windows) or `sh run-on-schedule.sh` (Linux or Mac). On an always-on Linux computer, `sh install-service.sh` keeps it running for good. A small always-on virtual machine or container is a good home for it.

`--schedule` keeps it running, so timed jobs and "when it changes" scripts start by themselves. **when Home Assistant event … happens with …** listens on Home Assistant's WebSocket, using the same `HA_URL` and `HA_TOKEN`, so it reacts at once instead of polling. Use it for remote and button presses (`zha_event`, `deconz_event`, `hue_event`), `automation_triggered`, phone notification actions or your own events. Type `anything` for every event. The second box is optional words the event's data must contain, like the remote's name. **what arrived** gives `event_type`, `entity`, `data`, `time`, `text`, and each field of the event's data, like `command`. *Developer tools → Events* in Home Assistant shows what your devices send.

## Homey

Second Thought also talks to **Homey Pro**, with its own green blocks under **Homey**:

- **when Homey device … … changes** starts a script when a device's value changes, like the washing machine's power dropping. **what arrived** says which device, what changed, and from what to what.
- **… of Homey device …** reads one value, like `measure_temperature` of the Proofing box.
- **Homey devices matching …** lists devices and everything they report.
- **set Homey device … … to …** switches something, like `onoff` to `off` or `dim` to `0.5`.
- **run Homey flow …** starts one of your flows. A flow can do anything your Homey can, like sending a Homey notification.
- **Homey variable …** and **set Homey variable … to …** read and change your Logic variables, so your flows can use them.

There are agent tools too, under **Tools**: **Homey: look at devices, flows and variables**, and **Homey: control devices and start flows**, which asks you before each change. On the page these blocks use a **sample Homey home**; try the examples under **Homey** in **Browse examples**. The same safety rule applies: unlocking, opening the garage and switching off the alarm always ask you first.

**Using your real Homey.** In the Homey Web App (my.homey.app), open Settings, then API Keys, and make a new key with only the permissions the program needs: view devices, control devices, view and start flows, and view and edit Logic. Put it in `second-thought.ini` with your Homey's address:

```
[homey]
HOMEY_URL = http://homey-XXXXXXX.local
HOMEY_API_KEY = your-api-key
```

The address is in the Homey app under Settings, General. The computer running the program must be on the same network. API keys work with Homey Pro (2023 and later) and Homey Pro mini.

**Homey Self-Hosted Server** serves the same API on port **4859**, so use the address of the computer it runs on, with `:4859` on the end:

```
HOMEY_URL = http://192.168.1.20:4859
```

Make the API key in the Homey Web App the same way. A **Homey Bridge** connected to a Self-Hosted Server needs nothing of its own: its devices show up through the server. To check it all works, run `python tools/smoke_test.py homey`. It only reads, so nothing is switched.

## Coinbase

The blue **Coinbase** blocks read your Coinbase account through its Advanced Trade API, and can place orders, always asking first:

- **Coinbase balances** lists each asset in your portfolio, biggest first: asset, amount, value and currency. Values are in your currency (`currency` in `second-thought.ini`).
- **Coinbase portfolio value** is what the whole portfolio is worth.
- **price of … on Coinbase** gives a trading pair's latest price, like BTC-GBP's in pounds; choose **24-hour change %** for how much it moved.
- **Coinbase daily prices of … for the last …** gives a record for each day (or hour): time, open, high, low, close and volume, oldest first.
- **Coinbase open orders** and **recent fills** list your orders and trades.
- **preview Coinbase order: buy … of …** says what a market order would come to, without placing it: size, spend, fee, total, slippage and warnings. **Buy** spends an amount of the second currency (50 of BTC-GBP spends £50); **sell** sells an amount of the first (0.01 of BTC-GBP sells 0.01 BTC).
- **place Coinbase order** and **cancel Coinbase order** move real money. They always ask you first, even when nothing else does, and the question shows the preview's fee and total. With nobody there to say yes (a schedule, GitHub Actions, a program serving as an MCP tool), they don't run; `approve_by = telegram` asks on your phone instead.

Only spot trading pairs are offered, and nothing converts, transfers or withdraws. On the page these blocks use a **sample portfolio**, in pounds, and nothing is bought or sold. Two gallery programs use them: **Weekly crypto round-up** and **Tell me if BTC drops 10%**. Both only read.

**Using your real account.** At [portal.cdp.coinbase.com](https://portal.cdp.coinbase.com), open API Keys and create one. Under its advanced settings choose **ECDSA** (Advanced Trade doesn't take Ed25519 keys), limit it to **one portfolio**, and give it **View** permission only, unless the program places orders (then View and Trade). Never give it Transfer. Save the key file it downloads next to the program, and name it in `second-thought.ini`:

```
[coinbase]
COINBASE_KEY_FILE = cdp_api_key.json
```

Or put the file's contents in `COINBASE_KEY` (in the keychain, say). Each request is signed with the key, which needs `pip install cryptography`; `run.bat` and `run.sh` install it. `--doctor` checks the key, and says if it can trade when the program only reads, or can't when it places orders.

## Proxmox

The orange **Proxmox** blocks read a Proxmox VE cluster through its REST API, and can start, shut down and reboot guests, always asking first:

- **Proxmox nodes**: node, status, cpu and memory (%), uptime (hours).
- **Proxmox guests**: each VM and container's vmid, name, node, type, status, cpu, memory and uptime, and for one that's stopped, onboot (whether it should start with the node).
- **Proxmox storage**: each storage on each node, with used (%), used_gb, size_gb and status.
- **Proxmox tasks of the last … hours**: started, node, type (vzdump is a backup), id, status (OK, or what went wrong) and user.
- **start / shut down / reboot Proxmox guest …** asks you every time, even when nothing else does, with the guest's name, node and state. With nobody there to say yes (a schedule, GitHub Actions), it doesn't run; `approve_by = telegram` asks on your phone instead. Guests listed in `PROXMOX_PROTECT` are never touched at all: your Home Assistant or domain controller, say.

Nothing else is ever sent: no destroying, snapshots, migrating, commands in a guest, or storage, permission or firewall changes. On the page these blocks use a **sample cluster**, where last night's backup of one guest failed and a storage is 88% full. The gallery program **Morning cluster check** reports each morning, and only reads.

**Using your own cluster.** In Proxmox, open Datacenter, Permissions, API Tokens, and make a token for a user with the **PVEAuditor** role (read-only). If the program starts or stops guests, give it VM.PowerMgmt too. Then:

```
[proxmox]
PROXMOX_URL = https://pve.local:8006
PROXMOX_TOKEN_ID = monitor@pve!second-thought
PROXMOX_TOKEN_SECRET = …
PROXMOX_CERT_SHA256 =
PROXMOX_PROTECT = 100, 101
```

Run `--doctor` once: it shows the node's certificate fingerprint to pin, then says what the token may do.

## UniFi

The teal **UniFi** blocks read your UniFi network through the Network API on a UniFi OS console (a Cloud Gateway or a Dream Machine). They only read: nothing is blocked, reconnected, restarted or reconfigured, and the firewall, VLANs and WiFi are never touched.

- **UniFi clients** lists who's connected: name, mac, ip, type (wired, wireless or vpn), connected (since when) and uplink (the UniFi device it comes through).
- **UniFi devices** lists your gateway, switches and access points: name, model, mac, ip, state, firmware, update (whether newer firmware is waiting), and for one that's online, uptime (hours), cpu and memory (%).

On the page they use a **sample network**, with an unnamed newcomer on the IoT network and an access point offline. The gallery program **Who's on the network?** reports what's new each morning.

**Using your own network.** In the Network app, open Settings, Control Plane, Integrations and create an API key. Then:

```
[unifi]
UNIFI_URL = https://192.168.1.1
UNIFI_API_KEY = …
UNIFI_CERT_SHA256 =
```

As with MikroTik, the console's certificate is its own: run `--doctor` once and it shows the fingerprint to pin. `UNIFI_SITE` picks a site other than the first. The key itself could do more than read (restart a device, block a client), but Second Thought only ever sends the reads in `unifi_free`; keep the key for this program alone.

## MikroTik

The brown **MikroTik** blocks read a MikroTik router or switch through RouterOS 7's REST API. They only read: nothing on the switch is ever changed, and there's no reboot. A switch that loses its config takes the network with it.

- **MikroTik ports** lists each port: port, running, speed (as RouterOS says it, like 10Gbps), errors, drops, link_downs and comment. Errors and drops count from when the switch last started.
- **MikroTik SFP modules** lists each module plugged in: port, module, temperature (°C), rx_power and tx_power (dBm).
- **MikroTik health** is a record about the switch itself: board, version, uptime, cpu_load, free_memory (MB), temperature, and any other sensors it has.
- **MikroTik log, last … lines** gives the end of its log.

On the page they use a **sample switch**, whose NAS port came up at 1Gbps. The gallery program **Is the 10Gb link at 10Gb?** checks that each morning.

**Using your own switch.** In RouterOS, turn on the `www-ssl` service, make a group with only the `read`, `api` and `rest-api` policies, and a user in it for Second Thought. Then:

```
[mikrotik]
MIKROTIK_URL = https://192.168.88.1
MIKROTIK_USER = monitor
MIKROTIK_PASSWORD = …
MIKROTIK_CERT_SHA256 =
```

A router's certificate is usually its own, which your computer doesn't trust. Run `--doctor` once: it shows the certificate's fingerprint, and once you've put it in `MIKROTIK_CERT_SHA256`, the program talks to that router only. `--doctor` also says if the user's group can do more than read.

---

Next: [MCP tools](mcp.md) · [Back to the README](../README.md)
