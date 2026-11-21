# Discord: a bot token (Discord Developer Portal, your application, Bot, Reset Token) with the Message Content intent
# turned on, and DISCORD_CHANNEL_ID: the channels it reads and posts in (anyone in a server can post, so only these count).
# Slack: a bot token (api.slack.com/apps, your app, OAuth & Permissions; scopes channels:history, groups:history,
# chat:write) and SLACK_CHANNEL_ID, the channels it reads and posts in. Invite the bot to each channel.
DISCORD_API = os.environ.get("DISCORD_API_URL", "https://discord.com/api/v10").rstrip("/")
SLACK_API = os.environ.get("SLACK_API_URL", "https://slack.com/api").rstrip("/")

def markdown_to_slack(text):
    """Slack's own formatting (*bold*, _italics_, <url|text>) for a model's Markdown."""
    t = to_str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")  # Slack reads these as its own
    t = _MD_LINK.sub(lambda m: f"<{m.group(2)}|{m.group(1)}>", t)
    t = re.sub(r"(?<![\w*])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![\w*])", r"_\1_", t)
    t = re.sub(r"^#{1,6}[ \t]+(.+?)[ \t]*#*$", r"*\1*", t, flags=re.M)
    t = re.sub(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", r"*\1*", t)
    return t
