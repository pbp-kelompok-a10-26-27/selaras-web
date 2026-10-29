"""Progres challenge, penyelesaian, lencana, peringkat, dan ringkasan dampak."""

from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

from apps.notifications.services import Kind, notify

from . import metrics
from .models import Challenge, ChallengeParticipation, UserBadge


def get_progress(participation):
    """Data progres satu peserta untuk template."""
    challenge = participation.challenge
    target = challenge.target
    current = metrics.measure(participation)
    percent = min(100, int(current * 100 / target)) if target else 0
    action = metrics.ACTION_URLS.get(challenge.goal_type)
    return {
        "challenge": challenge,
        "participation": participation,
        "goal_type": challenge.goal_type,
        "is_money": challenge.goal_type == Challenge.GoalType.DONATION_AMOUNT,
        "current": current,
        "target": target,
        "remaining": max(target - current, 0),
        "percent": percent,
        "reached": current >= target,
        "completed": participation.completed_at is not None or current >= target,
        "unit": metrics.UNITS[challenge.goal_type],
        "action_url": reverse(action[0]) if action else "",
        "action_label": action[1] if action else "",
    }


def evaluate(participation):
    """Ukur progres dan tandai selesai begitu target tercapai.

    Mengembalikan (progres, lencana yang didapat atau None).
    """
    progress = get_progress(participation)
    badge = None
    if progress["reached"] and participation.completed_at is None:
        badge = complete(participation)
        progress["completed"] = True
    return progress, badge


@transaction.atomic
def complete(participation):
    """Tandai selesai dan berikan lencana challenge."""
    locked = ChallengeParticipation.objects.select_for_update().get(pk=participation.pk)
    if locked.completed_at is not None:
        participation.completed_at = locked.completed_at
        return None
    locked.completed_at = participation.completed_at = timezone.now()
    locked.save(update_fields=("completed_at", "updated_at"))

    challenge = participation.challenge
    url = reverse("challenges:detail", args=(challenge.slug,))
    badge = challenge.badge
    if badge is not None:
        _, created = UserBadge.objects.get_or_create(
            user=participation.user,
            badge=badge,
            defaults={"challenge": challenge},
        )
        if created:
            notify(
                participation.user,
                Kind.BADGE_EARNED,
                f"Lencana baru: {badge.name}",
                f"Kamu menyelesaikan “{challenge.title}”. Pasang lencananya di profil!",
                url=reverse("accounts:profile") + "#badges",
            )
            return badge
        badge = None
    notify(
        participation.user,
        Kind.CHALLENGE_COMPLETED,
        f"Challenge selesai: {challenge.title}",
        "Target tercapai. Kerja bagus!",
        url=url,
    )
    return badge


def evaluate_user(user, event):
    """Cek ulang challenge pengguna setelah ada aktivitas di modul lain.

    ``event`` adalah kunci ``metrics.GOALS_BY_EVENT``. Mengembalikan lencana baru.
    """
    if user is None or not user.is_authenticated:
        return []
    goal_types = metrics.GOALS_BY_EVENT.get(event, ())
    today = timezone.localdate()
    participations = ChallengeParticipation.objects.filter(
        user=user,
        completed_at__isnull=True,
        challenge__is_published=True,
        challenge__goal_type__in=goal_types,
        challenge__start_date__lte=today,
        # Donasi yang baru disetujui setelah challenge selesai tetap dihitung
        challenge__end_date__gte=today - timedelta(days=30),
    ).select_related("challenge__badge", "user")
    earned = []
    for participation in participations:
        _, badge = evaluate(participation)
        if badge is not None:
            earned.append(badge)
    return earned


def active_progress(user, goal_types=None, limit=3):
    """Kartu progres challenge yang sedang berjalan untuk panel samping."""
    if user is None or not user.is_authenticated:
        return []
    today = timezone.localdate()
    participations = ChallengeParticipation.objects.filter(
        user=user,
        challenge__is_published=True,
        challenge__start_date__lte=today,
        challenge__end_date__gte=today,
    ).select_related("challenge__badge", "user")
    if goal_types:
        participations = participations.filter(challenge__goal_type__in=goal_types)
    participations = participations.order_by("completed_at", "challenge__end_date")
    return [get_progress(p) for p in participations[:limit]]


def check_in_streaks(participation):
    """(saat ini, terbaik) hari check-in berturut-turut."""
    days = sorted(
        participation.progress_records.filter(is_completed=True).values_list(
            "progress_date", flat=True
        )
    )
    best = run = 0
    previous = None
    for day in days:
        run = run + 1 if previous and day - previous == timedelta(days=1) else 1
        best = max(best, run)
        previous = day
    today = timezone.localdate()
    current = run if previous and today - previous <= timedelta(days=1) else 0
    return current, best


def set_featured_badge(user, user_badge_id):
    """Pasang satu lencana di samping nama (None untuk melepas)."""
    with transaction.atomic():
        UserBadge.objects.filter(user=user, is_featured=True).update(is_featured=False)
        if user_badge_id:
            return UserBadge.objects.filter(user=user, pk=user_badge_id).update(
                is_featured=True
            )
    return 0


# ------------------------------------------------------------------ leaderboard

LEADERBOARD_SIZE = 10


def leaderboard(challenge, viewer=None, size=LEADERBOARD_SIZE):
    """Urutkan peserta: progres terbanyak, lalu yang selesai lebih dulu, lalu yang
    gabung lebih dulu. Progres sama yang belum selesai berbagi peringkat (1, 2, 2, 4).
    Mengembalikan (baris teratas, baris penonton jika di luar teratas, total)."""
    from .queries import featured_badge_prefetch

    participations = metrics.annotate_values(
        challenge,
        challenge.participations.select_related("user").prefetch_related(
            featured_badge_prefetch("user")
        ),
    )
    target = challenge.target
    far_future = timezone.now() + timedelta(days=36500)
    entries = sorted(
        participations,
        key=lambda p: (
            -int(p.value or 0),
            p.completed_at or far_future,
            p.created_at or far_future,
        ),
    )
    rows = []
    previous = None
    for position, participation in enumerate(entries, start=1):
        value = int(participation.value or 0)
        finished = participation.completed_at is not None
        same_as_previous = (
            previous is not None
            and not finished
            and not previous["completed"]
            and previous["value"] == value
        )
        row = {
            "rank": previous["rank"] if same_as_previous else position,
            "user": participation.user,
            "value": value,
            "percent": min(100, int(value * 100 / target)) if target else 0,
            "completed": finished,
            "is_me": viewer is not None and participation.user_id == viewer.pk,
        }
        rows.append(row)
        previous = row
    top = rows[:size]
    me = next((row for row in rows[size:] if row["is_me"]), None)
    return top, me, len(rows)


# -------------------------------------------------------------- community goals


def community_goals(user=None, limit=None, include_upcoming=False):
    """Target komunitas yang sedang berjalan, lengkap dengan kontribusi pengguna."""
    from .models import CommunityGoal

    today = timezone.localdate()
    goals = CommunityGoal.objects.filter(is_published=True, end_date__gte=today)
    if not include_upcoming:
        goals = goals.filter(start_date__lte=today)
    goals = goals.order_by("end_date", "title")
    if limit:
        goals = goals[:limit]
    signed_in = user is not None and user.is_authenticated
    return [goal_progress(goal, user if signed_in else None) for goal in goals]


def goal_progress(goal, user=None):
    from .models import Challenge

    current = metrics.community_total(goal.goal_type, goal.start_date, goal.end_date)
    mine = (
        metrics.user_total(goal.goal_type, user, goal.start_date, goal.end_date)
        if user is not None
        else None
    )
    action = metrics.ACTION_URLS.get(goal.goal_type)
    return {
        "goal": goal,
        "current": current,
        "target": goal.target,
        "percent": min(100, int(current * 100 / goal.target)) if goal.target else 0,
        "reached": current >= goal.target,
        "mine": mine,
        "is_money": goal.goal_type == Challenge.GoalType.DONATION_AMOUNT,
        "unit": metrics.UNITS[goal.goal_type],
        "days_left": max((goal.end_date - timezone.localdate()).days, 0),
        "action_url": reverse(action[0]) if action else reverse("challenges:list"),
        "action_label": action[1] if action else "Lihat challenge",
    }


# ---------------------------------------------------------------- personal impact


def impact_summary(user):
    """Ringkasan aktivitas satu orang di seluruh SELARAS."""
    from apps.donations.models import Donation

    participations = list(
        ChallengeParticipation.objects.filter(user=user).select_related("challenge")
    )
    longest = 0
    for participation in participations:
        if not participation.challenge.is_tracked:
            longest = max(longest, check_in_streaks(participation)[1])
    return {
        "articles_read": user.article_reads.count(),
        "articles_published": user.articles.filter(status="PUBLISHED").count(),
        "challenges_joined": len(participations),
        "challenges_completed": sum(1 for p in participations if p.completed_at),
        "longest_streak": longest,
        "badges": user.badges.count(),
        "posts": user.posts.count(),
        "encouragements": user.comments.exclude(post__author=user).count(),
        # Hanya suka dari orang lain
        "likes_received": user.posts.aggregate(
            total=Count("likes", filter=~Q(likes__user=user))
        )["total"]
        or 0,
        "campaigns_supported": Donation.objects.filter(
            donor=user, status=Donation.Status.APPROVED
        )
        .values("campaign")
        .distinct()
        .count(),
    }
