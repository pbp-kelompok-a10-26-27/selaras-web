from django.conf import settings
from django.db import models
from django.utils.text import slugify

from apps.core.models import TimeStamp


class ArticleCategory(TimeStamp):
	name = models.CharField(max_length=100, unique=True)
	slug = models.SlugField(max_length=120, unique=True, blank=True)

	def save(self, *args, **kwargs):
		if not self.slug:
			self.slug = slugify(self.name)
		super().save(*args, **kwargs)

	def __str__(self):
		return self.name


class Article(TimeStamp):
	class Status(models.TextChoices):
		DRAFT = "DRAFT", "Draft"
		PUBLISHED = "PUBLISHED", "Published"

	title = models.CharField(max_length=200)
	slug = models.SlugField(max_length=220, unique=True, blank=True)
	summary = models.TextField(blank=True)
	content = models.TextField()
	category = models.ForeignKey(
		ArticleCategory,
		on_delete=models.PROTECT,
		related_name="articles",
	)
	author = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.PROTECT,
		related_name="articles",
	)
	status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
	published_at = models.DateTimeField(null=True, blank=True)

	def save(self, *args, **kwargs):
		if not self.slug:
			self.slug = slugify(self.title)
		super().save(*args, **kwargs)

	def __str__(self):
		return self.title
