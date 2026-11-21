    if (need.discord) out.push("", "[discord]",
      "; A bot: Discord Developer Portal (discord.com/developers), New Application, Bot, Reset Token. Turn on 'Message Content Intent'",
      "; on the same page, then invite the bot to your server (OAuth2, URL Generator, bot; Read and Send Messages).",
      "; The channels it reads and posts in: right-click a channel, Copy Channel ID (turn on Developer Mode first).",
      "; Anyone in a server can post, so only these channels count. Several can be separated by spaces.",
      "DISCORD_BOT_TOKEN = ", "DISCORD_CHANNEL_ID = ");
    if (need.slack) out.push("", "[slack]",
      "; A Slack app (api.slack.com/apps): OAuth & Permissions, bot scopes channels:history, groups:history and chat:write,",
      "; then install it and copy the Bot User OAuth Token (xoxb-…). Invite the bot to each channel with /invite.",
      "; The channels it reads and posts in: open the channel's details; the ID is at the bottom. Several can be separated by spaces.",
      "SLACK_BOT_TOKEN = ", "SLACK_CHANNEL_ID = ");
