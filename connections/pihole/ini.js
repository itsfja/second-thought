    if (need.pihole) out.push("", "[pihole]",
      "; Your Pi-hole (v6 or later), through its REST API: its address and its web interface's password. The blocks",
      "; read the stats and the top lists; blocking and the allow and deny lists ask first, and nothing else is",
      "; ever sent. Run --doctor once: it shows the certificate fingerprint for PIHOLE_CERT_SHA256, if Pi-hole is",
      "; behind HTTPS this computer doesn't trust.",
      "PIHOLE_URL = ", "PIHOLE_PASSWORD = ", "; PIHOLE_CERT_SHA256 = ");
