import uuid

from django.conf import settings
from django.db import models

from apps.core.models import TimeStamp


class Notification(TimeStamp):
    """Kabar untuk pengguna. Dibuat lewat ``notifications.services.notify``;
    app ini tidak mengimpor model app lain, hanya menyimpan judul, teks, dan tautan."""

    class Kind(models.TextChoices):
        POST_LIKED = "post_liked", "Postingan disukai"
        POST_COMMENTED = "post_commented", "Komentar baru"
        COMMENT_REPLIED = "comment_replied", "Balasan baru"
        COMMENT_LIKED = "comment_liked", "Komentar disukai"
        BADGE_EARNED = "badge_earned", "Lencana baru"
        CHALLENGE_COMPLETED = "challenge_completed", "Challenge selesai"
        DONATION_SUBMITTED = "donation_submitted", "Donasi perlu diverifikasi"
        DONATION_APPROVED = "donation_approved", "Donasi disetujui"
        DONATION_REJECTED = "donation_rejected", "Donasi ditolak"
        ARTICLE_SUBMITTED = "article_submitted", "Artikel perlu ditinjau"
        ARTICLE_APPROVED = "article_approved", "Artikel terbit"
        ARTICLE_REJECTED = "article_rejected", "Artikel perlu revisi"
        CONTENT_REMOVED = "content_removed", "Konten dihapus admin"

    # (ikon lucide, warna) per jenis notifikasi
    STYLE = {
        Kind.POST_LIKED: ("heart", "tertiary"),
        Kind.POST_COMMENTED: ("message-circle", "primary"),
        Kind.COMMENT_REPLIED: ("reply", "primary"),
        Kind.COMMENT_LIKED: ("heart", "tertiary"),
        Kind.BADGE_EARNED: ("award", "gold"),
        Kind.CHALLENGE_COMPLETED: ("trophy", "gold"),
        Kind.DONATION_SUBMITTED: ("inbox", "secondary"),
        Kind.DONATION_APPROVED: ("badge-check", "primary"),
        Kind.DONATION_REJECTED: ("circle-alert", "danger"),
        Kind.ARTICLE_SUBMITTED: ("file-pen-line", "secondary"),
        Kind.ARTICLE_APPROVED: ("book-open-check", "primary"),
        Kind.ARTICLE_REJECTED: ("circle-alert", "danger"),
        Kind.CONTENT_REMOVED: ("shield-alert", "danger"),
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    kind = models.CharField(max_length=40, choices=Kind.choices)
    title = models.CharField(max_length=160)
    message = models.CharField(max_length=300, blank=True)
    url = models.CharField(max_length=500, blank=True)
    # Mencegah notifikasi berulang, mis. suka -> batal -> suka
    dedupe_key = models.CharField(max_length=120, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=("recipient", "read_at", "-created_at"),
                name="notification_inbox_idx",
            )
        ]

    def __str__(self):
        return f"{self.get_kind_display()} for {self.recipient}"

    @property
    def is_read(self):
        return self.read_at is not None

    @property
    def icon(self):
        return self.STYLE.get(self.kind, ("bell", "neutral"))[0]

    @property
    def tone(self):
        return self.STYLE.get(self.kind, ("bell", "neutral"))[1]
