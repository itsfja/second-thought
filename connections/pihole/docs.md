## Pi-hole

The red **Pi-hole** blocks read your Pi-hole through its v6 API, and can turn blocking off and on and change its lists, always asking first:

- **Pi-hole summary**: one record for today — queries (how many DNS queries), blocked (how many were blocked), blocked_pct (the blocked share), gravity (how many domains the lists have), clients (how many devices asked) and blocking (whether blocking is on). The run log says the queries and the blocked count.
- **top N blocked domains**: a list of records, one for each of the most-blocked domains, with domain and count. **top N clients** gives each device that asked the most, with name, ip and count. They only read.
- **disable Pi-hole blocking for N seconds** asks you every time, even when nothing else does, then turns blocking off for that long — Pi-hole turns it back on itself when the timer runs out. **enable Pi-hole blocking** turns it back on sooner. With nobody there to say yes (a schedule, GitHub Actions), they don't run; `approve_by = telegram` asks on your phone instead.
- **add / remove on Pi-hole's allow list** and **… deny list** ask every time too, then put the domain on the list or take it off. A domain added by a program carries the comment `added by Second Thought`.

Nothing else is ever sent: no settings, no DHCP, no restart, nothing that touches the firewall beyond the four asks (`pihole_free` and `pihole_asks` in `SAFETY`). On the page these blocks use a **sample Pi-hole**. The gallery program **DNS check** reports each morning and only reads.

**Using your own Pi-hole.** Set its address and its web interface's password:

```
[pihole]
PIHOLE_URL = http://pi.hole
PIHOLE_PASSWORD = your-password
```

The password is the one you set in Pi-hole's settings (Settings, API/Web interface); the keychain can hold it. `--doctor` says today's queries and how many were blocked.
