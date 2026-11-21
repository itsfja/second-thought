# GitHub: a token from https://github.com/settings/tokens (read access to your repositories is enough to look;
# to comment on pull requests it also needs pull request write access).
GITHUB_API = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
# The last text of each page a 'when the web page … changes' block watches, so a restart doesn't count every page as changed.
PAGES_FILE = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "watched-pages.json")
