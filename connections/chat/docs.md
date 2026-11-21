## Discord and Slack

The **Discord and Slack** blocks read your channels and post in them, asking first. They share one shape: only the channels in `DISCORD_CHANNEL_ID` or `SLACK_CHANNEL_ID` count, because anyone in a server or workspace can post; the bot's own messages never count.

- **when a Discord message arrives** and **when a Slack message arrives**, checked every 10 seconds, run a script when someone posts in one of your channels (type 'anything', or words the message must contain). **what arrived** gives text, sender and channel. Discord needs the bot's *Message Content Intent* turned on.
- **send Discord message** and **send Slack message** post back in the channel a message came from, or in your first channel. With **ask me before sending messages and announcements**, they ask you first.
- The agent's **search Discord / search Slack** and **send Discord / send Slack** tools do the same from an agent; sending always asks first.

On the page these blocks use **sample channels**, and nothing is posted: try the **Discord questions?** listener example. The listeners start from what's new after the program starts.

**Settings:** `[discord]` and `[slack]` in `second-thought.ini` — a bot token for each (Discord Developer Portal, your application, Bot, Reset Token, with the Message Content intent on and the bot invited to the server; api.slack.com/apps, OAuth & Permissions, scopes channels:history, groups:history, chat:write, bot invited to each channel), and the channel ids. `--doctor` reads your channels when the program can.
