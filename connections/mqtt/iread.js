      case "rb_mqtt_read": {
        const topic = mqttTopic(await input(b, tc, "TOPIC")), got = mqttRead(topic);
        if (!/[+#]/.test(topic)) { const v = got[topic] || ""; addStep("MQTT " + topic, { mono:true, text:v || tr("(no message yet: only messages the broker keeps show up straight away)") }).done("read", "ok"); return v; }
        addStep("MQTT " + topic, { mono:true, text:Object.keys(got).sort().map(k => k + ": " + short(got[k], 80)).join("\n") || tr("(nothing)") }).done(tr("{n} topics", { n:Object.keys(got).length }), "ok");
        return got;
      }
