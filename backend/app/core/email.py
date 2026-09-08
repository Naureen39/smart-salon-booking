import smtplib
from email.message import EmailMessage

import structlog

from app.core.config import get_settings

settings = get_settings()
logger = structlog.get_logger(__name__)


def send_email(to_address: str, subject: str, body: str) -> None:
    """Sends via SMTP when configured; otherwise logs the message (dev/test mode)
    so verification/reminder flows are exercisable without real SMTP credentials.
    """
    if not settings.smtp_host:
        logger.info("email.dev_mode", to=to_address, subject=subject, body=body)
        return

    message = EmailMessage()
    message["From"] = settings.smtp_from_email
    message["To"] = to_address
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(message)
