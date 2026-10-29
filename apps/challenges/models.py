from django.conf import settings
from django.db import models
from django.db.models import Q, UniqueConstraint
from django.utils import timezone

from apps.core.models import TimeStamp
from apps.core.utils import include_slug_in_update_fields, set_unique_slug


class Badge(TimeStamp):
    """Hadiah yang dibuat admin dan bisa dipasang di beberapa challenge."""

    class Tone(models.TextChoices):
        PRIMARY = "primary", "Hijau daun"
        SECONDARY = "secondary", "Hijau hutan"
        TERTIARY = "tertiary", "Merah muda"
        GOLD = "gold", "Emas"

    # Ikon Lucide yang bisa dipilih di editor lencana
    ICON_CHOICES = [
        ("award", "Penghargaan"),
        ("medal", "Medali"),
        ("trophy", "Piala"),
        ("crown", "Mahkota"),
        ("gem", "Permata"),
        ("star", "Bintang"),
        ("sparkles", "Kilau"),
        ("flame", "Api"),
        ("zap", "Petir"),
        ("leaf", "Daun"),
        ("sprout", "Tunas"),
        ("trees", "Pohon"),
        ("recycle", "Daur ulang"),
        ("droplets", "Air"),
        ("sun", "Matahari"),
        ("bike", "Sepeda"),
        ("mountain", "Gunung"),
        ("book-open", "Buku"),
        ("hand-heart", "Uluran tangan"),
        ("heart", "Hati"),
        ("message-circle", "Obrolan"),
        ("shield-check", "Perisai"),
    ]

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=40, choices=ICON_CHOICES, default="award")
    tone = models.CharField(max_length=20, choices=Tone.choices, default=Tone.PRIMARY)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if set_unique_slug(self, self.name, "name", 120, "badge"):
            include_slug_in_update_fields(kwargs)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Challenge(TimeStamp):
    class GoalType(models.TextChoices):
        CHECK_IN = "check_in", "Check-in harian"
        ARTICLES_READ = "articles_read", "Artikel dibaca"
        DONATION_AMOUNT = "donation_amount", "Jumlah donasi (Rp)"
        POSTS_CREATED = "posts_created", "Cerita dibagikan"
        LIKES_RECEIVED = "likes_received", "Suka diterima"
        COMMENTS_WRITTEN = "comments_written", "Komentar ditulis"

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField()
    start_date = models.DateField()
    end_date = models.DateField()
    is_published = models.BooleanField(default=False)
    # Selain check-in, progres dihitung otomatis (challenges/metrics.py)
    goal_type = models.CharField(
        max_length=30, choices=GoalType.choices, default=GoalType.CHECK_IN
    )
    # Target angka; challenge check-in memakai jumlah harinya
    goal_target = models.PositiveIntegerField(null=True, blank=True)
    badge = models.ForeignKey(
        Badge,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="challenges",
        help_text="Diberikan otomatis saat peserta mencapai target.",
    )

    def save(self, *args, **kwargs):
        # Slug dibuat sekali agar tautan tetap valid saat judul diubah
        if not self.slug and set_unique_slug(
            self, self.title, "title", 220, "challenge"
        ):
            include_slug_in_update_fields(kwargs)
        super().save(*args, **kwargs)

    @property
    def status(self):
        """Status menurut tanggal: draft, upcoming, active, atau ended."""
        if not self.is_published:
            return "draft"
        today = timezone.localdate()
        if self.end_date < today:
            return "ended"
        if self.start_date > today:
            return "upcoming"
        return "active"

    @property
    def duration_days(self):
        return max(1, (self.end_date - self.start_date).days + 1)

    @property
    def is_tracked(self):
        """True jika progres dihitung dari aktivitas, bukan check-in."""
        return self.goal_type != self.GoalType.CHECK_IN

    @property
    def goal_icon(self):
        return {
            self.GoalType.CHECK_IN: "calendar-check",
            self.GoalType.ARTICLES_READ: "book-open",
            self.GoalType.DONATION_AMOUNT: "hand-heart",
            self.GoalType.POSTS_CREATED: "image-plus",
            self.GoalType.LIKES_RECEIVED: "heart",
            self.GoalType.COMMENTS_WRITTEN: "message-circle",
        }.get(self.goal_type, "target")

    @property
    def target(self):
        if not self.is_tracked:
            return self.duration_days
        return max(self.goal_target or 1, 1)

    def __str__(self):
        return self.title


class ChallengeParticipation(TimeStamp):
    challenge = models.ForeignKey(
        Challenge, on_delete=models.CASCADE, related_name="participations"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="challenge_participations",
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=("challenge", "user"), name="unique_challenge_participant"
            )
        ]


class ChallengeProgress(TimeStamp):
    participation = models.ForeignKey(
        ChallengeParticipation,
        on_delete=models.CASCADE,
        related_name="progress_records",
    )
    progress_date = models.DateField()
    notes = models.TextField(blank=True)
    is_completed = models.BooleanField(default=False)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=("participation", "progress_date"),
                name="unique_daily_challenge_progress",
            )
        ]


class UserBadge(TimeStamp):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="badges"
    )
    badge = models.ForeignKey(
        Badge, on_delete=models.CASCADE, related_name="awarded_to"
    )
    # Challenge asal lencana (tetap tercatat walau challenge dihapus)
    challenge = models.ForeignKey(
        Challenge,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="awarded_badges",
    )
    awarded_at = models.DateTimeField(auto_now_add=True)
    # Satu lencana yang tampil di samping nama
    is_featured = models.BooleanField(default=False)

    class Meta:
        constraints = [
            UniqueConstraint(fields=("user", "badge"), name="unique_user_badge"),
            UniqueConstraint(
                fields=("user",),
                condition=Q(is_featured=True),
                name="one_featured_badge_per_user",
            ),
        ]


class CommunityGoal(TimeStamp):
    """Target bersama seluruh komunitas, misalnya "2.000 artikel dibaca bulan ini".
    Dihitung dari aktivitas semua orang di antara dua tanggal."""

    title = models.CharField(max_length=160)
    description = models.CharField(max_length=300, blank=True)
    goal_type = models.CharField(
        max_length=30,
        choices=Challenge.GoalType.choices,
        default=Challenge.GoalType.ARTICLES_READ,
    )
    target = models.PositiveIntegerField()
    start_date = models.DateField()
    end_date = models.DateField()
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ["end_date", "title"]

    def __str__(self):
        return self.title

    @property
    def goal_icon(self):
        return Challenge(goal_type=self.goal_type).goal_icon

    @property
    def status(self):
        if not self.is_published:
            return "draft"
        today = timezone.localdate()
        if self.end_date < today:
            return "ended"
        if self.start_date > today:
            return "upcoming"
        return "active"
