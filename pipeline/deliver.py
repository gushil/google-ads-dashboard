"""
Deliver the dashboard to the paid-media team by email (SMTP, provider-agnostic).

Sends a multipart message: the dashboard HTML as the email body *and* as a
.html attachment, since Gmail/Outlook strip some CSS but render an opened
attachment faithfully. Swap this module for SendGrid/SES/Slack as needed —
run_weekly.py only calls deliver.send(cfg, html, subject).
"""
from __future__ import annotations

import smtplib
from email.message import EmailMessage


def send(cfg, html: str, subject: str, extra_note: str = "") -> None:
    if cfg.dry_run:
        print("[deliver] DRY_RUN set - skipping email send.")
        return
    if not (cfg.smtp_host and cfg.mail_to):
        print("[deliver] SMTP_HOST or MAIL_TO not configured - skipping email send "
              "(dashboard is served from Railway regardless).")
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg.mail_from
    msg["To"] = ", ".join(cfg.mail_to)
    msg.set_content(
        "Your weekly Google Ads performance report is ready. Open it in a browser "
        "for the full layout." + extra_note
    )
    msg.add_alternative(html, subtype="html")
    msg.add_attachment(
        html.encode("utf-8"), maintype="text", subtype="html",
        filename="openclinica-paid-media-weekly.html",
    )

    with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port) as server:
        server.starttls()
        if cfg.smtp_user:
            server.login(cfg.smtp_user, cfg.smtp_password)
        server.send_message(msg)
    print(f"[deliver] Sent to {len(cfg.mail_to)} recipient(s).")
