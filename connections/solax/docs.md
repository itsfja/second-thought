## Solax

The green **Solax** block reads your Solax inverter's figures from SolaxCloud. It only reads: nothing on the inverter is ever changed, and there is nothing to install.

- **Solax figures** is a record: ac_power_w (what it's making now), yield_today_kwh and yield_total_kwh (solar generated), feedin_power_w and feedin_energy_kwh (to the grid), import_energy_kwh (from the grid), battery_soc_pct, status (as SolaxCloud names it, like Normal Mode) and upload_time.

The inverter's own local API is gone from newer firmware, so the cloud is what there is. Its figures update about every five minutes, and it allows only ten calls a minute, so each read is kept for five minutes and reused: a program that asks twice makes one call. On the page the block uses a **sample inverter**, mid-afternoon with the battery over half full. The gallery program **How did the sun do today?** reports each evening and compares with yesterday.

**Using your own inverter.** Make a free token on the API page of [SolaxCloud](https://www.solaxcloud.com), and find the Registration No. of the inverter's wifi dongle (on its label, or in the app). Then:

```ini
SOLAX_TOKEN_ID = your-token
SOLAX_SN = ABCDEFGHIJ
; Another region's cloud, like the EU one:
; SOLAX_API_URL = https://www.eu.solaxcloud.com:9443/proxy/api/getRealtimeInfo.do
```

`--doctor` checks both settings and reaches the cloud. If your inverter is already in Home Assistant, its sensors can be read today through the Home Assistant connection; Modbus control (charging from the grid, export limits) is not offered, because it costs and earns money and belongs behind the ask-first rules.
