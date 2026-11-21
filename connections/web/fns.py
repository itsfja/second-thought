# The last text of each page a 'when the web page … changes' block watches, so a restart doesn't count every page as changed.
PAGES_FILE = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "watched-pages.json")

# Web requests: WEBHOOK_SECRET is a password every request must carry (?key=... or an X-Second-Thought-Key header);
