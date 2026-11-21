  /* MQTT on the page: sample topics. */
  const MQTT = () => { connNote("MQTT"); return CONN.mqtt || { topics:{} }; };
  function mqttTopic(topic, publishing){
    topic = str(topic).trim();
    if (!topic) fail(tr("MQTT needs a topic, like home/kitchen/temperature."));
    if (publishing && /[+#]/.test(topic)) fail(tr("You can't publish to a topic with + or # in it: those only work for listening."));
    return topic;
  }
  function mqttMatches(sub, topic){
    const a = sub.split("/"), b = topic.split("/");
    for (let i = 0; i < a.length; i++) { if (a[i] === "#") return true; if (i >= b.length || (a[i] !== "+" && a[i] !== b[i])) return false; }
    return a.length === b.length;
  }
  function mqttRead(topic){ topic = mqttTopic(topic); const got = {}; Object.entries(MQTT().topics || {}).forEach(([t, v]) => { if (mqttMatches(topic, t)) got[t] = v; }); return got; }
  async function mqttPublish(topic, text, retain, approved){
    topic = mqttTopic(topic, true); text = str(text);
    if (!approved && !(await allowed(["ha", "messages"], "publish to MQTT " + topic + ": " + short(text, 120)))) return false;
    MQTT(); addStep("MQTT → " + topic, { text:text + (retain ? "  " + tr("(kept by the broker)") : "") }).done("sample", "ok");
    return true;
  }
  function mqttRecord(topic, text){
    const rec = { topic, text };
    try { const j = JSON.parse(text); if (j && typeof j === "object" && !Array.isArray(j)) Object.entries(j).forEach(([k, v]) => { if (!(k in rec)) rec[k] = v && typeof v === "object" ? JSON.stringify(v) : v; }); } catch(e) {}
    return rec;
  }
