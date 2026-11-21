## Plex and Tautulli

The gold **Plex** blocks read your Plex media server through the X-Plex-Token API the apps use, and Tautulli adds the history and the watch-time stats. **scan a Plex library** and **stop a stream** always ask first:

- **Plex server**: one record — name, version and up (it answered, so it's up).
- **Plex libraries**: each library's name, type (movie, show or artist) and count (how many items it has).
- **Plex sessions**: each thing playing now — id (the session's id), user, title, player, state (playing or paused) and transcode (whether the server is transcoding it: a sign a client needs a better file). They only read.
- **Plex new items, last N days**: each item added in that many days, with title, library and added.
- **Tautulli history, last N days**: each thing watched in that many days, with user, title, when and whether it was transcoded. **Tautulli watch time, last N days** gives each person's hours. They only read.
- **scan the … library on Plex** asks you every time, even when nothing else does, then scans one library for new files. With nobody there to say yes (a schedule, GitHub Actions), it doesn't run; `approve_by = telegram` asks on your phone instead.
- **stop the … stream on Plex** asks every time too, then stops that session's stream (Tautulli's terminate).

Nothing else is ever sent: no media or library is ever deleted, no sharing, no user access, no transcoding or remote-access settings (`plex_free`, `plex_asks`, `tautulli_free` and `tautulli_asks` in `SAFETY`). On the page these blocks use a **sample server**. The gallery program **Media server check** reports each morning and only reads.

**Using your own Plex and Tautulli.** Set the server's address and its token, and Tautulli's address and API key:

```
[plex]
PLEX_URL = http://plex:32400
PLEX_TOKEN = your-token

[tautulli]
TAUTULLI_URL = http://tautulli:8181
TAUTULLI_API_KEY = your-key
```

The token is the one the apps send (a device's account details show it); the keychain can hold it and Tautulli's key (Settings, API Keys). `--doctor` says Plex's version and its libraries, and Tautulli's play count.
