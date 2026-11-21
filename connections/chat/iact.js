      case "rb_discord_send": case "rb_slack_send": await chatSend(b.type === "rb_discord_send" ? "discord" : "slack", await input(b, tc, "TEXT"), false); break;
