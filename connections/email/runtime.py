    # Email
    MAIL_SERVERS = {"gmail.com": ("imap.gmail.com", "smtp.gmail.com", 465), "googlemail.com": ("imap.gmail.com", "smtp.gmail.com", 465),
                    "icloud.com": ("imap.mail.me.com", "smtp.mail.me.com", 587), "me.com": ("imap.mail.me.com", "smtp.mail.me.com", 587),
                    "yahoo.com": ("imap.mail.yahoo.com", "smtp.mail.yahoo.com", 465), "yahoo.co.uk": ("imap.mail.yahoo.com", "smtp.mail.yahoo.com", 465),
                    "fastmail.com": ("imap.fastmail.com", "smtp.fastmail.com", 465),
                    "mailbox.org": ("imap.mailbox.org", "smtp.mailbox.org", 465)}

    def _mail(self):
        addr, pw = os.environ.get("EMAIL_ADDRESS", "").strip(), os.environ.get("EMAIL_PASSWORD", "")
        if not addr or not pw:
            raise RunError(tr("Email needs EMAIL_ADDRESS and EMAIL_PASSWORD {where_keys}. Use an app password, not your normal one.", where_keys=WHERE_KEYS))
        guess = self.MAIL_SERVERS.get(addr.rsplit("@", 1)[-1].lower(), (None, None, 465))
        imap = os.environ.get("EMAIL_IMAP_HOST") or guess[0]
        smtp = os.environ.get("EMAIL_SMTP_HOST") or guess[1]
        if not imap or not smtp:
            raise RunError(tr("Set EMAIL_IMAP_HOST and EMAIL_SMTP_HOST {where_keys}: your email provider's help pages list them.", where_keys=WHERE_KEYS))
        secure = os.environ.get("EMAIL_SSL", "yes").strip().lower() not in ("0", "no", "false", "off")
        return {"addr": addr, "pw": pw, "imap": imap, "imap_port": int(os.environ.get("EMAIL_IMAP_PORT") or (993 if secure else 143)),
                "smtp": smtp, "smtp_port": int(os.environ.get("EMAIL_SMTP_PORT") or guess[2]), "ssl": secure}

    def _imap(self, c):
        import imaplib
        try:
            m = imaplib.IMAP4_SSL(c["imap"], c["imap_port"], timeout=30) if c["ssl"] else imaplib.IMAP4(c["imap"], c["imap_port"], timeout=30)
            m.login(c["addr"], c["pw"])
        except imaplib.IMAP4.error as e:
            raise RunError(tr("The email server refused the login ({e}). Check EMAIL_PASSWORD is an app password.", e=_short(e, 120))) from None
        except OSError as e:
            raise RunError(tr("Couldn't reach the email server {imap} ({e}).", imap=c['imap'], e=e)) from None
        return m

    @staticmethod
    def _mail_text(msg, limit):
        """The readable text of an email: the plain part, or the HTML part's words."""
        plain = html = None
        for part in msg.walk():
            if part.get_content_maintype() == "multipart" or part.get_filename():
                continue
            if part.get_content_type() in ("text/plain", "text/html"):
                try:
                    body = part.get_content()
                except (LookupError, ValueError):
                    body = part.get_payload(decode=True).decode("utf-8", "replace") if part.get_payload(decode=True) else ""
                if part.get_content_type() == "text/plain" and plain is None:
                    plain = body
                elif html is None:
                    html = page_text(body, "text/html")[1]
        text = (plain if plain and plain.strip() else html) or ""
        return re.sub(r"\n{3,}", "\n\n", text).strip()[:limit]

    @staticmethod
    def _mail_head(msg, uid):
        import email.utils
        d = _parse_date(msg.get("Date", ""))
        who = email.utils.parseaddr(str(msg.get("From", "")))
        return f"id {uid} · {_when(d) if d else '?'} · From: {who[0] or who[1]}" + (f" <{who[1]}>" if who[0] else "") + f" · Subject: {msg.get('Subject', '(no subject)')}"

    async def email_search(self, query="", days=7):
        import email
        import email.policy
        c, query, days = self._mail(), to_str(query).strip(), max(1, min(365, round_js(num(days)) or 7))

        def go():
            m = self._imap(c)
            try:
                m.select("INBOX", readonly=True)
                since = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%d-%b-%Y")
                if query and not query.isascii():
                    m.literal = query.encode("utf-8")
                    typ, data = m.uid("SEARCH", "CHARSET", "UTF-8", "SINCE", since, "TEXT")
                elif query:
                    typ, data = m.uid("SEARCH", "SINCE", since, "TEXT", '"' + query.replace('"', "") + '"')
                else:
                    typ, data = m.uid("SEARCH", "SINCE", since)
                uids = (data[0] or b"").split()[-20:][::-1]
                out = []
                for uid in uids:
                    typ, got = m.uid("FETCH", uid, "(BODY.PEEK[]<0.20000>)")
                    raw = next((x[1] for x in got if isinstance(x, tuple)), b"")
                    msg = email.message_from_bytes(raw, policy=email.policy.default)
                    out.append(self._mail_head(msg, uid.decode()) + "\n  " + _short(self._mail_text(msg, 600), 200))
                return out
            finally:
                try:
                    m.logout()
                except Exception:  # noqa: BLE001
                    pass
        found = await asyncio.to_thread(go)
        return "\n".join(found) or f"No emails in the last {days} days" + (f" with “{query}”." if query else ".")

    async def email_read(self, uid):
        import email
        import email.policy
        c, uid = self._mail(), to_str(uid).strip().removeprefix("id").strip()
        if not uid.isdigit():
            raise RunError(tr("read_email needs an email's id number, from search_email."))

        def go():
            m = self._imap(c)
            try:
                m.select("INBOX", readonly=True)
                typ, got = m.uid("FETCH", uid, "(BODY.PEEK[])")
                raw = next((x[1] for x in got if isinstance(x, tuple)), None)
                if not raw:
                    raise RunError(tr("There's no email with id {uid}.", uid=uid))
                msg = email.message_from_bytes(raw, policy=email.policy.default)
                files = [p.get_filename() for p in msg.walk() if p.get_filename()]
                return (self._mail_head(msg, uid) + (f"\nTo: {msg.get('To', '')}" if msg.get("To") else "") + "\n\n" + self._mail_text(msg, 15000)
                        + (f"\n\nAttachments: {', '.join(files)}" if files else ""))
            finally:
                try:
                    m.logout()
                except Exception:  # noqa: BLE001
                    pass
        return await asyncio.to_thread(go)

    async def email_send(self, to, subject, body, approved=False):
        import smtplib
        from email.message import EmailMessage
        to, subject, body = to_str(to).strip(), to_str(subject).strip(), to_str(body)
        addrs = [a.strip() for a in re.split(r"[,;]", to) if a.strip()]
        if not addrs or not all(re.fullmatch(r"[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+", a) for a in addrs):
            raise RunError(tr("“{to}” isn't an email address.", to=to))
        c = self._mail()
        if (not approved or self.dry_run()) and not await self._allowed(["messages"], f"send an email to {to}: {subject}"):
            return False
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = c["addr"], ", ".join(addrs), subject or "(no subject)"
        msg.set_content(body)

        def go():
            try:
                if c["ssl"] and c["smtp_port"] == 465:
                    s_ = smtplib.SMTP_SSL(c["smtp"], 465, timeout=30)
                else:
                    s_ = smtplib.SMTP(c["smtp"], c["smtp_port"], timeout=30)
                    if c["ssl"]:
                        s_.starttls()
                with s_:
                    s_.login(c["addr"], c["pw"])
                    s_.send_message(msg)
            except smtplib.SMTPException as e:
                raise RunError(tr("The email couldn't be sent ({e}).", e=_short(e, 160))) from None
            except OSError as e:
                raise RunError(tr("Couldn't reach the email server {smtp} ({e}).", smtp=c['smtp'], e=e)) from None
        await asyncio.to_thread(go)
        self.log(tr("Email sent to {to}", to=to), tr("Subject: {subject}\n\n{body}", subject=subject, body=_short(body, 600)), tr("sent"))
        return True

    async def _listen_email(self, items):
        c, last = self._mail(), None
        print(tr("Checking for new email."), flush=True)
        while True:
            try:
                last, new = await asyncio.to_thread(self._mail_new, c, last)
                for rec in new:
                    hay = (rec["from"] + " " + rec["subject"] + " " + rec["body"]).lower()
                    for contains, fn in items:
                        want = to_str(contains).strip().lower()
                        if want in ("", "anything") or want in hay:
                            self._fire(fn, dict(rec), tr("New email: {subject}", subject=_short(rec["subject"], 40)))
            except RunError as e:
                print(tr("  (Email check failed: {e})", e=e), flush=True)
            await asyncio.sleep(self._poll(120))
