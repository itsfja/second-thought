## NZBGeek

The purple **NZBGeek** blocks search the Usenet indexer through its Newznab API, and can fetch one NZB file, always asking first:

- **search NZBGeek for**: each release the indexer has for those words, with title, id, size_mb, grabs, posted (when it was posted) and group. The run log says how many were found. It only reads: nothing is ever downloaded.
- **fetch the NZB for** asks you every time, even when nothing else does, then saves the one file as `<id>.nzb`. With nobody there to say yes (a schedule, GitHub Actions), it doesn't run; `approve_by = telegram` asks on your phone instead. It never hands anything to a downloader: the file is saved, that's all.

Nothing else is ever sent: no account changes, no VIP time, nothing that touches payment (`nzbgeek_free` and `nzbgeek_asks` in `SAFETY`). On the page these blocks use a **sample search**: two releases of the same film. The gallery program **Missing, searched** pairs the search with the Radarr wanted list and only reads.

**Using your own NZBGeek.** Set its API key (My Account, API key):

```
[nzbgeek]
NZBGEEK_API_KEY = your-key
```

The API address is `https://api.nzbgeek.info`; `NZBGEEK_URL` overrides it if that ever moves. `--doctor` says NZBGeek's version and its days of retention.
