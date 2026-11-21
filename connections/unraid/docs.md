## Unraid

The orange **Unraid** blocks read your Unraid server through its own GraphQL API (built into Unraid 7.2 and later, the Unraid Connect plugin before that), and can start and stop one container or VM, and check the parity, always asking first:

- **Unraid array**: one record for the array: state (STARTED, STOPPED, ...), started (whether it's started), free_gb, total_gb and uptime.
- **Unraid disks**: each disk in the array, parity first then data then cache, with name, type, status (DISK_OK, DISK_NP, ...), temp_c, errors, size_gb and free_gb.
- **Unraid shares**: each user share, with name, free_gb, used_gb and total_gb.
- **Unraid containers**: each Docker container, with name, state (running, exited, ...), status and auto_start (whether Unraid starts it with the array).
- **Unraid VMs**: each virtual machine, with name and state (RUNNING, SHUTOFF, ...).
- **start / stop Unraid container / VM** and **check Unraid's parity** ask you every time, even when nothing else does. With nobody there to say yes (a schedule, GitHub Actions), it doesn't run; `approve_by = telegram` asks on your phone instead.

Nothing else is ever sent: the array is never stopped, no disk is added or removed, no container is updated or removed, no plugin is installed, nothing runs in a terminal, and the parity check writes no corrections (`unraid_free` and `unraid_asks` in `SAFETY`). On the page these blocks use a **sample server**: the array started, one parity, two data disks and a cache, plex running and pihole stopped, one VM up and one down. The gallery program **Server morning check** reports each morning and only reads.

**Using your own Unraid.** Set its address and an API key (Settings, Management Access, API Keys):

```
[unraid]
UNRAID_URL = https://unraid
UNRAID_API_KEY = your-key
```

If Unraid is behind HTTPS with a certificate this computer doesn't trust, `UNRAID_CERT_SHA256` pins it, as for MikroTik and UniFi (`--doctor` shows the fingerprint). `--doctor` says Unraid's version and the array's state.
