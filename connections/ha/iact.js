      case "rb_ha_call": await haCall(await input(b, tc, "SERVICE"), await input(b, tc, "ENTITY"), await input(b, tc, "DATA"), tc); break;
      case "rb_ha_notify": {
        const target = str(await input(b, tc, "TARGET")).trim() || "persistent_notification", text = str(await input(b, tc, "TEXT"));
        if (!text.trim()) fail(tr("The 'notify' block has no message."));
        if (!(await allowed(["ha", "messages"], "send a notification to " + target + ": " + short(text, 120)))) break;
        haNote(); addStep(tr("Notification → {target}", { target }), { text }).done("sample house", "ok"); break;
      }
      case "rb_ha_speak": {
        const text = str(await input(b, tc, "TEXT")), player = str(await input(b, tc, "PLAYER")).trim();
        if (!text.trim()) fail(tr("The 'say' block has nothing to say."));
        if (!(await allowed(["ha", "messages"], "say on " + (player || "a speaker") + ": " + short(text, 120)))) break;
        haNote(); addStep(tr("Spoken on {player}", { player:player || tr("a speaker") }), { text }).done("sample house", "ok"); break;
      }
