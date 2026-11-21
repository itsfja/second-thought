## Email

The **Email** blocks read your inbox and send mail from your address, asking first:

- **when an email arrives containing …**, checked every 2 minutes, runs a script when a new email arrives in your inbox whose sender, subject or words contain this. **what arrived** gives from, subject, body and text.
- **search my email** (an agent tool) gives the emails of the last days, or those containing words; **read email …** gives one whole email by its id number.
- **send email to … subject …** sends one. With **ask me before sending messages and announcements**, it asks you first.

On the page these blocks use **sample emails**, and nothing is sent: try **When the flour shop emails** or **Email me a news digest**. The listener starts from what's new after the program starts; emails that arrived while it was off don't start the script.

**Settings:** `[email]` in `second-thought.ini` — `EMAIL_ADDRESS` and an **app password**, not your normal password (in Gmail, it's in your Google account under Security). Gmail, iCloud, Yahoo, Fastmail and mailbox.org find their own mail servers. For anything else, fill in `EMAIL_IMAP_HOST` and `EMAIL_SMTP_HOST` (and the ports, or `EMAIL_SSL = no` for a plain connection). `--doctor` signs in to read and to send, and says so.
