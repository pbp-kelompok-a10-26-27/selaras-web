# Utils Functions

from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify


def generate_slug(text):
    """
    Generate a slug from the given text.
    """
    return slugify(text)


def get_query_params(request, allowed_filters):
    """Return normalized filters and bounded pagination from a request query string."""
    filters = {}
    for key in allowed_filters:
        value = request.GET.get(key, "").strip()
        if value:
            filters[key] = value

    try:
        page = max(int(request.GET.get("page", 1)), 1)
    except (TypeError, ValueError):
        page = 1

    try:
        page_size = min(max(int(request.GET.get("page_size", 20)), 1), 100)
    except (TypeError, ValueError):
        page_size = 20

    return {
        "filters": filters,
        "pagination": {
            "page": page,
            "page_size": page_size,
        },
    }


def set_unique_slug(instance, source, source_field, max_length, fallback):
    """Fill ``instance.slug`` from ``source``, adding -2, -3... until it is unique.

    The slug is regenerated when it is empty, or when the source field changed and
    the slug still matches the old generated value (a hand-edited slug is kept).
    Returns True when the slug was (re)set.
    """
    original = None
    if instance.pk and not instance._state.adding:
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


def include_slug_in_update_fields(kwargs):
    update_fields = kwargs.get("update_fields")
    if update_fields is not None:
        kwargs["update_fields"] = set(update_fields) | {"slug"}


def safe_next_url(request, fallback):
    """``next`` dari form/URL kalau masih di situs ini, selain itu ``fallback``.
    Mencegah open redirect."""
    target = request.POST.get("next") or request.GET.get("next")
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return fallback
