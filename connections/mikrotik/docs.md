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
