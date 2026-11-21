    if (need.proxmox) out.push("", "[proxmox]",
      "; Your Proxmox VE cluster, through its REST API. Make an API token (Datacenter, Permissions, API Tokens) for a user",
      "; with the PVEAuditor role, or one that may also start and stop guests (VM.PowerMgmt) if the program does. Run",
      "; --doctor once: it shows the node's certificate fingerprint to pin. PROXMOX_PROTECT lists VMIDs never started,",
      "; stopped or rebooted, like your Home Assistant or domain controller.",
      "PROXMOX_URL = https://pve.local:8006", "PROXMOX_TOKEN_ID = ", "PROXMOX_TOKEN_SECRET = ", "PROXMOX_CERT_SHA256 = ", "PROXMOX_PROTECT = ");
