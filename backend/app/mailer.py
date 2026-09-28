"""Password-reset delivery over plain SMTP.

Configured entirely by env vars (see backend/.env.example):

    SMTP_HOST=smtp.example.com   SMTP_PORT=587   SMTP_USE_TLS=true
    SMTP_USER=you@example.com    SMTP_PASSWORD=...
    SMTP_FROM=no-reply@gramshiksha.in

Any provider works — Gmail app password, Resend SMTP, Mailgun, Hostinger,
school/college mail — because it's plain SMTP, not a vendor SDK.

No SMTP_HOST configured → send_reset_email() returns False and the caller
decides what to do (dev SQLite: log the code locally; production: fail loudly
rather than silently swallowing a reset request). The code is never written to
a log line in production and never appears in an API response.
"""
import logging
import smtplib
from email.message import EmailMessage

from .config import settings

log = logging.getLogger("gramshiksha")


def send_reset_email(to: str, code: str) -> bool:
    """Send the 6-digit code. True = handed to the SMTP server."""
    if not settings.smtp_enabled:
        return False

    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = "Your GramShiksha password reset code"
    msg.set_content(
        "Your GramShiksha password reset code is:\n\n"
        f"    {code}\n\n"
        "It expires in 15 minutes and can be used once.\n"
        "If you didn't request this, you can ignore this email — your "
        "password has not changed.\n"
    )
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
        log.info("Password reset code delivered by SMTP to %s", to)  # never the code
        return True
    except Exception as exc:  # noqa: BLE001 — delivery must not take down the API
        log.error("SMTP delivery failed for %s: %s", to, exc)
        return False
