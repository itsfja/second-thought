    if (need.coinbase) out.push("", "[coinbase]",
      "; A Coinbase API key: at portal.cdp.coinbase.com, API Keys, Create API key. Choose ECDSA under its advanced settings,",
      "; limit it to one portfolio, and give it View permission only, unless the program places orders (then View and Trade).",
      "; Never give it Transfer. Save the key file it downloads next to the program, and put its name here.",
      "; Values are in the currency set under [run]. Signing needs:  pip install cryptography",
      "COINBASE_KEY_FILE = cdp_api_key.json");
