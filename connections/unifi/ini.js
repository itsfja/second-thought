    if (need.unifi) out.push("", "[unifi]",
      "; Your UniFi console (a Cloud Gateway or Dream Machine), read through its Network API. Make a key in the Network app:",
      "; Settings, Control Plane, Integrations. Run --doctor once: it shows the console's certificate fingerprint to pin.",
      "UNIFI_URL = https://192.168.1.1", "UNIFI_API_KEY = ", "UNIFI_CERT_SHA256 = ");
