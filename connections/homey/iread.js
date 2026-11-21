      case "rb_homey_value": return homeyValue(await input(b, tc, "CAPABILITY"), await input(b, tc, "DEVICE"));
      case "rb_homey_find": {
        const t = str(await input(b, tc, "TEXT", "*")) || "*", recs = homeyFind(t);
        addStep("Homey: " + short(t, 50), { mono:true, text:homeyMatch(t).map(homeyLine).join("\n") || tr("(nothing)") }).done(tr("{n} devices", { n:recs.length }), "ok");
        return recs;
      }
      case "rb_homey_variable": return homeyVar(await input(b, tc, "NAME")).value;
