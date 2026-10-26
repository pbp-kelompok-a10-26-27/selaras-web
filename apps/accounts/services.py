from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Count, Q
from django.urls import reverse

from apps.helpdesk.models import Ticket

from .models import User

# Fields that make a profile "complete" (shown as the ring around the avatar)
PROFILE_COMPLETION_FIELDS = (
    ("first_name", "Add your first name"),
    ("last_name", "Add your last name"),
    ("email", "Confirm your email"),
    ("bio", "Write a short bio"),
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
    """Three headline numbers for the profile page, one query each role."""

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
                "label": "Assigned to you",
                "value": counts["assigned"],
                "icon": "life-buoy",
                "hint": "Active tickets waiting on you",
                "href": href,
            },
            {
                "label": "Tickets solved",
                "value": counts["solved"],
                "icon": "badge-check",
                "hint": "Resolved or closed by you",
                "href": href,
            },
            {
                "label": "Unassigned queue",
                "value": counts["queue"],
                "icon": "inbox",
                "hint": "Open tickets nobody has picked up",
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
            "label": "Tickets filed",
            "value": counts["total"],
            "icon": "ticket",
            "hint": "Everything you've asked the help desk",
            "href": href,
        },
        {
            "label": "In progress",
            "value": counts["active"],
            "icon": "hourglass",
            "hint": "Open tickets the team is working on",
            "href": href,
        },
        {
            "label": "Resolved",
            "value": counts["solved"],
            "icon": "circle-check",
            "hint": "Questions that got an answer",
            "href": href,
        },
    ]
