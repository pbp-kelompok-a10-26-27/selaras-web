from django.conf import settings
from django.db import models
from django.utils.text import slugify

from apps.core.models import TimeStamp


class Campaign(TimeStamp):
	class Status(models.TextChoices):
		DRAFT = "DRAFT", "Draft"
		PUBLISHED = "PUBLISHED", "Published"
		CLOSED = "CLOSED", "Closed"

	title = models.CharField(max_length=200)
	slug = models.SlugField(max_length=220, unique=True, blank=True)
	description = models.TextField()
	target_amount = models.DecimalField(max_digits=12, decimal_places=2)
	status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
	starts_at = models.DateTimeField(null=True, blank=True)
	ends_at = models.DateTimeField(null=True, blank=True)

	def save(self, *args, **kwargs):
		if not self.slug:
			self.slug = slugify(self.title)
		super().save(*args, **kwargs)

	def __str__(self):
		return self.title


class Donation(TimeStamp):
	class Status(models.TextChoices):
		PENDING = "PENDING", "Pending"
		APPROVED = "APPROVED", "Approved"
		REJECTED = "REJECTED", "Rejected"

	campaign = models.ForeignKey(Campaign, on_delete=models.PROTECT, related_name="donations")
	donor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="donations")
	amount = models.DecimalField(max_digits=12, decimal_places=2)
	proof = models.FileField(upload_to="donations/", blank=True)
	status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
	verified_at = models.DateTimeField(null=True, blank=True)
