"""Hitung progres target challenge dari aktivitas di modul lain.

Selain check-in, semua target dihitung dari artikel yang dibaca, donasi yang
disetujui, postingan, suka, dan komentar. Hanya modul ini yang membaca modul
lain; feeds, donations, dan articles tidak mengimpor challenges.

Aktivitas dihitung sejak peserta gabung (atau sejak challenge mulai, mana yang
lebih akhir) sampai akhir hari terakhir challenge.
"""

from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import (
    Count,
    DecimalField,
    F,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import Challenge

GoalType = Challenge.GoalType


def activity_window(participation):
    challenge = participation.challenge
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(challenge.start_date, time.min), tz)
    end = timezone.make_aware(
        datetime.combine(challenge.end_date + timedelta(days=1), time.min), tz
    )
    if participation.created_at and participation.created_at > start:
        start = participation.created_at
    return start, end


def _check_ins(participation, user, start, end):
    return participation.progress_records.filter(is_completed=True).count()


def _articles_read(participation, user, start, end):
    from apps.articles.models import ArticleRead

    return ArticleRead.objects.filter(
        user=user, created_at__gte=start, created_at__lt=end
    ).count()


def _donation_amount(participation, user, start, end):
    from apps.donations.models import Donation

    # Hanya donasi yang sudah disetujui
    total = Donation.objects.filter(
        donor=user,
        status=Donation.Status.APPROVED,
        created_at__gte=start,
        created_at__lt=end,
    ).aggregate(total=Sum("amount"))["total"]
    return int(total or 0)


def _posts_created(participation, user, start, end):
    from apps.feeds.models import Post

    return Post.objects.filter(
        author=user, created_at__gte=start, created_at__lt=end
    ).count()


def _likes_received(participation, user, start, end):
    from apps.feeds.models import Like

    # Suka di postingan sendiri tidak dihitung
    return (
        Like.objects.filter(
            post__author=user, created_at__gte=start, created_at__lt=end
        )
        .exclude(user=user)
        .count()
    )


def _comments_written(participation, user, start, end):
    from apps.feeds.models import Comment

    # Komentar di postingan sendiri tidak dihitung
    return (
        Comment.objects.filter(author=user, created_at__gte=start, created_at__lt=end)
        .exclude(post__author=user)
        .count()
    )


COUNTERS = {
    GoalType.CHECK_IN: _check_ins,
    GoalType.ARTICLES_READ: _articles_read,
    GoalType.DONATION_AMOUNT: _donation_amount,
    GoalType.POSTS_CREATED: _posts_created,
    GoalType.LIKES_RECEIVED: _likes_received,
    GoalType.COMMENTS_WRITTEN: _comments_written,
}

# Satuan progres untuk tiap jenis target
UNITS = {
    GoalType.CHECK_IN: "check-in",
    GoalType.ARTICLES_READ: "artikel",
    GoalType.DONATION_AMOUNT: "rupiah",
    GoalType.POSTS_CREATED: "postingan",
    GoalType.LIKES_RECEIVED: "suka",
    GoalType.COMMENTS_WRITTEN: "komentar",
}

# Ke mana peserta pergi untuk menambah progres
ACTION_URLS = {
    GoalType.ARTICLES_READ: ("articles:html-list", "Baca artikel"),
    GoalType.DONATION_AMOUNT: ("donations:campaign_list", "Donasi sekarang"),
    GoalType.POSTS_CREATED: ("feeds:list", "Bagikan cerita"),
    GoalType.LIKES_RECEIVED: ("feeds:list", "Buka feed"),
    GoalType.COMMENTS_WRITTEN: ("feeds:list", "Ikut ngobrol"),
}

# Jenis target yang bisa bergerak karena tiap peristiwa
GOALS_BY_EVENT = {
    "article_read": (GoalType.ARTICLES_READ,),
    "donation_approved": (GoalType.DONATION_AMOUNT,),
    "post_created": (GoalType.POSTS_CREATED,),
    "like_received": (GoalType.LIKES_RECEIVED,),
    "comment_written": (GoalType.COMMENTS_WRITTEN,),
}


def measure(participation):
    """Nilai progres saat ini untuk satu peserta."""
    start, end = activity_window(participation)
    counter = COUNTERS.get(participation.challenge.goal_type, _check_ins)
    return counter(participation, participation.user, start, end)


def date_window(start_date, end_date):
    """Rentang waktu (aware) dari dua tanggal lokal, tanggal akhir ikut."""
    tz = timezone.get_current_timezone()
    return (
        timezone.make_aware(datetime.combine(start_date, time.min), tz),
        timezone.make_aware(
            datetime.combine(end_date + timedelta(days=1), time.min), tz
        ),
    )


def _activity(goal_type, start, end):
    """Semua baris aktivitas yang dihitung untuk satu jenis target."""
    from apps.articles.models import ArticleRead
    from apps.donations.models import Donation
    from apps.feeds.models import Comment, Like, Post

    from .models import ChallengeProgress

    window = {"created_at__gte": start, "created_at__lt": end}
    if goal_type == GoalType.ARTICLES_READ:
        return ArticleRead.objects.filter(**window)
    if goal_type == GoalType.DONATION_AMOUNT:
        return Donation.objects.filter(status=Donation.Status.APPROVED, **window)
    if goal_type == GoalType.POSTS_CREATED:
        return Post.objects.filter(**window)
    if goal_type == GoalType.LIKES_RECEIVED:
        return Like.objects.filter(**window).exclude(user=F("post__author"))
    if goal_type == GoalType.COMMENTS_WRITTEN:
        return Comment.objects.filter(**window).exclude(author=F("post__author"))
    return ChallengeProgress.objects.filter(
        is_completed=True,
        progress_date__gte=timezone.localdate(start),
        progress_date__lt=timezone.localdate(end),
    )


# Field yang menunjukkan pemilik aktivitas
OWNER_FIELD = {
    GoalType.ARTICLES_READ: "user",
    GoalType.DONATION_AMOUNT: "donor",
    GoalType.POSTS_CREATED: "author",
    GoalType.LIKES_RECEIVED: "post__author",
    GoalType.COMMENTS_WRITTEN: "author",
    GoalType.CHECK_IN: "participation__user",
}


def _total(rows, goal_type):
    if goal_type == GoalType.DONATION_AMOUNT:
        return int(rows.aggregate(total=Sum("amount"))["total"] or 0)
    return rows.count()


def community_total(goal_type, start_date, end_date):
    """Total progres seluruh komunitas."""
    return _total(_activity(goal_type, *date_window(start_date, end_date)), goal_type)


def user_total(goal_type, user, start_date, end_date):
    """Kontribusi satu orang ke target komunitas."""
    rows = _activity(goal_type, *date_window(start_date, end_date))
    return _total(rows.filter(**{OWNER_FIELD[goal_type]: user}), goal_type)


def annotate_values(challenge, participations):
    """Tambahkan ``value`` (progres) ke tiap peserta dalam satu query, dihitung
    sejak masing-masing gabung, sama seperti ``measure``."""
    if not challenge.is_tracked:
        return participations.annotate(
            value=Count(
                "progress_records", filter=Q(progress_records__is_completed=True)
            )
        )
    start, end = date_window(challenge.start_date, challenge.end_date)
    owner = OWNER_FIELD[challenge.goal_type]
    rows = (
        _activity(challenge.goal_type, start, end)
        .filter(**{owner: OuterRef("user"), "created_at__gte": OuterRef("created_at")})
        .order_by()
        .values(owner)
    )
    if challenge.goal_type == GoalType.DONATION_AMOUNT:
        rows = rows.annotate(n=Sum("amount")).values("n")
        empty = Value(
            Decimal("0"), output_field=DecimalField(max_digits=14, decimal_places=2)
        )
    else:
        rows = rows.annotate(n=Count("pk")).values("n")
        empty = Value(0)
    return participations.annotate(value=Coalesce(Subquery(rows[:1]), empty))
