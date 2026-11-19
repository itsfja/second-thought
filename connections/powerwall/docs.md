## Powerwall

The red **Powerwall** blocks read a Tesla Powerwall, Powerwall 2 or Powerwall+ through the gateway's local API, and one block changes the backup reserve after asking.

- **Powerwall figures** is a record: battery_soc_pct (its charge), solar_power_w (making now), battery_power_w (positive is charging), grid_power_w (positive is importing), load_power_w (the house), reserve_pct (the backup reserve it keeps), mode (self_consumption, backup, ...) and grid (connected, or islanded in a power cut).
- **set Powerwall backup reserve to N %** raises or lowers how much of the battery the house keeps for a power cut. It **always asks you first**, even with (no asking), and with nobody there to say yes it doesn't run: it changes how long the house lasts in a cut.

The **Powerwall 3 has no local web API**, so these blocks can't reach one: use Home Assistant's Tesla Fleet integration, or Teslemetry's MCP server, for a Powerwall 3. Nothing else is ever sent to a Powerwall: no firmware, no storm watch, no operation mode, no grid charging or export setting — the calls are the two lists `powerwall_free` and `powerwall_asks` in `SAFETY`. On the page the blocks use a **sample Powerwall**, evening, battery three-quarters full. The gallery program **Power cut ready?** checks each evening, and raises the reserve to 100% if a storm warning applies — asking.

**Using your own Powerwall.** The gateway's address, and the customer password (the last five characters of the one on its QR sticker, unless you changed it). Then:

```ini
POWERWALL_URL = https://192.168.1.50
POWERWALL_PASSWORD = H4rd!
; The gateway's certificate is its own: run --doctor once and it shows the fingerprint to pin.
; POWERWALL_CERT_SHA256 = aa:bb:...
```

`--doctor` checks both settings, reports the battery, the reserve and the grid, and shows the certificate fingerprint. Login happens once and the token is kept.
