    if (need.mikrotik) out.push("", "[mikrotik]",
      "; Your MikroTik router or switch, read through RouterOS 7's REST API (turn on the www-ssl service). Make a group with",
      "; only the read, api and rest-api policies, and a user in it for this program. Run --doctor once: it shows the",
      "; router's certificate fingerprint to pin.",
      "MIKROTIK_URL = https://192.168.88.1", "MIKROTIK_USER = ", "MIKROTIK_PASSWORD = ", "MIKROTIK_CERT_SHA256 = ");
