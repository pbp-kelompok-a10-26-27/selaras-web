from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Notification

Kind = Notification.Kind


def notify(recipient, kind, title, message="", url="", actor=None, dedupe_key=""):
    """Create one notification. People are never notified about their own actions,
    and an event with a ``dedupe_key`` is only stored once per actor."""

    if recipient is None or not recipient.is_active:
        return None
    if actor is not None and actor.pk == recipient.pk:
        return None
    if (
        dedupe_key
        and Notification.objects.filter(
            recipient=recipient, kind=kind, actor=actor, dedupe_key=dedupe_key
        ).exists()
    ):
        return None
    return Notification.objects.create(
        recipient=recipient,
        actor=actor,
        kind=kind,
        title=title[:160],
        message=message[:300],
        url=url,
        dedupe_key=dedupe_key,
    )


def notify_admins(kind, title, message="", url="", actor=None):
    admins = get_user_model().objects.filter(role="admin", is_active=True)
    if actor is not None:
        admins = admins.exclude(pk=actor.pk)
    Notification.objects.bulk_create(
        Notification(
            recipient=admin,
            actor=actor,
            kind=kind,
            title=title[:160],
            message=message[:300],
            url=url,
        )
        for admin in admins
    )


def unread_count(user):
    if not getattr(user, "is_authenticated", False):
        return 0
    return Notification.objects.filter(recipient=user, read_at__isnull=True).count()


def mark_read(notification):
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=("read_at", "updated_at"))


def mark_all_read(user):
    return Notification.objects.filter(recipient=user, read_at__isnull=True).update(
        read_at=timezone.now()
    )


def display_name(user):
    return user.get_full_name().strip() or user.get_username()
