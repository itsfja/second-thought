## SABnzbd

The amber **SABnzbd** blocks read your download queue through SABnzbd's API, and can pause and resume it, always asking first:

- **SABnzbd queue**: each job in the queue, with name, size_mb, left_mb, percent, eta (time left, like 0:12:34) and status (Downloading, Queued, Paused). The run log says whether the whole queue is paused and how much is left.
- **SABnzbd history, last … hours**: each job that finished in that time, with name, status (Completed or Failed), size_mb, when it finished and, for a failure, why it failed.
- **SABnzbd diskspace**: each of SABnzbd's folders (the download folder first), with folder and free_gb.
- **pause / resume SABnzbd** asks you every time, even when nothing else does, with how much is left and how many jobs are queued. With nobody there to say yes (a schedule, GitHub Actions), it doesn't run; `approve_by = telegram` asks on your phone instead.

Nothing else is ever sent: no jobs added, deleted or retried, no speed limit, and nothing in the config, the servers or the categories. On the page these blocks use a **sample queue**: two jobs downloading, one that finished overnight and one that failed on missing articles. The gallery program **Queue watch** reports each morning and only reads.

**Using your own SABnzbd.** Set its address and the full API key (Config, General, API Key — not the NZB key, which only adds jobs):

```
[sabnzbd]
SABNZBD_URL = http://sabnzbd:8080
SABNZBD_API_KEY = your-full-key
```

If SABnzbd is behind HTTPS with a certificate this computer doesn't trust, `SABNZBD_CERT_SHA256` pins it, as for MikroTik and UniFi (`--doctor` shows the fingerprint). `--doctor` says SABnzbd's version and how many jobs are in the queue.
