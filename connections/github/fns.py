# GitHub: a token from https://github.com/settings/tokens (read access to your repositories is enough to look;
# to comment on pull requests it also needs pull request write access).
GITHUB_API = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
