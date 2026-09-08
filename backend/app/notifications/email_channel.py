from app.core.email import send_email


class EmailChannel:
    """SMTP-backed NotificationChannel — see app.notifications.base for why
    this interface exists."""

    def send(self, *, to: str, subject: str, body: str) -> None:
        send_email(to, subject, body)
