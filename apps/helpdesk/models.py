from django.conf import settings
from django.db import models

from apps.core.models import TimeStamp


class Ticket(TimeStamp):
	class Status(models.TextChoices):
		OPEN = "OPEN", "Open"
		IN_PROGRESS = "IN_PROGRESS", "In progress"
		RESOLVED = "RESOLVED", "Resolved"
		CLOSED = "CLOSED", "Closed"

	class Priority(models.TextChoices):
		LOW = "LOW", "Low"
		NORMAL = "NORMAL", "Normal"
		HIGH = "HIGH", "High"

	requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="support_tickets")
	subject = models.CharField(max_length=200)
	description = models.TextField()
	status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
	priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL)
	closed_at = models.DateTimeField(null=True, blank=True)

	def __str__(self):
		return self.subject


class TicketMessage(TimeStamp):
	ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="messages")
	author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ticket_messages")
	body = models.TextField()
	is_staff_response = models.BooleanField(default=False)
