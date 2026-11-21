## Radarr and Sonarr

The green **Radarr and Sonarr** blocks read your movie and TV managers through their API, and can start a search for what's missing, always asking first:

- **Radarr/Sonarr queue**: each job in the queue, with title, status (Downloading, Queued, Paused, Grabbed, Importing), size_mb, left_mb, quality and eta. The run log says how many are downloading.
- **Radarr/Sonarr wanted list**: each movie or episode on the wanted list (missing, not yet grabbed), with title, added (the date it was added) and id.
- **Radarr/Sonarr diskspace**: each folder Radarr or Sonarr manages, with path, label, free_gb and total_gb.
- **search Radarr/Sonarr for what's missing** asks you every time, even when nothing else does. With nobody there to say yes (a schedule, GitHub Actions), it doesn't run; `approve_by = telegram` asks on your phone instead.

Nothing else is ever sent: no movies or series added, renamed or deleted, no queue emptied, no manual import, no restart (`arr_free` and `arr_asks` in `SAFETY`). On the page these blocks use a **sample queue**: a movie importing, one downloading, and the wanted list and disk space to match. The gallery program **Wanted list check** reports each morning and only reads.

**Using your own Radarr and Sonarr.** Set each one's address and API key (Settings, General, API Key):

```
[radarr]
RADARR_URL = http://radarr:7878
RADARR_API_KEY = your-key

[sonarr]
SONARR_URL = http://sonarr:8989
SONARR_API_KEY = your-key
```

Either one works on its own; the blocks you use decide which is called. If Radarr or Sonarr is behind HTTPS with a certificate this computer doesn't trust, `RADARR_CERT_SHA256` or `SONARR_CERT_SHA256` pins it, as for MikroTik and UniFi (`--doctor` shows the fingerprint). `--doctor` says each one's version and how many jobs are in the queue.
