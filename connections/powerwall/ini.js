    if (need.powerwall) out.push("", "[powerwall]",
      "; Your Tesla Powerwall (a Powerwall, Powerwall 2 or Powerwall+), read through the gateway's local API. The",
      "; Powerwall 3 has no local web API: use Home Assistant or Teslemetry for one of those.",
      "; The customer password is the last five characters of the one on the gateway's QR sticker, unless you",
      "; changed it. Run --doctor once: it shows the gateway's certificate fingerprint for POWERWALL_CERT_SHA256.",
      "; Setting the backup reserve always asks, and never runs unattended.",
      "POWERWALL_URL = https://192.168.1.50", "POWERWALL_PASSWORD = ",
      ...note("POWERWALL_EMAIL", "you@example.com", "the email the gateway's login form asks for (anything works)"),
      ...note("POWERWALL_CERT_SHA256", "aa:bb:...", "to pin the gateway's own certificate"));
