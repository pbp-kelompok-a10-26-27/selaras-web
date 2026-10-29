from django.conf import settings
from django.db import models
from django.db.models.functions import Lower

from apps.core.models import TimeStamp
from apps.core.utils import include_slug_in_update_fields, set_unique_slug


class ArticleCategory(TimeStamp):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)

    def save(self, *args, **kwargs):
        if set_unique_slug(self, self.name, "name", 120, "category"):
            include_slug_in_update_fields(kwargs)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Tag(TimeStamp):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("name"), name="articles_tag_name_ci_unique")
        ]

    def save(self, *args, **kwargs):
        if set_unique_slug(self, self.name, "name", 120, "tag"):
            include_slug_in_update_fields(kwargs)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Article(TimeStamp):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draf"
        # Tulisan pengguna yang menunggu ditinjau admin
        PENDING = "PENDING", "Menunggu review"
        PUBLISHED = "PUBLISHED", "Terbit"
        REJECTED = "REJECTED", "Perlu revisi"

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    summary = models.TextField(blank=True)
    content = models.TextField()
    image = models.ImageField(upload_to="articles/", blank=True)
    category = models.ForeignKey(
        ArticleCategory,
        on_delete=models.PROTECT,
        related_name="articles",
    )
    tags = models.ManyToManyField(Tag, related_name="articles", blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="articles",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    published_at = models.DateTimeField(null=True, blank=True)
    # Jejak review untuk tulisan pengguna
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_articles",
    )
    review_note = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if set_unique_slug(self, self.title, "title", 220, "article"):
            include_slug_in_update_fields(kwargs)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    @property
    def reading_minutes(self):
        return max(round(len(self.content.split()) / 200), 1)


class ArticleRead(TimeStamp):
    """Pembaca yang menyelesaikan artikel (dihitung sekali per pembaca)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="article_reads",
    )
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="reads")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("user", "article"), name="articles_read_once_per_user"
            )
        ]
        indexes = [
            models.Index(fields=("user", "created_at"), name="articles_read_user_idx")
        ]
