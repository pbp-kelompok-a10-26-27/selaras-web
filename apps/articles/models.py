from django.conf import settings
from django.db import models
from django.db.models.functions import Lower
from django.utils.text import slugify

from apps.core.models import TimeStamp


def _set_unique_slug(instance, source, source_field, max_length, fallback):
    original = None
    if instance.pk:
        original = (
            type(instance)
            .objects.filter(pk=instance.pk)
            .values(source_field, "slug")
            .first()
        )

    should_regenerate = not instance.slug or (
        original
        and original[source_field] != source
        and original["slug"] == instance.slug
    )
    if not should_regenerate:
        return False

    base = (slugify(source) or fallback)[:max_length]
    slug = base
    counter = 2
    matches = type(instance).objects.all()
    if instance.pk:
        matches = matches.exclude(pk=instance.pk)
    while matches.filter(slug=slug).exists():
        suffix = f"-{counter}"
        slug = f"{base[: max_length - len(suffix)]}{suffix}"
        counter += 1
    instance.slug = slug
    return True


def _include_slug_in_update_fields(kwargs):
    update_fields = kwargs.get("update_fields")
    if update_fields is not None:
        kwargs["update_fields"] = set(update_fields) | {"slug"}


class ArticleCategory(TimeStamp):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)

    def save(self, *args, **kwargs):
        if _set_unique_slug(self, self.name, "name", 120, "category"):
            _include_slug_in_update_fields(kwargs)
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
        if _set_unique_slug(self, self.name, "name", 120, "tag"):
            _include_slug_in_update_fields(kwargs)
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

    def save(self, *args, **kwargs):
        if _set_unique_slug(self, self.title, "title", 220, "article"):
            _include_slug_in_update_fields(kwargs)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
