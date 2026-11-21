          case "rb_discord_send": case "rb_slack_send": E("await R.chat_send(" + pyStr(b.type === "rb_discord_send" ? "discord" : "slack") + ", " + I("TEXT", '""') + ")"); break;
