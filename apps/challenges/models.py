from django.conf import settings
from django.db import models
from django.db.models import UniqueConstraint
from django.utils.text import slugify

from apps.core.models import TimeStamp


class Challenge(TimeStamp):
	title = models.CharField(max_length=200)
	slug = models.SlugField(max_length=220, unique=True, blank=True)
	description = models.TextField()
	start_date = models.DateField()
	end_date = models.DateField()
	is_published = models.BooleanField(default=False)

	def save(self, *args, **kwargs):
		if not self.slug:
			self.slug = slugify(self.title)
		super().save(*args, **kwargs)

	def __str__(self):
		return self.title


class ChallengeParticipation(TimeStamp):
	challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name="participations")
	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="challenge_participations")
	completed_at = models.DateTimeField(null=True, blank=True)

	class Meta:
		constraints = [UniqueConstraint(fields=("challenge", "user"), name="unique_challenge_participant")]


class ChallengeProgress(TimeStamp):
	participation = models.ForeignKey(ChallengeParticipation, on_delete=models.CASCADE, related_name="progress_records")
	progress_date = models.DateField()
	notes = models.TextField(blank=True)
	is_completed = models.BooleanField(default=False)

	class Meta:
		constraints = [UniqueConstraint(fields=("participation", "progress_date"), name="unique_daily_challenge_progress")]


class Badge(TimeStamp):
	name = models.CharField(max_length=100, unique=True)
	description = models.TextField(blank=True)

	def __str__(self):
		return self.name


class UserBadge(TimeStamp):
	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="badges")
	badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name="awarded_to")
	awarded_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		constraints = [UniqueConstraint(fields=("user", "badge"), name="unique_user_badge")]
