# Security

## Reporting a problem

Please don't open a public issue for a security problem. Use **Report a vulnerability** on this repository's
**Security** tab, which sends a private report. Include what an attacker could do, the steps to reproduce it, and the
runtime version (`python my-program.py --version`). You'll get a reply as soon as it's been looked at; fixes go out
as a new runtime version, noted in [CHANGELOG.md](CHANGELOG.md).

Fixes are made to the latest runtime only. An exported program keeps the runtime it was exported with, so a fix
reaches it in one of two ways. `python my-program.py --update-runtime` puts the newest release of the same major
version into the file in place, after checking it against the SHA-256 published with the release. For a new major
version, import the program on the page and export it again. `--doctor` says when a newer runtime is out, and fails
when the release says it fixes a security problem. Programs exported before 3.1.0 need exporting again once.

## What the SHA-256 check proves, and what it doesn't

`--update-runtime` downloads the release's `runtime.py` and refuses it unless it matches `runtime.py.sha256`, published
with the same release. That proves the download arrived intact: a corrupted or truncated file won't match. It can't
prove the runtime is the one the project meant to publish, because both files come from the same place: the release,
and its fingerprint with it, are made by the same GitHub account and workflow. Whoever could publish a release, or take
over the account or the repository, could make a changed `runtime.py` and its matching SHA-256 together, and the check
would pass. The runtime is code that then runs as you, with your permissions and your keys, so this is a limit to know
about, not a corner case.

Updating is always your choice: nothing updates itself, and `--update-runtime` writes the new runtime only when you run
it. To check a release by hand instead, compare its `runtime.py` with the tagged source: check out the release's tag,
run `python tools/sync.py --check` (which rebuilds `python/runtime.py` from the sources and says if they disagree), and
compare the result with the file attached to the release. A release that doesn't match its own tagged source is one not
to use.

Releases are also signed with an Ed25519 key kept off GitHub ([#311](https://github.com/itsfja/second-thought/issues/311)):
`tools/sign_runtime.py` signs each release's `runtime.py` on the maintainer's computer, the `.sig` is attached to the
release, and the runtime holds the key's public half (`UPDATE_SIGNING_KEY` in update.py), so `--update-runtime` refuses
a runtime that isn't signed by it — whoever can publish a release, or take over the account, can't make a matching
pair the way they can with the SHA-256. Until the first signed release, the key is empty and only the SHA-256 applies.

## What an exported program can do

An exported program runs as you, on your computer, with the keys in its `second-thought.ini`. What it can do is
decided by its blocks, and every block declares it (the `CAPABILITIES` list in `python/second_thought/core.py`):

- **Act:** send email, Telegram, Discord or Slack messages; comment on GitHub; control Home Assistant or Homey
  devices and start Homey flows; publish MQTT messages; accept web requests from other computers; use the tools of
  MCP servers you set up; place and cancel Coinbase orders.
- **Read:** web pages and search, your email, calendars, news feeds, GitHub, Telegram, Discord and Slack messages,
  Home Assistant, Homey and MQTT, your Coinbase balances and orders, your MikroTik switch's ports and log, who's on your UniFi network, a folder it watches, and files you choose.
- **Keep:** files in its `outputs` folder, and notes between runs in `memory.json`.

Everything it reads and writes is sent to the model services it uses.

## What limits it

- **Approval before the first run.** A program that can act lists what it can do and asks before its first run.
  The answer is remembered against a hash of the program, so a changed program asks again. A scheduled program won't
  start until it has been approved once, unless you set `approve = no`.
- **Asking before each action.** Agent tools that send or change something ask before each use, unless you choose a
  **(no asking)** variant. **ask me before …** blocks do the same for ordinary blocks. With nobody there to answer, the
  answer is no.
- **Some things always ask, even with the no-asking tools.**
  - **Opening and unlocking.** Anything that could unlock, open or disarm asks: every lock, cover (garage doors, gates)
    and valve action except locking, closing and stopping, including toggling and setting a position, and
    `homeassistant.turn_on`, `turn_off` or `toggle` that could reach one: named as the entity or in the data, or
    aimed at a whole area, device, floor or label, at `all`, or at nothing in particular (we can't see what those reach).
  - **Money.** Placing and cancelling a Coinbase order asks every time, live, after a preview that shows the fee and
    total, and never runs with nobody there to say yes (unless `approve_by = telegram`). Every Coinbase call other than
    reading and previewing goes through that question (`coinbase_free` in `SAFETY`), so nothing else can move money;
    converting, transferring and withdrawing aren't offered at all. Use a View-only key unless the program trades.
  - **Your network.** The MikroTik and UniFi blocks only read. The runtime sends nothing to RouterOS or a UniFi console
    but the reads in `mikrotik_free` and `unifi_free` (`SAFETY`): no change, block, restart or reboot is ever sent,
    whoever asks. A device's own certificate is used only when `MIKROTIK_CERT_SHA256` or `UNIFI_CERT_SHA256` pins it.
  - **Things that could do anything.** When an agent chooses it, running a Home Assistant script, scene or automation,
    pressing a button, starting a Homey flow, or publishing an MQTT message that says unlock, open or disarm.
- **No reading made-up addresses next to private data.** An agent that can see private things (email, messages,
  calendars, GitHub, your home, memory, files, MCP) asks before reading a page or feed whose address wasn't in its goal
  or in anything it read, since the address itself could carry your data away (`https://example.com/?d=<your emails>`).
  Addresses it found in search results, feeds or pages don't ask; only a whole address counts, not part of one. A
  search query leaves your computer too, for the search service (not the sites in its results), so an agent that
  can see private things could put some of them in a query; a search service is a place you chose to send text to.
- **Untrusted text stays text.** An agent only reads what its tools return; it's told never to follow instructions
  inside it. Treat this as a mitigation, not a guarantee: anything an agent reads (an email, a web page, a pull
  request) can try to steer it, which is why acting tools ask first. The tests play an agent that has been fully
  fooled by a hostile email, issue or page, and check that none of these limits gives way; `tools/smoke_test.py` also
  says whether a real model took the bait.
- **Web requests.** The listener only starts once `WEBHOOK_SECRET` is set, refuses requests without the secret
  (compared in constant time), and listens on `127.0.0.1` unless you set `WEBHOOK_HOST`.
- **No local network by default.** The agent's web tools read only public addresses, never ones on your own
  network (including shared addresses such as Tailscale's `100.64.0.0/10`), unless you set `local_pages = yes`. Every address a name resolves to is checked, and so is every redirect.
  Each name is looked up once and the connection goes to exactly the address that was checked, so a name can't change
  its answer in between (DNS rebinding). Through a proxy, the proxy is sent to that address too: the request names the
  address, and an https tunnel goes to it while the certificate is still checked against the name.
- **MCP servers run with your permissions.** A server named by a command in `second-thought.ini` is started as you
  and can do whatever that command can. Only add servers you trust. In an agent, a tool the server marks
  `destructiveHint` (one that can delete or overwrite) always asks first, even under (no asking). Kraken's tools are
  judged the safe way round: only the ones known not to move money run without asking, so a tool a later kraken-cli
  adds counts as money until it's checked. Trust Wallet's Agent Kit (`twak serve`) is judged the same way, and its
  automations, which trade later out of sight, are never offered to an agent.
- **approve_by = telegram asks on your phone.** A run with nobody at the keyboard refuses anything that must ask
  first, unless `approve_by = telegram` is set in `second-thought.ini`: then the question goes to your Telegram with a
  fresh four-digit code, and only a reply from your chat with that code, within five minutes, allows it. Anyone who
  can read your Telegram can allow it, so the phone that reads it should be yours.
- **Keys stay out of the program.** Keys live in `second-thought.ini` or environment variables, never in the
  exported `.py` file. `second-thought.ini` is git-ignored here; keep yours private. On Linux and Mac, `--doctor`
  says if other people on the computer can read it.
- **Private files are only yours.** On Linux and Mac, what a program keeps between runs (the journal of prompts and
  answers, memory, messages, spending, saved logs) is readable only by you.
- **Settings can't change how a program starts.** `second-thought.ini` and `ST_` variables never set `LD_*`, `DYLD_*`
  or `PYTHON*` names, which could load code into the program and everything it starts.

## On the page

The page runs inside claude.ai and uses your claude.ai account for Claude. It never asks for API keys. The
connection blocks (feeds, GitHub, email, Telegram, calendar, Home Assistant, Homey) use sample data on the page, so
nothing real is read or sent until you export a program and set it up.
