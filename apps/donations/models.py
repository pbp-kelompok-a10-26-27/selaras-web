import uuid
from pathlib import Path

from django.conf import settings
from django.db import models

from apps.core.models import TimeStamp
from apps.core.storage import private_storage
from apps.core.utils import include_slug_in_update_fields, set_unique_slug


def proof_upload_to(instance, filename):
    """Nama acak agar bukti transfer tidak bisa ditebak."""
    return f"donations/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"


class Campaign(TimeStamp):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draf"
        PUBLISHED = "PUBLISHED", "Terbit"
        CLOSED = "CLOSED", "Ditutup"

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField()
    image = models.ImageField(upload_to="campaigns/", blank=True)
    target_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        # Slug dibuat sekali agar tautan tetap valid saat judul diubah
        if not self.slug and set_unique_slug(
            self, self.title, "title", 220, "campaign"
        ):
            include_slug_in_update_fields(kwargs)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class Donation(TimeStamp):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Menunggu"
        APPROVED = "APPROVED", "Disetujui"
        REJECTED = "REJECTED", "Ditolak"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(
        Campaign, on_delete=models.PROTECT, related_name="donations"
    )
    donor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="donations"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    # Disimpan di luar MEDIA_ROOT, hanya bisa diunduh lewat view yang mengecek pemilik
    proof = models.FileField(
        upload_to=proof_upload_to, storage=private_storage, blank=True
    )
    # Pesan semangat di daftar donatur kampanye
    message = models.CharField(max_length=280, blank=True)
    # Sembunyikan nama donatur di daftar publik (admin tetap melihat)
    is_anonymous = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_donations",
    )
    # Dikirim ke donatur saat donasi ditolak
    rejection_reason = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-created_at"]
