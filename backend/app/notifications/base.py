from typing import Protocol


class NotificationChannel(Protocol):
    """A pluggable send target for reminders (docs plan §10.4). Email is the
    guaranteed-free default (see EmailChannel); a paid SMS/WhatsApp provider
    can be dropped in later as another class with this same signature, without
    touching the reminder-scheduling logic in app/tasks/reminders.py.

    Sync by design: Celery's default execution model is synchronous, and the
    only channel implemented so far (SMTP) is a blocking call anyway.
    """

    def send(self, *, to: str, subject: str, body: str) -> None: ...
