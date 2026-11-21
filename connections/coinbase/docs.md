## Coinbase

The blue **Coinbase** blocks read your Coinbase account through its Advanced Trade API, and can place orders, always asking first:

- **Coinbase balances** lists each asset in your portfolio, biggest first: asset, amount, value and currency. Values are in your currency (`currency` in `second-thought.ini`).
- **Coinbase portfolio value** is what the whole portfolio is worth.
- **price of … on Coinbase** gives a trading pair's latest price, like BTC-GBP's in pounds; choose **24-hour change %** for how much it moved.
- **Coinbase daily prices of … for the last …** gives a record for each day (or hour): time, open, high, low, close and volume, oldest first.
- **Coinbase open orders** and **recent fills** list your orders and trades.
- **preview Coinbase order: buy … of …** says what a market order would come to, without placing it: size, spend, fee, total, slippage and warnings. **Buy** spends an amount of the second currency (50 of BTC-GBP spends £50); **sell** sells an amount of the first (0.01 of BTC-GBP sells 0.01 BTC).
- **place Coinbase order** and **cancel Coinbase order** move real money. They always ask you first, even when nothing else does, and the question shows the preview's fee and total. With nobody there to say yes (a schedule, GitHub Actions, a program serving as an MCP tool), they don't run; `approve_by = telegram` asks on your phone instead.

Only spot trading pairs are offered, and nothing converts, transfers or withdraws. On the page these blocks use a **sample portfolio**, in pounds, and nothing is bought or sold. Two gallery programs use them: **Weekly crypto round-up** and **Tell me if BTC drops 10%**. Both only read.

**Using your real account.** At [portal.cdp.coinbase.com](https://portal.cdp.coinbase.com), open API Keys and create one. Under its advanced settings choose **ECDSA** (Advanced Trade doesn't take Ed25519 keys), limit it to **one portfolio**, and give it **View** permission only, unless the program places orders (then View and Trade). Never give it Transfer. Save the key file it downloads next to the program, and name it in `second-thought.ini`:

```
[coinbase]
COINBASE_KEY_FILE = cdp_api_key.json
```

Or put the file's contents in `COINBASE_KEY` (in the keychain, say). Each request is signed with the key, which needs `pip install cryptography`; `run.bat` and `run.sh` install it. `--doctor` checks the key, and says if it can trade when the program only reads, or can't when it places orders.
