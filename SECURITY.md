# Security

## Reporting a problem

Please don't open a public issue for a security problem. Use **Report a vulnerability** on this repository's
**Security** tab, which sends a private report. Include what an attacker could do, the steps to reproduce it, and the
runtime version (`python my-program.py --version`). You'll get a reply as soon as it's been looked at; fixes go out
as a new runtime version, noted in [CHANGELOG.md](CHANGELOG.md).

Fixes are made to the latest runtime only. An exported program keeps the runtime it was exported with, so to get a
fix, import the program on the page and export it again.

## What an exported program can do

An exported program runs as you, on your computer, with the keys in its `second-thought.ini`. What it can do is
decided by its blocks, and every block declares it (the `CAPABILITIES` list in `python/second_thought/core.py`):

- **Act:** send email, Telegram, Discord or Slack messages; comment on GitHub; control Home Assistant or Homey
  devices and start Homey flows; publish MQTT messages; accept web requests from other computers; use the tools of
  MCP servers you set up.
- **Read:** web pages and search, your email, calendars, news feeds, GitHub, Telegram, Discord and Slack messages,
  Home Assistant, Homey and MQTT, a folder it watches, and files you choose.
- **Keep:** files in its `outputs` folder, and notes between runs in `memory.json`.

Everything it reads and writes is sent to the model services it uses.

## What limits it

- **Approval before the first run.** A program that can act lists what it can do and asks before its first run.
  The answer is remembered against a hash of the program, so a changed program asks again. A scheduled program won't
  start until it has been approved once, unless you set `approve = no`.
- **Asking before each action.** Agent tools that send or change something ask before each use, unless you choose a
  **(no asking)** variant. **ask me before …** blocks do the same for ordinary blocks. Unlocking, opening the garage
  and switching off an alarm always ask. With nobody there to answer, the answer is no.
- **Untrusted text stays text.** An agent only reads what its tools return; it's told never to follow instructions
  inside it. Treat this as a mitigation, not a guarantee: anything an agent reads (an email, a web page, a pull
  request) can try to steer it, which is why acting tools ask first.
- **Web requests.** The listener only starts once `WEBHOOK_SECRET` is set, refuses requests without the secret
  (compared in constant time), and listens on `127.0.0.1` unless you set `WEBHOOK_HOST`.
- **No local network by default.** The agent's web tools read only public addresses, never ones on your own
  network, unless you set `local_pages = yes`.
- **MCP servers run with your permissions.** A server named by a command in `second-thought.ini` is started as you
  and can do whatever that command can. Only add servers you trust.
- **Keys stay out of the program.** Keys live in `second-thought.ini` or environment variables, never in the
  exported `.py` file. `second-thought.ini` is git-ignored here; keep yours private.

## On the page

The page runs inside claude.ai and uses your claude.ai account for Claude. It never asks for API keys. The
connection blocks (feeds, GitHub, email, Telegram, calendar, Home Assistant, Homey) use sample data on the page, so
nothing real is read or sent until you export a program and set it up.
