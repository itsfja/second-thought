    if (need.unraid) out.push("", "[unraid]",
      "; Your Unraid server, through its own GraphQL API (built into Unraid 7.2 and later, the Unraid Connect plugin",
      "; before that): its address and an API key (Settings, Management Access, API Keys). The blocks read the array,",
      "; the disks, the shares, the containers and the VMs; start, stop and a parity check ask first, and nothing",
      "; else is ever sent.",
      "UNRAID_URL = ", "UNRAID_API_KEY = ", "; UNRAID_CERT_SHA256 = ");
