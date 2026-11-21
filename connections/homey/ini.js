    if (need.homey) out.push("", "[homey]",
      "; Your Homey's address, and an API key: in the Homey Web App (my.homey.app), Settings, API Keys, New API Key.",
      "; Homey Pro: http://homey-XXXXXXX.local or its IP address. Homey Self-Hosted Server: the computer's IP address and :4859,",
      "; like http://192.168.1.20:4859. Devices on a Homey Bridge connected to it show up there too.",
      "; Give the key the permissions the program needs: View devices, Control devices, View and start flows, View and edit Logic.",
      "HOMEY_URL = http://homey-XXXXXXX.local", "HOMEY_API_KEY = ");
