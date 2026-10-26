import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStamp


class Ticket(TimeStamp):
    class Status(models.TextChoices):
        OPEN = "open", _("Open")
        IN_PROGRESS = "in_progress", _("In Progress")
        RESOLVED = "resolved", _("Resolved")
        CLOSED = "closed", _("Closed")

    class Priority(models.TextChoices):
        LOW = "low", _("Low")
        NORMAL = "normal", _("Normal")
        HIGH = "high", _("High")

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="support_tickets",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        limit_choices_to={"role": "admin"},
        null=True,
        blank=True,
        related_name="assigned_tickets",
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subject = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.OPEN
    )
    priority = models.CharField(
        max_length=20, choices=Priority.choices, default=Priority.NORMAL
    )
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Ticket #{self.id} - {self.subject} - ({self.status})"


class TicketMessage(TimeStamp):
    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="messages"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ticket_messages",
    )
    message = models.TextField()
    is_admin_response = models.BooleanField(default=False)
    # The message this one replies to (quoted above it). Kept as a plain message if
    # the original is deleted.
    reply_to = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="replies"
    )

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return (
            f"Message #{self.id} - Ticket #{self.ticket.id} - "
            f"Author: {self.author.username}"
        )
