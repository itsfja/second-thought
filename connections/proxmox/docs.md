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
