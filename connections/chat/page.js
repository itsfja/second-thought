  /* Discord and Slack on the page: sample channels. Matches the runtime's chat_search and chat_send wording. */
  const CHAT_NAME = { discord:"Discord", slack:"Slack" };
  const CHAT = svc => { connNote(CHAT_NAME[svc]); return (CONN.chat || {})[svc] || { messages:[], channel:"" }; };
  function chatSearch(svc, text){
    const words = str(text).toLowerCase().split(/\s+/).filter(Boolean), c = CHAT(svc);
    const found = c.messages.slice().sort((a, b) => a.hours_ago - b.hours_ago).filter(m => words.every(w => m.text.toLowerCase().includes(w))).slice(0, 20);
    return found.map(m => whenText(hoursAgo(m.hours_ago)) + " · " + m.from + " in " + c.channel + ": " + short(m.text, 300)).join("\n") ||
      ("No " + CHAT_NAME[svc] + " messages found" + (words.length ? " with “" + str(text).trim() + "”" : "") + ". Only the channels in " + svc.toUpperCase() + "_CHANNEL_ID are read.");
  }
  async function chatSend(svc, text, approved){
    text = str(text).trim(); if (!text) fail(tr("A {service} message needs some text.", { service:CHAT_NAME[svc] }));
    if (!approved && !(await allowed(["messages"], "send a " + CHAT_NAME[svc] + " message: " + short(text, 120)))) return false;
    const c = CHAT(svc); addStep(CHAT_NAME[svc] + " → " + (c.channel || tr("your channel")), { text }).done("sample", "ok");
    return true;
  }
