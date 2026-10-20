# Utils Functions

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

