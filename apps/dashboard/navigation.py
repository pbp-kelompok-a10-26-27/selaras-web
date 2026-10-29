"""Menu sidebar dan halaman ringkasan dashboard admin.

Bagian yang URL-nya belum ada tampil sebagai "Segera" (nonaktif), bukan tautan
rusak. Cukup tambahkan URL-nya untuk mengaktifkan.
"""

from django.urls import NoReverseMatch, reverse

from apps.articles.models import Article
from apps.donations.models import Donation
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
        "Pengguna",
        "users",
        "dashboard:admin_user_list",
        "Kelola akun, peran, dan akses.",
    ),
    (
        "articles",
        "Artikel",
        "newspaper",
        "dashboard:admin_article_list",
        "Tulis, tinjau, dan terbitkan artikel.",
    ),
    (
        "challenges",
        "Challenge",
        "trophy",
        "dashboard:admin_challenge_list",
        "Atur challenge, lencana, dan progres.",
    ),
    (
        "donations",
        "Donasi",
        "hand-heart",
        "dashboard:admin_donation_list",
        "Pantau kampanye dan donasi.",
    ),
    (
        "feeds",
        "Feeds",
        "rss",
        "dashboard:admin_feed_list",
        "Moderasi postingan, suka, dan komentar.",
    ),
    (
        "helpdesk",
        "Helpdesk",
        "life-buoy",
        "dashboard:admin_ticket_list",
        "Jawab dan selesaikan tiket bantuan.",
    ),
]


def get_helpdesk_badge_label(count):
    return f"{count} tiket aktif ditugaskan ke kamu"


# Angka di menu: hal yang menunggu tindakan admin. key -> (hitung, label)
BADGES = {
    "helpdesk": (
        lambda user: Ticket.objects.filter(
            assigned_to=user,
            status__in=[Ticket.Status.OPEN, Ticket.Status.IN_PROGRESS],
        ).count(),
        get_helpdesk_badge_label,
    ),
    "articles": (
        lambda user: Article.objects.filter(status=Article.Status.PENDING).count(),
        lambda count: f"{count} artikel menunggu review",
    ),
    "donations": (
        lambda user: Donation.objects.filter(status=Donation.Status.PENDING).count(),
        lambda count: f"{count} donasi menunggu verifikasi",
    ),
}


def get_sidebar_sections(user, active=None):
    """Bagian menu untuk komponen sidebar. ``active`` menandai menu yang aktif
    untuk halaman admin di luar /dashboard/ (mis. verifikasi donasi)."""

    items = []
    for key, label, icon, url_name, description in MANAGEMENT_SECTIONS:
        item = {
            "key": key,
            "label": label,
            "icon": icon,
            "href": _url_or_none(url_name),
            "description": description,
        }
        if key in BADGES:
            count, badge_label = BADGES[key]
            # Selalu diisi (walau 0) supaya bisa diperbarui live; disembunyikan saat 0
            item["badge"] = count(user)
            item["badge_label"] = badge_label(item["badge"])
        if active:
            item["active"] = key == active
        items.append(item)

    return [
        {
            "key": "main",
            "label": "",
            "items": [
                {
                    "key": "overview",
                    "label": "Ringkasan",
                    "icon": "layout-dashboard",
                    "href": _url_or_none("dashboard:home"),
                    # The overview URL is a prefix of every dashboard URL, so
                    # only an exact match counts as active
                    "exact": True,
                }
            ],
        },
        {"key": "manage", "label": "Kelola", "items": items},
    ]
