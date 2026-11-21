## Web

Web requests, web search and watching a web page:

- **when a web request arrives at /…**, for Home Assistant automations, IFTTT, or a shortcut on your phone. Every request must carry your `WEBHOOK_SECRET`, or it's refused. Until you set one, the program doesn't listen for web requests at all. By default only the same computer can reach it; `WEBHOOK_HOST = 0.0.0.0` lets other devices in. **What arrived** gives the text sent, and the fields of JSON or of the address.
- **when the web page … changes**, for a price, a stock notice, opening times or the council's bin page. Fill in **only the part containing …** (like `Price`) to watch just the lines with those words and the two lines after each. It checks every 60 minutes unless you say otherwise. The first check only remembers the page. What changed is in `changed`, with `before` and `after`. The last copy of each page is kept in `watched-pages.json`, next to the program, so a restart doesn't count every page as changed. Pages that need a browser to show their words can't be watched.
- **search the web for …** (under Agents) answers from the model's own knowledge, saying plainly when something may be out of date; exported Python can search live.

On the page the page-watch and web-request listeners use **sample data**. The listener starts from what's new after the program starts.

**Settings:** `[web requests]` in `second-thought.ini` — `WEBHOOK_SECRET`, a long password, and `WEBHOOK_PORT` if 8765 is taken. Call `http://127.0.0.1:8765/<address>?key=<your secret>` from the same computer, or put the secret in an `X-Second-Thought-Key` header. `feeds = ` (in `[feeds and pages]`) lists your news feeds. `--doctor` checks the port is free when the program can take web requests.
