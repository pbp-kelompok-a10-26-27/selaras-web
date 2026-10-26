"""Live numbers for the landing page's growth rings.

Rings: Belajar · Bertindak · Berbagi · Berdonasi.

Each ring reads from the app that owns the data. Every block is guarded, so a
failing query (missing migration, app still in development) shows zeros for
that ring instead of taking the landing page down.
"""

import logging
from decimal import Decimal

from django.apps import apps
from django.db import DatabaseError
from django.db.models import Count, Q, Sum
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

logger = logging.getLogger(__name__)


def _url(name, *args):
    try:
        return reverse(name, args=args)
    except NoReverseMatch:
        return None


def format_rupiah(amount):
    """Rp 12.400.000 (Indonesian thousands separator)."""
    return "Rp " + f"{int(amount or 0):,}".replace(",", ".")


def format_rupiah_compact(amount):
    """12,4 jt / 850 rb / 1,2 M, for big numbers in tight spaces."""
    value = float(amount or 0)
    for size, suffix in ((1_000_000_000, "M"), (1_000_000, "jt"), (1_000, "rb")):
        if value >= size:
            short = f"{value / size:.1f}".rstrip("0").rstrip(".").replace(".", ",")
            return f"{short} {suffix}"
    return f"{int(value)}"


def _safe(section, default, build):
    try:
        return build()
    except (DatabaseError, LookupError):
        logger.exception("Landing page: couldn't load %s stats", section)
        return default


def _learn():
    Article = apps.get_model("articles", "Article")
    published = Article.objects.filter(status=Article.Status.PUBLISHED)
    latest = published.select_related("category").order_by(
        "-published_at", "-created_at"
    )[:3]
    return {
        "count": published.count(),
        "latest": [
            {
                "title": a.title,
                "summary": a.summary,
                "category": a.category.name if getattr(a, "category", None) else "",
                "url": _url("articles:detail", a.slug),
            }
            for a in latest
        ],
    }


def _act():
    Challenge = apps.get_model("challenges", "Challenge")
    Participation = apps.get_model("challenges", "ChallengeParticipation")
    UserBadge = apps.get_model("challenges", "UserBadge")
    today = timezone.localdate()

    active = Challenge.objects.filter(is_published=True, end_date__gte=today)
    latest = active.annotate(participants=Count("participations")).order_by(
        "start_date"
    )[:3]
    return {
        "count": active.count(),
        "participants": Participation.objects.count(),
        "completed": Participation.objects.filter(completed_at__isnull=False).count(),
        "badges": UserBadge.objects.count(),
        "latest": [
            {
                "title": c.title,
                "days": (c.end_date - c.start_date).days + 1,
                "participants": c.participants,
                "starts_in": (c.start_date - today).days,
                "url": _url("challenges:detail", c.slug),
            }
            for c in latest
        ],
    }


def _share():
    Post = apps.get_model("feeds", "Post")
    Like = apps.get_model("feeds", "Like")
    Comment = apps.get_model("feeds", "Comment")
    return {
        "count": Post.objects.count(),
        "likes": Like.objects.count(),
        "comments": Comment.objects.count(),
    }


def _give():
    Campaign = apps.get_model("donations", "Campaign")
    Donation = apps.get_model("donations", "Donation")
    approved = Q(donations__status=Donation.Status.APPROVED)

    campaigns = (
        Campaign.objects.filter(status=Campaign.Status.PUBLISHED)
        .annotate(
            raised=Sum("donations__amount", filter=approved),
            donors=Count("donations__donor", filter=approved, distinct=True),
        )
        .order_by("-created_at")[:3]
    )
    total = Donation.objects.filter(status=Donation.Status.APPROVED).aggregate(
        total=Sum("amount")
    )["total"] or Decimal(0)
    return {
        "count": Campaign.objects.filter(status=Campaign.Status.PUBLISHED).count(),
        "raised": int(total),
        "raised_full": format_rupiah(total),
        "raised_compact": format_rupiah_compact(total),
        "donors": Donation.objects.filter(status=Donation.Status.APPROVED)
        .values("donor")
        .distinct()
        .count(),
        "latest": [
            {
                "title": c.title,
                "raised": format_rupiah(c.raised),
                "target": format_rupiah(c.target_amount),
                "donors": c.donors,
                # Capped at 100 for the bar; the label still shows the real amount
                "percent": min(100, round((c.raised or 0) / c.target_amount * 100))
                if c.target_amount
                else 0,
                "url": _url("donations:campaign_detail", c.slug),
            }
            for c in campaigns
        ],
    }


def _ring_info(learn, act, share, give):
    """What the hero's ring info card says for each layer.

    Read by static/js/landing/home.js.
    """
    return {
        "learn": {
            "kicker": f"Lapisan inti · {learn['count']} artikel",
            "title": "Belajar",
            "text": (
                "Inti dari setiap kebiasaan: memahami mengapa sebuah langkah kecil "
                "berarti."
            ),
            "swatch": "bg-primary-300",
        },
        "act": {
            "kicker": f"Lapisan kedua · {act['count']} tantangan aktif",
            "title": "Bertindak",
            "text": "Ikuti tantangan, catat progres harian, dan raih lencana.",
            "swatch": "bg-primary-500",
        },
        "share": {
            "kicker": f"Lapisan ketiga · {share['count']} cerita",
            "title": "Berbagi",
            "text": (
                "Bagikan perjalanan Anda dan saling menyemangati di feed komunitas."
            ),
            "swatch": "bg-tertiary-300",
        },
        "give": {
            "kicker": f"Lapisan terluar · {give['raised_full']} terkumpul",
            "title": "Berdonasi",
            "text": "Lapisan terluar: dukung kampanye lingkungan yang terverifikasi.",
            "swatch": "bg-secondary-300",
        },
    }


def get_landing_context():
    User = apps.get_model("accounts", "User")
    learn = _safe("articles", {"count": 0, "latest": []}, _learn)
    act = _safe(
        "challenges",
        {"count": 0, "participants": 0, "completed": 0, "badges": 0, "latest": []},
        _act,
    )
    share = _safe("feeds", {"count": 0, "likes": 0, "comments": 0}, _share)
    give = _safe(
        "donations",
        {
            "count": 0,
            "raised": 0,
            "raised_full": "Rp 0",
            "raised_compact": "0",
            "donors": 0,
            "latest": [],
        },
        _give,
    )

    return {
        "members": _safe(
            "members", 0, lambda: User.objects.filter(is_active=True).count()
        ),
        "learn": learn,
        "act": act,
        "share": share,
        "give": give,
        "ring_info": _ring_info(learn, act, share, give),
        # Ring legend and sticky index next to the layers:
        # (key, lucide icon, name = section id)
        "layer_index": [
            ("learn", "book-open", "Belajar"),
            ("act", "footprints", "Bertindak"),
            ("share", "messages-square", "Berbagi"),
            ("give", "hand-heart", "Berdonasi"),
        ],
        "act_steps": [
            (
                "flag",
                "Gabung tantangan",
                "Pilih satu kebiasaan, dari 7 sampai 30 hari.",
            ),
            (
                "calendar-check",
                "Catat setiap hari",
                "Satu catatan singkat per hari menjaga ritmenya.",
            ),
            (
                "award",
                "Raih lencana",
                "Selesaikan tantangan dan lencananya menjadi milik Anda.",
            ),
        ],
        # Impact estimator: rough per-person, per-day figures, for illustration only
        "habits": [
            {
                "key": "tumbler",
                "icon": "cup-soda",
                "label": "Membawa tumbler",
                "per_day": 1,
                "unit": "botol plastik",
                "note": "tidak berakhir di tempat sampah, sungai, atau laut.",
            },
            {
                "key": "bag",
                "icon": "shopping-bag",
                "label": "Membawa tas belanja",
                "per_day": 1,
                "unit": "kantong plastik",
                "note": "tidak dipakai sekali lalu dibuang.",
            },
            {
                "key": "bike",
                "icon": "bike",
                "label": "Bersepeda 2 km",
                "per_day": 0.2,
                "unit": "kg CO₂e",
                "note": "emisi yang dihindari dibandingkan naik sepeda motor.",
            },
            {
                "key": "ac",
                "icon": "air-vent",
                "label": "Mematikan AC 1 jam lebih awal",
                "per_day": 1,
                "unit": "kWh listrik",
                "note": "energi yang dihemat dari jaringan listrik.",
            },
        ],
        # Impact estimator: quick picks next to the duration and people sliders
        "impact_days": [
            (7, "1 minggu"),
            (30, "1 bulan"),
            (90, "3 bulan"),
            (365, "1 tahun"),
        ],
        "impact_people": [
            (1, "Anda"),
            (30, "Satu kelas"),
            (100, "Satu RT"),
            (1000, "Satu kampus"),
        ],
        # Try-it demos under each layer. They run in the browser only and save nothing.
        "learn_quiz": [
            {
                "text": (
                    "Plastik dengan simbol segitiga daur ulang pasti akan didaur ulang."
                ),
                "answer": "mitos",
                "why": (
                    "Simbol itu hanya menunjukkan jenis plastiknya. Banyak plastik "
                    "bersimbol tetap berakhir di TPA."
                ),
            },
            {
                "text": "Sisa makanan yang menumpuk di TPA menghasilkan gas metana.",
                "answer": "fakta",
                "why": (
                    "Sampah organik yang membusuk tanpa udara melepaskan metana, gas "
                    "rumah kaca yang jauh lebih kuat daripada CO₂."
                ),
            },
            {
                "text": (
                    "Charger yang tetap tercolok tanpa ponsel tidak memakai listrik "
                    "sama sekali."
                ),
                "answer": "mitos",
                "why": (
                    "Charger yang tercolok masih menarik sedikit listrik. Kecil per "
                    "hari, tetapi berjalan terus."
                ),
            },
            {
                "text": "Membilas kemasan sebelum dipilah membantu proses daur ulang.",
                "answer": "fakta",
                "why": (
                    "Kemasan bersih lebih mudah diterima pendaur ulang dan tidak "
                    "mengotori sampah lain."
                ),
            },
        ],
        "act_demo_badges": [
            (1, "sprout", "Langkah pertama"),
            (3, "flame", "Mulai terbiasa"),
            (7, "award", "Kebiasaan baru"),
        ],
        "share_demo_prompts": [
            "Hari ini saya membawa tumbler sendiri.",
            "Saya menolak sedotan plastik saat makan siang.",
            "Saya mulai memilah sampah di rumah.",
        ],
        "share_demo_posts": [
            {
                "name": "Rani",
                "initial": "R",
                "time": "2 jam lalu",
                "text": (
                    "Hari ke-12 tanpa plastik sekali pakai. Ternyata membawa tumbler "
                    "jauh lebih mudah daripada yang saya bayangkan."
                ),
                "likes": 24,
            },
            {
                "name": "Bima",
                "initial": "B",
                "time": "5 jam lalu",
                "text": (
                    "Akhirnya punya komposter kecil di balkon. Sisa sayur sekarang "
                    "jadi pupuk untuk cabai."
                ),
                "likes": 17,
            },
        ],
        "give_demo": {
            "title": "Tanam mangrove di pesisir utara",
            "target": 5_000_000,
            "target_label": format_rupiah(5_000_000),
            "raised": 3_150_000,
            "raised_label": format_rupiah(3_150_000),
            "percent": 63,
            "donors": 84,
            "per_seedling": 5_000,
            "amounts": [
                (amount, format_rupiah_compact(amount))
                for amount in (10_000, 25_000, 50_000, 100_000)
            ],
        },
        # The closing section's faint log-end rings
        "cta_rings": list(range(40, 400, 26)),
        "urls": {
            "articles": _url("articles:list"),
            "challenges": _url("challenges:list"),
            "feed": _url("feeds:list"),
            "donations": _url("donations:campaign_list"),
            "helpdesk": _url("helpdesk:ticket_list"),
            "register": _url("accounts:register"),
            "login": _url("accounts:login"),
        },
    }
