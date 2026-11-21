_MD_LINK = re.compile(r"\[([^\]\n]+)\]\((https?://[^\s)]+)\)")

# Telegram: make a bot by talking to @BotFather in Telegram; it gives you the token. TELEGRAM_CHAT_ID is your own chat
# with the bot: the bot only listens to, and searches, the chats listed there (anyone can message a bot).
TELEGRAM_API = os.environ.get("TELEGRAM_API_URL", "https://api.telegram.org").rstrip("/")
TELEGRAM_FILE = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "telegram-messages.json")

def markdown_to_telegram(text):
    """Telegram's HTML formatting for a model's Markdown. Everything else is escaped, so nothing in it reads as a tag."""
    t = to_str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = _MD_LINK.sub(lambda m: f'<a href="{m.group(2).replace(chr(34), "&quot;")}">{m.group(1)}</a>', t)
    t = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", t)
    t = re.sub(r"^#{1,6}[ \t]+(.+?)[ \t]*#*$", r"<b>\1</b>", t, flags=re.M)
    t = re.sub(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"__(?=\S)(.+?)(?<=\S)__", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![\w*])", r"<i>\1</i>", t)
    return t
