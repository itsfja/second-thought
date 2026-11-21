  const TG = () => { connNote("Telegram"); return CONN.telegram || { messages:[], chat:"" }; };
  function tgSearch(text){
    const words = str(text).toLowerCase().split(/\s+/).filter(Boolean), t = TG();
    const found = t.messages.slice().sort((a, b) => a.hours_ago - b.hours_ago).filter(m => words.every(w => m.text.toLowerCase().includes(w))).slice(0, 20);
    return found.map(m => whenText(hoursAgo(m.hours_ago)) + " · " + m.from + ": " + short(m.text, 300)).join("\n") ||
      ("No messages found" + (words.length ? " with “" + str(text).trim() + "”" : "") + ". The bot only sees messages sent to it, from the chats in TELEGRAM_CHAT_ID.");
  }
  async function tgSend(text, approved){
    text = str(text).trim(); if (!text) fail(tr("A Telegram message needs some text."));
    if (!approved && !(await allowed(["messages"], "send a Telegram message: " + short(text, 120)))) return false;
    const t = TG(); addStep("Telegram → " + (t.chat || tr("your chat")), { text }).done("sample", "ok");
    return true;
  }
