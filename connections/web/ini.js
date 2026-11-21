    if (need.feeds || need.pages) out.push("", "[feeds and pages]",
      ...(need.feeds ? ["; Your news feeds (RSS or Atom addresses), separated by spaces. 'News from feed' with nothing in it, and the agent, read these.",
                        "feeds = "] : []),
      ...note("local_pages", "yes", "let the agent read pages and feeds on your own network too (normally only public ones)"));

    if (need.webhook) out.push("", "[web requests]",
      "; A long password that every web request must carry: http://127.0.0.1:8765/<address>?key=<this password>",
      "; or in an X-Second-Thought-Key header. Requests without it are refused.",
      "; Only this computer can call it, which is enough for Home Assistant on the same machine. For Home Assistant",
      "; on another machine, IFTTT or your phone, uncomment WEBHOOK_HOST = 0.0.0.0 and call http://<this computer>:8765/...",
      "WEBHOOK_SECRET = ", "; WEBHOOK_PORT = 8765", "; WEBHOOK_HOST = 0.0.0.0");
