    if (need.solax) out.push("", "[solax]",
      "; Your Solax inverter, read from SolaxCloud (the inverter's own local API is gone from newer firmware).",
      "; Make a free token on the API page of SolaxCloud, and find the Registration No. on the dongle's label or in the",
      "; app. The cloud updates about every five minutes, and each read is kept that long, so a run costs few calls.",
      "; SOLAX_API_URL points at another region's cloud, like the EU one.",
      "SOLAX_TOKEN_ID = ", "SOLAX_SN = ",
      ...note("SOLAX_API_URL", "https://www.eu.solaxcloud.com:9443/proxy/api/getRealtimeInfo.do", "to read from another region's SolaxCloud"));
