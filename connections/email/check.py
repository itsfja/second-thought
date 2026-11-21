        if has("email_read"):
            async def mail_in():
                await self.email_search("", 2)
                return tr("read the inbox")
            out.append(("Email (reading)", mail_in))
        if has("email_send"):
            async def mail_out():
                import smtplib
                c = self._mail()

                def go():
                    s_ = smtplib.SMTP_SSL(c["smtp"], 465, timeout=30) if c["ssl"] and c["smtp_port"] == 465 else smtplib.SMTP(c["smtp"], c["smtp_port"], timeout=30)
                    with s_:
                        if c["ssl"] and c["smtp_port"] != 465:
                            s_.starttls()
                        s_.login(c["addr"], c["pw"])
                try:
                    await asyncio.to_thread(go)
                except smtplib.SMTPAuthenticationError:
                    raise RunError(tr("the email server refused EMAIL_ADDRESS and EMAIL_PASSWORD {where_keys}. Use an app password.", where_keys=WHERE_KEYS)) from None
                except (smtplib.SMTPException, OSError) as e:
                    raise RunError(tr("couldn't sign in to {smtp} to send ({e})", smtp=c['smtp'], e=_short(e, 120))) from None
                return tr("signed in to {smtp} (nothing was sent)", smtp=c['smtp'])
            out.append(("Email (sending)", mail_out))
