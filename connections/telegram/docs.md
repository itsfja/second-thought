## Telegram

The **Telegram** blocks read the messages sent to your bot and send messages back, asking first:

- **when a Telegram message arrives containing …**, for messages to your bot. Only messages from your own chats count (`TELEGRAM_CHAT_ID`); anyone can message a bot, so the bot only sees the chats you list. In exported Python it listens all the time; on the page, right-click it and choose **Run this script** to try it with a sample message.
- **Telegram message …** gives the message that started the script: its words, who sent it, or the chat. Empty outside a Telegram script.
- **search my Telegram messages** (an agent tool) gives the newest messages, or those containing words.
- **send Telegram message …** sends one: back to the chat a message came from, or to your first chat. With **ask me before sending messages and announcements**, it asks you first.

On the page these blocks use **sample messages**, and nothing is sent: try **Morning briefing on Telegram** under Automation. Telegram messages are kept for searching even while no program runs.

**Settings:** `[telegram]` in `second-thought.ini` — in Telegram, message **@BotFather** and send `/newbot`; it gives you `TELEGRAM_BOT_TOKEN`. Then message your bot and run the program: it tells you your chat number for `TELEGRAM_CHAT_ID`. Anyone can message a bot, so it only listens to, and searches, the chats you list there. A bot only sees messages sent to it, so it can't search your other chats. `--doctor` says the bot's name when the program can read or send.
