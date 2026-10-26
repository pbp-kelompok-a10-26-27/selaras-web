"""Navigation for the admin dashboard sidebar and overview page.

Each section links to a URL name in the "dashboard" namespace. Until a teammate
adds that route, the section shows as "Soon" (disabled) instead of a broken
link; adding the URL is enough to enable it, nothing here has to change.
"""

from django.urls import NoReverseMatch, reverse

from apps.helpdesk.models import Ticket


def _url_or_none(name):
    try:
        return reverse(name)
    except NoReverseMatch:
        return None


# (key, label, lucide icon, URL name, short description for the overview cards)
MANAGEMENT_SECTIONS = [
    (
        "users",
        "Users",
        "users",
        "dashboard:admin_user_list",
        "Manage accounts, roles and access.",
    ),
    (
        "articles",
        "Articles",
        "newspaper",
        "dashboard:admin_article_list",
        "Write, review and publish articles.",
    ),
    (
        "challenges",
        "Challenges",
        "trophy",
        "dashboard:admin_challenge_list",
        "Run challenges, badges and progress.",
    ),
    (
        "donations",
        "Donations",
        "hand-heart",
        "dashboard:admin_donation_list",
        "Track campaigns and donations.",
    ),
    (
        "feeds",
        "Feeds",
        "rss",
        "dashboard:admin_feed_list",
        "Moderate posts, likes and comments.",
    ),
    (
        "helpdesk",
        "Helpdesk",
        "life-buoy",
        "dashboard:admin_ticket_list",
        "Answer and resolve support tickets.",
    ),
]


def get_helpdesk_badge_label(count):
    return f"{count} active ticket{'s' if count != 1 else ''} assigned to you"


def get_sidebar_sections(user):
    """Sections for the sidebar component: [{"label": ..., "items": [...]}]."""

    # Badge on Helpdesk: the admin's own tickets that still need work
    assigned_active = Ticket.objects.filter(
        assigned_to=user,
        status__in=[Ticket.Status.OPEN, Ticket.Status.IN_PROGRESS],
    ).count()

    items = []
    for key, label, icon, url_name, description in MANAGEMENT_SECTIONS:
        item = {
            "key": key,
            "label": label,
            "icon": icon,
            "href": _url_or_none(url_name),
            "description": description,
        }
        if key == "helpdesk":
            # Always set (even 0) so the badge can be updated live; it's hidden while 0
            item["badge"] = assigned_active
            item["badge_label"] = get_helpdesk_badge_label(assigned_active)
        items.append(item)

    return [
        {
            "label": "",
            "items": [
                {
                    "key": "overview",
                    "label": "Overview",
                    "icon": "layout-dashboard",
                    "href": _url_or_none("dashboard:home"),
                    # The overview URL is a prefix of every dashboard URL, so
                    # only an exact match counts as active
                    "exact": True,
                }
            ],
        },
        {"label": "Management", "items": items},
    ]
