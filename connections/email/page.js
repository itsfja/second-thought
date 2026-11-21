  const MAIL = () => { connNote("Email"); return CONN.email || { messages:[] }; };
  const mailHead = m => "id " + m.id + " · " + whenText(hoursAgo(m.hours_ago)) + " · From: " + m.from + " · Subject: " + m.subject;
  function emailSearch(query, days){
    query = str(query).trim(); days = Math.max(1, Math.min(365, Math.floor(num(days) + 0.5) || 7));
    const words = query.toLowerCase().split(/\s+/).filter(Boolean);
    const found = MAIL().messages.filter(m => m.hours_ago <= days * 24 && words.every(w => (m.from + " " + m.subject + " " + m.body).toLowerCase().includes(w)));
    return found.map(m => mailHead(m) + "\n  " + short(m.body, 200)).join("\n") || "No emails in the last " + days + " days" + (query ? " with “" + query + "”." : ".");
  }
  function emailRead(id){
    id = str(id).trim().replace(/^id\s*/, "");
    if (!/^\d+$/.test(id)) fail(tr("read_email needs an email's id number, from search_email."));
    const m = MAIL().messages.find(x => x.id === id);
    if (!m) fail(tr("There's no email with id {id}.", { id }));
    return mailHead(m) + "\nTo: " + (CONN.email.address || "you") + "\n\n" + m.body;
  }
  async function emailSend(to, subject, body, approved){
    to = str(to).trim(); subject = str(subject).trim();
    const addrs = to.split(/[,;]/).map(a => a.trim()).filter(Boolean);
    if (!addrs.length || !addrs.every(a => /^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$/.test(a))) fail(tr("“{to}” isn't an email address.", { to }));
    if (!approved && !(await allowed(["messages"], "send an email to " + to + ": " + subject))) return false;
    MAIL(); addStep(tr("Email to {to}", { to }), { text:tr("Subject: {subject}", { subject:subject || tr("(no subject)") }) + "\n\n" + str(body) }).done("sample", "ok");
    return true;
  }
