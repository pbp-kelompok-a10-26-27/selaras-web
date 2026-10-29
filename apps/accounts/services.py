from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Count, Q
from django.urls import reverse

from apps.helpdesk.models import Ticket

from .models import User

# Fields that make a profile "complete" (shown as the ring around the avatar)
PROFILE_COMPLETION_FIELDS = (
    ("first_name", "Isi nama depan"),
    ("last_name", "Isi nama belakang"),
    ("email", "Isi email"),
    ("bio", "Tulis bio singkat"),
)


@transaction.atomic
def assign_default_role(user: User) -> User:

    user.role = User.Role.USER
    user.save(update_fields=["role"])

    group, _ = Group.objects.get_or_create(name="User")
    user.groups.add(group)
    return user


def get_profile_completion(user: User) -> dict:
    steps = [
        {"field": field, "label": label, "done": bool(getattr(user, field, ""))}
        for field, label in PROFILE_COMPLETION_FIELDS
    ]
    done = sum(step["done"] for step in steps)
    return {"steps": steps, "percent": round(done / len(steps) * 100)}


def get_profile_stats(user: User) -> list[dict]:
    """Tiga angka utama di profil (satu query per peran)."""

    active = [Ticket.Status.OPEN, Ticket.Status.IN_PROGRESS]
    finished = [Ticket.Status.RESOLVED, Ticket.Status.CLOSED]

    if user.is_admin:
        counts = Ticket.objects.aggregate(
            assigned=Count("id", filter=Q(assigned_to=user, status__in=active)),
            solved=Count("id", filter=Q(assigned_to=user, status__in=finished)),
            queue=Count("id", filter=Q(assigned_to__isnull=True, status__in=active)),
        )
        href = reverse("dashboard:admin_ticket_list")
        return [
            {
                "label": "Ditugaskan ke kamu",
                "value": counts["assigned"],
                "icon": "life-buoy",
                "hint": "Tiket aktif yang menunggumu",
                "href": href,
            },
            {
                "label": "Tiket selesai",
                "value": counts["solved"],
                "icon": "badge-check",
                "hint": "Diselesaikan atau ditutup olehmu",
                "href": href,
            },
            {
                "label": "Antrean belum ditugaskan",
                "value": counts["queue"],
                "icon": "inbox",
                "hint": "Tiket terbuka yang belum diambil",
                "href": href,
            },
        ]

    counts = user.support_tickets.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status__in=active)),
        solved=Count("id", filter=Q(status__in=finished)),
    )
    href = reverse("helpdesk:ticket_list")
    return [
        {
            "label": "Tiket dibuat",
            "value": counts["total"],
            "icon": "ticket",
            "hint": "Semua pertanyaanmu ke tim bantuan",
            "href": href,
        },
        {
            "label": "Sedang diproses",
            "value": counts["active"],
            "icon": "hourglass",
            "hint": "Tiket yang sedang dikerjakan tim",
            "href": href,
        },
        {
            "label": "Terjawab",
            "value": counts["solved"],
            "icon": "circle-check",
            "hint": "Pertanyaan yang sudah dijawab",
            "href": href,
        },
    ]


def get_badge_collection(user: User) -> dict:
    """Earned badges (newest first) plus the ones still to unlock, with the
    published challenges that award them."""
    from apps.challenges.models import Badge, UserBadge

    earned = list(
        UserBadge.objects.filter(user=user)
        .select_related("badge", "challenge")
        .order_by("-awarded_at")
    )
    owned = {item.badge_id for item in earned}
    locked = list(
        Badge.objects.exclude(pk__in=owned)
        .filter(challenges__is_published=True)
        .distinct()
        .prefetch_related("challenges")
        .order_by("name")
    )
    for badge in locked:
        badge.open_challenges = [
            challenge for challenge in badge.challenges.all() if challenge.is_published
        ]
    featured = next((item for item in earned if item.is_featured), None)
    return {
        "earned": earned,
        "locked": locked,
        "featured": featured,
        "total": len(earned) + len(locked),
    }


def get_impact_summary(user: User) -> dict:
    """Total aktivitas pribadi di semua modul."""
    from apps.challenges.services import impact_summary

    return impact_summary(user)
