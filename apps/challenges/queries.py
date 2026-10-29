"""Query helpers other modules use to show users with their featured badge."""

from django.db.models import Prefetch

from .models import UserBadge


def featured_badge_prefetch(user_path):
    """Prefetch the featured badge of the user at ``user_path`` (e.g. "author")
    into ``featured_badges``, which ``User.featured_badge`` reads."""
    return Prefetch(
        f"{user_path}__badges",
        queryset=UserBadge.objects.filter(is_featured=True).select_related("badge"),
        to_attr="featured_badges",
    )
