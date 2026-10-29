"""Seed every module with demo data for integration checks, edge cases and UAT.

    python manage.py seed_demo            # add the demo data (safe to re-run)
    python manage.py seed_demo --reset    # remove the demo data first, then seed
    python manage.py seed_demo --clear    # only remove the demo data

All demo accounts log in as ``demo_<name>`` (e.g. ``demo_sari``), use the email
domain ``@seed.selaras.test`` and the password ``selaras123``; the email
domain is how ``--reset`` finds what to delete. Everything else the command
creates (badges, challenges, campaigns, articles, ...) hangs off those accounts
or is listed in the constants below, so real data is never touched.

The data is fixed (no randomness), so every run produces the same scenario and
the UAT checklist printed at the end always matches what is on screen.
"""

from datetime import datetime, time, timedelta
from decimal import Decimal
from io import BytesIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageDraw

PASSWORD = "selaras123"
DOMAIN = "seed.selaras.test"
# Login names get this prefix so they never clash with real accounts (e.g. "admin")
PREFIX = "demo_"

# Palette from the design tokens, for generated pictures
GREEN, FOREST, BLOSSOM, SAND, SKY = (
    (136, 157, 87),
    (57, 73, 47),
    (195, 158, 166),
    (230, 228, 223),
    (120, 160, 190),
)

USERS = [
    # username, first, last, role, bio, has_avatar
    ("admin", "Tim", "Selaras", "admin", "Admin utama SELARAS.", True),
    ("moderator", "Rani", "Moderator", "admin", "Admin konten & donasi.", False),
    ("sari", "Sari", "Wulandari", "user", "Suka berkebun di balkon 🌱", True),
    ("budi", "Budi", "Santoso", "user", "Pesepeda ke kantor setiap hari.", True),
    ("citra", "Citra", "Lestari", "user", "", False),
    ("dimas", "Dimas", "Pratama", "user", "Belajar zero waste pelan-pelan.", False),
    # Edge: no first/last name -> the username is shown everywhere
    ("noname", "", "", "user", "", False),
    # Edge: very long name, unicode and emoji
    (
        "panjang",
        "Bartholomeus Alexander Christopher",
        "Wijayakusuma-Nugroho 🌍",
        "user",
        "Nama sangat panjang untuk menguji pemotongan teks di kartu dan daftar.",
        False,
    ),
    # Edge: brand-new account with no activity at all
    ("baru", "Eka", "Baru", "user", "", False),
]
INACTIVE_USER = ("nonaktif", "Akun", "Nonaktif")

BADGES = [
    # name, icon, tone, description
    ("Kompos Pro", "sprout", "gold", "Rajin berbagi cerita kebun dan kompos."),
    ("Kutu Buku Hijau", "book-open", "secondary", "Menyelesaikan bacaan edukasi."),
    ("Dermawan", "hand-heart", "tertiary", "Berdonasi untuk aksi lingkungan."),
    ("Penyemangat", "message-circle", "primary", "Aktif menyemangati di feed."),
    ("Bintang Feed", "star", "gold", "Ceritanya banyak disukai."),
    ("Pejuang 7 Hari", "flame", "primary", "Check-in tujuh hari berturut-turut."),
    # Edge: badge no challenge offers yet (must not appear as "to unlock")
    ("Legenda Rahasia", "crown", "gold", "Belum dipakai challenge mana pun."),
]

COMMUNITY_GOALS = [
    # title, goal type, target, start offset, end offset, published
    ("Demo: 50 artikel dibaca bulan ini", "articles_read", 50, -10, 20, True),
    ("Demo: Rp1 juta untuk aksi hijau", "donation_amount", 1_000_000, -10, 20, True),
    ("Demo: 20 cerita komunitas", "posts_created", 20, -7, 7, True),
    # Edge: already reached, upcoming, ended and hidden goals
    ("Demo: 5 cerita pertama", "posts_created", 5, -7, 7, True),
    ("Demo: Pekan komentar positif", "comments_written", 100, 3, 10, True),
    ("Demo: Target bulan lalu", "articles_read", 10, -40, -11, True),
    ("Demo: Target tersembunyi", "likes_received", 10, -1, 10, False),
]

TAGS = [
    "kompos",
    "plastik",
    "energi",
    "air",
    "sepeda",
    "zero waste",
    "berkebun",
    "daur ulang",
    "pangan",
    "hemat",
    "kota",
    "laut",
]

PARAGRAPH = (
    "Langkah kecil yang dilakukan setiap hari jauh lebih berdampak daripada "
    "rencana besar yang tidak pernah dimulai. Mulailah dari dapur, lalu ajak "
    "keluarga dan tetangga untuk ikut mencoba."
)

# Text meant to break layouts or escaping
XSS = '<script>alert("xss")</script><b>tebal?</b> & "kutip"'
LONG_WORD = "superkalifragilistikekspialidosiushijaulestari" * 3


def picture(color, label="", size=(1200, 800), fmt="PNG"):
    """A flat image with a soft circle and an optional label."""
    image = Image.new("RGB", size, color)
    draw = ImageDraw.Draw(image)
    w, h = size
    r = min(w, h) // 3
    lighter = tuple(min(255, c + 40) for c in color)
    draw.ellipse((w // 2 - r, h // 2 - r, w // 2 + r, h // 2 + r), fill=lighter)
    if label:
        draw.text((32, 32), label, fill=(255, 255, 255))
    data = BytesIO()
    image.save(data, format=fmt)
    return data.getvalue()


def file_of(color, name, label="", size=(1200, 800), fmt="PNG"):
    return ContentFile(picture(color, label, size, fmt), name=name)


class Command(BaseCommand):
    help = "Seed all modules with demo data for integration, edge-case and UAT checks."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true", help="Remove demo data first, then seed."
        )
        parser.add_argument(
            "--clear", action="store_true", help="Only remove the demo data."
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Allow running when DEBUG is False (never on production data).",
        )

    # ------------------------------------------------------------------ entry

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            raise CommandError(
                "Refusing to seed with DEBUG=False. Pass --force if this really is "
                "a development or staging database."
            )
        if options["reset"] or options["clear"]:
            self.clear()
            if options["clear"]:
                return
        elif get_user_model().objects.filter(email__endswith=f"@{DOMAIN}").exists():
            self.stdout.write(
                self.style.WARNING(
                    "Demo data already exists. Use --reset to rebuild it from scratch."
                )
            )
            return

        self.today = timezone.localdate()
        self.now = timezone.now()
        with transaction.atomic():
            self.seed_users()
            self.seed_badges()
            self.seed_challenges()
            self.seed_articles()
            self.seed_feed()
            self.seed_donations()
            self.seed_helpdesk()
            self.seed_community_goals()
        # Signals queued challenge checks on commit; settle the rest explicitly
        self.settle_challenges()
        self.seed_notifications()
        self.report()

    # ------------------------------------------------------------------ clear

    def clear(self):
        from apps.articles.models import Article, ArticleCategory, Tag
        from apps.challenges.models import Badge, Challenge, CommunityGoal
        from apps.donations.models import Campaign, Donation
        from apps.feeds.models import PostImage

        users = get_user_model().objects.filter(email__endswith=f"@{DOMAIN}")
        with transaction.atomic():
            # Files first (deleting rows does not remove them from disk)
            for image in PostImage.objects.filter(post__author__in=users):
                image.image.delete(save=False)
            for donation in Donation.objects.filter(donor__in=users):
                if donation.proof:
                    donation.proof.delete(save=False)
            for article in Article.objects.filter(author__in=users):
                if article.image:
                    article.image.delete(save=False)
            for user in users:
                if user.avatar:
                    user.avatar.delete(save=False)
            campaigns = Campaign.objects.filter(slug__startswith="demo-")
            for campaign in campaigns:
                if campaign.image:
                    campaign.image.delete(save=False)

            # PROTECTed relations before the users
            Donation.objects.filter(donor__in=users).delete()
            Donation.objects.filter(campaign__in=campaigns).delete()
            campaigns.delete()
            Article.objects.filter(author__in=users).delete()
            ArticleCategory.objects.filter(slug__startswith="demo-").delete()
            Tag.objects.filter(name__in=TAGS, articles__isnull=True).delete()
            Challenge.objects.filter(slug__startswith="demo-").delete()
            CommunityGoal.objects.filter(
                title__in=[goal[0] for goal in COMMUNITY_GOALS]
            ).delete()
            Badge.objects.filter(name__in=[b[0] for b in BADGES]).delete()
            count = users.count()
            users.delete()
        self.stdout.write(self.style.SUCCESS(f"Removed demo data ({count} accounts)."))

    # ------------------------------------------------------------------ users

    def seed_users(self):
        User = get_user_model()
        self.users = {}
        colors = [FOREST, GREEN, BLOSSOM, SKY]
        for index, (username, first, last, role, bio, avatar) in enumerate(USERS):
            user = User.objects.create_user(
                username=f"{PREFIX}{username}",
                email=f"{username}@{DOMAIN}",
                password=PASSWORD,
                first_name=first,
                last_name=last,
                role=role,
                bio=bio or None,
                is_staff=role == "admin",
            )
            if avatar:
                user.avatar.save(
                    f"{username}.png",
                    file_of(colors[index % 4], f"{username}.png", size=(256, 256)),
                )
            self.users[username] = user
        username, first, last = INACTIVE_USER
        self.users[username] = User.objects.create_user(
            username=f"{PREFIX}{username}",
            email=f"{username}@{DOMAIN}",
            password=PASSWORD,
            first_name=first,
            last_name=last,
            is_active=False,
        )
        # A long-time member, for "member since" displays
        User.objects.filter(pk=self.users["budi"].pk).update(
            date_joined=self.now - timedelta(days=400)
        )
        self.log("Users", len(self.users))

    # ----------------------------------------------------------------- badges

    def seed_badges(self):
        from apps.challenges.models import Badge

        self.badges = {
            name: Badge.objects.create(
                name=name, icon=icon, tone=tone, description=description
            )
            for name, icon, tone, description in BADGES
        }
        self.log("Badges", len(self.badges))

    # ------------------------------------------------------------- challenges

    def seed_challenges(self):
        from apps.challenges.models import Challenge, ChallengeParticipation
        from apps.challenges.models import ChallengeProgress as Progress

        G = Challenge.GoalType
        t = self.today
        b = self.badges
        specs = [
            # key, title, goal, target, start, end, published, badge
            (
                "checkin",
                "7 Hari Tanpa Plastik",
                G.CHECK_IN,
                None,
                -6,
                0,
                True,
                "Pejuang 7 Hari",
            ),
            (
                "checkin-long",
                "30 Hari Bersepeda",
                G.CHECK_IN,
                None,
                -10,
                19,
                True,
                None,
            ),
            (
                "read",
                "Baca 3 Artikel Edukasi",
                G.ARTICLES_READ,
                3,
                -3,
                10,
                True,
                "Kutu Buku Hijau",
            ),
            (
                "donate",
                "Donasi Rp100.000 Minggu Ini",
                G.DONATION_AMOUNT,
                100000,
                -2,
                5,
                True,
                "Dermawan",
            ),
            (
                "posts",
                "Bagikan 3 Cerita Kebun",
                G.POSTS_CREATED,
                3,
                -5,
                9,
                True,
                "Kompos Pro",
            ),
            (
                "likes",
                "Kumpulkan 5 Suka",
                G.LIKES_RECEIVED,
                5,
                -5,
                9,
                True,
                "Bintang Feed",
            ),
            (
                "comments",
                "Tulis 4 Komentar Penyemangat",
                G.COMMENTS_WRITTEN,
                4,
                -5,
                9,
                True,
                "Penyemangat",
            ),
            # Edge: lifecycle states
            ("upcoming", "Pekan Hemat Air", G.CHECK_IN, None, 3, 9, True, None),
            ("ended", "Bulan Tanpa Sedotan", G.CHECK_IN, None, -40, -10, True, None),
            (
                "draft",
                "Draf: Challenge Laut Bersih",
                G.ARTICLES_READ,
                2,
                0,
                14,
                False,
                None,
            ),
            # Edge: one-day challenge, and a target nobody can reach
            ("oneday", "Satu Hari Tanpa Kendaraan", G.CHECK_IN, None, 0, 0, True, None),
            (
                "huge",
                "Donasi Rp10 Juta",
                G.DONATION_AMOUNT,
                10_000_000,
                -1,
                30,
                True,
                None,
            ),
        ]
        self.challenges = {}
        for key, title, goal, target, start, end, published, badge in specs:
            self.challenges[key] = Challenge.objects.create(
                title=title,
                slug=f"demo-{key}",
                description=(
                    f"{title}. {PARAGRAPH}\n\nTantangan ini dibuat oleh seeder untuk "
                    "pengujian. Ikuti, lalu lihat progresmu bertambah."
                ),
                start_date=t + timedelta(days=start),
                end_date=t + timedelta(days=end),
                is_published=published,
                goal_type=goal,
                goal_target=target,
                badge=b.get(badge) if badge else None,
            )
        # Edge: a description with markup that must be escaped
        Challenge.objects.filter(pk=self.challenges["huge"].pk).update(
            description=f"Uji escape: {XSS}"
        )

        def join(user, key, days_before_start=0):
            """Join and backdate so activity seeded later falls inside the window."""
            challenge = self.challenges[key]
            participation = ChallengeParticipation.objects.create(
                challenge=challenge, user=self.users[user]
            )
            joined = timezone.make_aware(
                datetime.combine(challenge.start_date, time(7))
            ) - timedelta(days=days_before_start)
            ChallengeParticipation.objects.filter(pk=participation.pk).update(
                created_at=joined
            )
            participation.refresh_from_db()
            return participation

        def check_in(participation, offsets, note="Hari ini berhasil!"):
            for offset in offsets:
                Progress.objects.create(
                    participation=participation,
                    progress_date=t - timedelta(days=offset),
                    notes=note if offset % 2 else "",
                    is_completed=True,
                )

        # Check-in: Sari has every day (completes -> badge), Budi has a broken streak
        check_in(join("sari", "checkin"), range(7))
        check_in(join("budi", "checkin"), [0, 1, 2, 5, 6])
        check_in(join("citra", "checkin"), [3])  # streak already broken
        check_in(join("budi", "checkin-long"), range(10))
        join("dimas", "checkin-long")  # joined, no check-ins yet

        # Tracked goals (progress comes from the data seeded below)
        for user in ("sari", "budi", "citra"):
            join(user, "read")
        for user in ("sari", "budi", "dimas"):
            join(user, "donate")
        for user in ("sari", "budi"):
            join(user, "posts")
        for user in ("sari", "citra"):
            join(user, "likes")
        for user in ("budi", "dimas", "citra"):
            join(user, "comments")
        join("sari", "huge")
        join("panjang", "oneday")

        # Ended: one finisher, one who never finished
        finished = join("sari", "ended")
        check_in(finished, [])
        ChallengeParticipation.objects.filter(pk=finished.pk).update(
            completed_at=self.now - timedelta(days=10)
        )
        join("budi", "ended")

        self.log("Challenges", len(self.challenges))

    # --------------------------------------------------------------- articles

    def seed_articles(self):
        from apps.articles.models import Article, ArticleCategory, ArticleRead, Tag

        S = Article.Status
        tags = {name: Tag.objects.get_or_create(name=name)[0] for name in TAGS}
        categories = {
            name: ArticleCategory.objects.get_or_create(name=name)[0]
            for name in ("Lingkungan", "Konsumsi Sadar", "Energi", "Pangan & Kebun")
        }
        # Edge: a category no article uses (can be deleted on the category page)
        ArticleCategory.objects.get_or_create(
            name="Kategori Kosong Demo", defaults={"slug": "demo-kosong"}
        )
        admin, moderator = self.users["admin"], self.users["moderator"]

        def body(paragraphs):
            return "\n\n".join(f"{PARAGRAPH} ({i + 1})" for i in range(paragraphs))

        specs = [
            # title, category, author, status, paragraphs, image color, tags, days ago
            (
                "Memulai Kompos di Rumah Kecil",
                "Pangan & Kebun",
                admin,
                S.PUBLISHED,
                8,
                GREEN,
                ["kompos", "berkebun"],
                1,
            ),
            (
                "Tumbler, Tas Kain, dan Kebiasaan Baru",
                "Konsumsi Sadar",
                admin,
                S.PUBLISHED,
                5,
                BLOSSOM,
                ["plastik", "zero waste"],
                2,
            ),
            (
                "Hemat Listrik Tanpa Repot",
                "Energi",
                moderator,
                S.PUBLISHED,
                6,
                None,
                ["energi", "hemat"],
                3,
            ),
            (
                "Menanam Sayur di Balkon",
                "Pangan & Kebun",
                admin,
                S.PUBLISHED,
                4,
                SKY,
                ["berkebun", "pangan"],
                4,
            ),
            (
                "Belanja di Pasar Tanpa Plastik",
                "Konsumsi Sadar",
                admin,
                S.PUBLISHED,
                3,
                None,
                ["plastik", "pangan"],
                6,
            ),
            (
                "Air Hujan untuk Kebun Kota",
                "Lingkungan",
                moderator,
                S.PUBLISHED,
                5,
                FOREST,
                ["air", "kota"],
                9,
            ),
            (
                "Bersepeda ke Kantor: Panduan Pemula",
                "Lingkungan",
                admin,
                S.PUBLISHED,
                7,
                None,
                ["sepeda", "kota"],
                12,
            ),
            # Edge: no summary, one tiny paragraph, no tags
            ("Catatan Singkat", "Lingkungan", admin, S.PUBLISHED, 1, None, [], 20),
            # Edge: very long title and content with an unbreakable word
            (
                "Panduan Super Lengkap dan Sangat Panjang tentang Mengelola Sampah "
                "Rumah Tangga dari Dapur hingga Bank Sampah di Lingkungan RT",
                "Lingkungan",
                moderator,
                S.PUBLISHED,
                25,
                GREEN,
                TAGS,
                30,
            ),
            # Admin draft
            (
                "Draf Admin: Laut Bebas Sampah",
                "Lingkungan",
                admin,
                S.DRAFT,
                2,
                None,
                ["laut"],
                0,
            ),
        ]
        self.articles = []
        for title, cat, author, status, paragraphs, color, tag_names, days in specs:
            article = Article(
                title=title,
                summary="" if title == "Catatan Singkat" else PARAGRAPH[:140],
                content=body(paragraphs),
                category=categories[cat],
                author=author,
                status=status,
                published_at=(
                    self.now - timedelta(days=days) if status == S.PUBLISHED else None
                ),
            )
            if title.startswith("Panduan Super"):
                article.content += f"\n\n{LONG_WORD}\n\nUji escape: {XSS}"
            if color:
                article.image = file_of(color, "cover.png", title[:30])
            article.save()
            article.tags.set([tags[name] for name in tag_names])
            self.articles.append(article)

        # Community writing in every review state
        sari, budi, citra = self.users["sari"], self.users["budi"], self.users["citra"]
        review = [
            (sari, "Kebun Hidroponik dari Botol Bekas", S.PENDING, "", 2),
            (budi, "Rute Sepeda Teraman di Kota", S.PENDING, "", 0),
            (
                citra,
                "Resep Sabun dari Minyak Jelantah",
                S.REJECTED,
                "Tolong tambahkan sumber dan langkah keamanan saat membuat sabun.",
                3,
            ),
            (sari, "Draf: Cerita Panen Pertama", S.DRAFT, "", 1),
            (budi, "Pengalaman Setahun Tanpa Mobil", S.PUBLISHED, "", 5),
        ]
        for author, title, status, note, days in review:
            article = Article.objects.create(
                title=title,
                summary="Tulisan komunitas untuk menguji alur review.",
                content=body(3),
                category=categories["Lingkungan"],
                author=author,
                status=status,
                submitted_at=(
                    self.now - timedelta(days=days) if status != S.DRAFT else None
                ),
                published_at=(
                    self.now - timedelta(days=days) if status == S.PUBLISHED else None
                ),
                reviewed_at=(
                    self.now - timedelta(days=days - 1)
                    if status in (S.PUBLISHED, S.REJECTED)
                    else None
                ),
                reviewed_by=admin if status in (S.PUBLISHED, S.REJECTED) else None,
                review_note=note,
            )
            article.tags.set([tags["kota"]])
            self.articles.append(article)

        # Reads (these move the "Baca 3 Artikel" challenge through signals)
        published = [a for a in self.articles if a.status == S.PUBLISHED]
        reads = {"sari": 3, "budi": 2, "citra": 1, "dimas": 5, "panjang": 1}
        for username, count in reads.items():
            for article in published[:count]:
                ArticleRead.objects.create(user=self.users[username], article=article)
        self.log("Articles", len(self.articles))

    # ------------------------------------------------------------------- feed

    def seed_feed(self):
        from apps.feeds.models import Comment, CommentLike, Like, Post, PostImage

        u = self.users
        c = self.challenges
        colors = [GREEN, BLOSSOM, SKY, FOREST, SAND]

        def post(author, content, images=0, challenge=None, hours_ago=1, edited=False):
            item = Post.objects.create(
                author=u[author], content=content, challenge=challenge
            )
            for index in range(images):
                photo = PostImage(post=item, position=index)
                photo.image.save(
                    f"seed-{index}.png",
                    file_of(colors[index % 5], "p.png", f"{index + 1}/{images}"),
                    save=False,
                )
                photo.save()
            created = self.now - timedelta(hours=hours_ago)
            Post.objects.filter(pk=item.pk).update(
                created_at=created,
                updated_at=created + timedelta(minutes=30 if edited else 0),
            )
            item.refresh_from_db()
            return item

        posts = {
            "harvest": post(
                "sari",
                "Panen kompos pertama! @demo_budi lihat hasilnya 🌱",
                3,
                c["posts"],
                2,
            ),
            "single": post(
                "budi", "Sepeda pagi ini, 12 km tanpa macet.", 1, c["checkin-long"], 5
            ),
            "text": post(
                "citra",
                "Hari ini aku menolak sedotan plastik tiga kali. Kecil, tapi berasa!",
                0,
                None,
                8,
                edited=True,
            ),
            # Edge: user photo maximum (10) and admin photo maximum (20)
            "max-user": post(
                "sari",
                "Sepuluh foto perjalanan kebun dari bibit sampai panen.",
                10,
                c["posts"],
                12,
            ),
            "max-admin": post(
                "admin",
                "Dokumentasi lengkap kegiatan tanam pohon bersama komunitas.",
                20,
                None,
                20,
            ),
            # Edge: exactly 2000 characters, markup to escape, unbreakable word
            "long": post("panjang", ("Cerita panjang. " * 125)[:2000], 0, None, 26),
            "xss": post("dimas", f"Uji escape di feed: {XSS} {LONG_WORD}", 0, None, 30),
            "mentions": post(
                "budi",
                "Makasih @demo_sari dan @demo_citra, ikut bersih sungai! @tidakada",
                2,
                None,
                40,
            ),
            "noname": post(
                "noname", "Postingan dari akun tanpa nama lengkap.", 0, None, 50
            ),
            "old": post(
                "budi",
                "Postingan lama untuk menguji urutan dan tab Populer.",
                0,
                None,
                24 * 45,
            ),
        }
        # More posts so the list paginates (10 per page)
        for index in range(12):
            post(
                ["sari", "budi", "citra", "dimas"][index % 4],
                f"Catatan harian #{index + 1}: {PARAGRAPH[:90]}",
                index % 3 == 0,
                None,
                60 + index * 6,
            )

        # Likes: "harvest" is popular; Sari reaches the 5-like challenge
        likers = ["budi", "citra", "dimas", "admin", "moderator", "panjang"]
        for name in likers:
            Like.objects.create(post=posts["harvest"], user=u[name])
        for name in ("sari", "citra"):
            Like.objects.create(post=posts["single"], user=u[name])
        Like.objects.create(post=posts["text"], user=u["sari"])
        # Edge: liking your own post (must not count towards challenges)
        Like.objects.create(post=posts["text"], user=u["citra"])
        for name in ("sari", "budi", "citra", "dimas", "admin"):
            Like.objects.create(post=posts["old"], user=u[name])

        def comment(post_key, author, content, parent=None, minutes_ago=30):
            item = Comment.objects.create(
                post=posts[post_key],
                author=u[author],
                content=content,
                parent=parent,
            )
            Comment.objects.filter(pk=item.pk).update(
                created_at=self.now - timedelta(minutes=minutes_ago)
            )
            return item

        root = comment(
            "harvest", "budi", "Keren banget! Pakai kompos apa?", minutes_ago=90
        )
        comment("harvest", "sari", "@demo_budi pakai komposter takakura 😄", root, 80)
        comment("harvest", "citra", "Aku mau coba juga!", root, 70)
        comment("harvest", "dimas", "Ajarin dong kak", root, 60)
        reply = comment(
            "harvest", "sari", "@demo_dimas boleh, nanti aku tulis artikelnya", root, 50
        )
        comment("harvest", "admin", "Mantap, terus berbagi ya!", root, 40)
        comment("harvest", "moderator", "Semangat komunitas! 🌿", minutes_ago=20)
        # Edge: comment at the 500-character maximum, and markup to escape
        comment("harvest", "panjang", ("Komentar panjang. " * 30)[:500], minutes_ago=10)
        comment("text", "dimas", f"Uji escape komentar: {XSS}", minutes_ago=15)
        for name in ("budi", "dimas", "citra"):
            comment("single", name, f"Semangat bersepeda! dari {name}", minutes_ago=120)
            comment("text", name, "Langkah kecil yang keren 👏", minutes_ago=100)

        for name in ("budi", "citra", "dimas"):
            CommentLike.objects.create(comment=root, user=u[name])
        CommentLike.objects.create(comment=reply, user=u["dimas"])
        self.posts = posts
        self.log("Feed posts", Post.objects.filter(author__in=u.values()).count())

    # -------------------------------------------------------------- donations

    def seed_donations(self):
        from apps.donations.models import Campaign, Donation

        C = Campaign.Status
        D = Donation.Status
        now = self.now
        specs = [
            # key, title, target, status, starts, ends (days), image color
            ("trees", "Hutan Kota 1.000 Pohon", "5000000", C.PUBLISHED, -10, 20, GREEN),
            ("river", "Bersihkan Sungai Ciliwung", "2000000", C.PUBLISHED, -5, 3, SKY),
            (
                "bank",
                "Bank Sampah untuk Sekolah",
                "1500000",
                C.PUBLISHED,
                None,
                None,
                None,
            ),
            # Edge: target already exceeded (progress must cap at 100%)
            ("done", "Sumur Resapan Kampung", "500000", C.PUBLISHED, -30, 10, FOREST),
            # Edge: published but ended, published but not started, closed, draft
            (
                "ended",
                "Tanam Mangrove (Selesai)",
                "3000000",
                C.PUBLISHED,
                -60,
                -1,
                BLOSSOM,
            ),
            ("soon", "Kebun Komunitas (Segera)", "2500000", C.PUBLISHED, 5, 40, None),
            ("closed", "Panel Surya Masjid", "8000000", C.CLOSED, -90, -30, None),
            ("draft", "Draf Kampanye Rahasia", "1000000", C.DRAFT, None, None, None),
        ]
        self.campaigns = {}
        for key, title, target, status, starts, ends, color in specs:
            campaign = Campaign(
                title=title,
                slug=f"demo-{key}",
                description=f"{title}. {PARAGRAPH}\n\n{PARAGRAPH}",
                target_amount=Decimal(target),
                status=status,
                starts_at=now + timedelta(days=starts) if starts is not None else None,
                ends_at=now + timedelta(days=ends) if ends is not None else None,
            )
            if color:
                campaign.image = file_of(color, "campaign.png", title[:30])
            campaign.save()
            self.campaigns[key] = campaign

        u = self.users
        admin = u["admin"]

        def donate(
            user,
            key,
            amount,
            status=D.PENDING,
            message="",
            anonymous=False,
            reason="",
            days_ago=1,
        ):
            donation = Donation(
                campaign=self.campaigns[key],
                donor=u[user],
                amount=Decimal(amount),
                message=message,
                is_anonymous=anonymous,
                status=status,
                verified_at=now - timedelta(days=days_ago - 0.5)
                if status != D.PENDING
                else None,
                verified_by=admin if status != D.PENDING else None,
                rejection_reason=reason,
            )
            donation.proof.save(
                "bukti.png",
                file_of(SAND, "bukti.png", "BUKTI", size=(600, 900)),
                save=False,
            )
            donation.save()
            Donation.objects.filter(pk=donation.pk).update(
                created_at=now - timedelta(days=days_ago)
            )
            return donation

        # Donation challenge: Sari reaches Rp100.000, Budi is halfway, Dimas pending
        donate("sari", "trees", "75000", D.APPROVED, "Semoga cepat rindang 🌳")
        donate("sari", "river", "25000", D.APPROVED, anonymous=True)
        donate("budi", "trees", "50000", D.APPROVED, "Untuk bumi yang lebih hijau")
        donate("dimas", "river", "150000", D.PENDING, "Menunggu verifikasi")
        # Edge: rejected with and without a written reason, decimals, tiny amount
        donate(
            "dimas",
            "trees",
            "20000",
            D.REJECTED,
            reason="Nominal pada bukti tidak sama.",
        )
        donate(
            "citra",
            "bank",
            "10000.50",
            D.REJECTED,
            reason="Bukti transfer belum dapat kami verifikasi.",
        )
        donate("citra", "bank", "0.01", D.PENDING, "Uji nominal terkecil")
        donate("panjang", "bank", "125000.75", D.APPROVED, f"Uji escape: {XSS}")
        # Exceed the "done" target
        for name, amount in (
            ("budi", "300000"),
            ("citra", "250000"),
            ("admin", "100000"),
        ):
            donate(name, "done", amount, D.APPROVED, days_ago=15)
        donate("sari", "ended", "100000", D.APPROVED, "Terima kasih!", days_ago=20)
        # Many approved donors for the donor wall (shows the latest 8)
        for index, name in enumerate(
            ["budi", "citra", "dimas", "panjang", "noname", "moderator"]
        ):
            donate(
                name,
                "trees",
                str(10000 * (index + 1)),
                D.APPROVED,
                anonymous=index % 3 == 2,
                days_ago=2 + index,
            )
        self.log("Campaigns", len(self.campaigns))
        self.log("Donations", Donation.objects.filter(donor__in=u.values()).count())

    # --------------------------------------------------------------- helpdesk

    def seed_helpdesk(self):
        from apps.helpdesk.models import Ticket, TicketMessage

        u = self.users
        S, P = Ticket.Status, Ticket.Priority
        specs = [
            ("sari", "Badge tidak muncul di profil", S.OPEN, P.HIGH, None),
            (
                "budi",
                "Donasi saya belum diverifikasi",
                S.IN_PROGRESS,
                P.NORMAL,
                "admin",
            ),
            (
                "citra",
                "Cara mengirim artikel untuk review?",
                S.RESOLVED,
                P.LOW,
                "moderator",
            ),
            ("dimas", "Akun terkunci setelah ganti email", S.CLOSED, P.NORMAL, "admin"),
            ("panjang", f"Uji escape subjek {XSS}"[:200], S.OPEN, P.LOW, None),
        ]
        for requester, subject, status, priority, assignee in specs:
            ticket = Ticket.objects.create(
                requester=u[requester],
                assigned_to=u[assignee] if assignee else None,
                subject=subject,
                description=f"{subject}. {PARAGRAPH}",
                status=status,
                priority=priority,
                closed_at=self.now if status == S.CLOSED else None,
            )
            first = TicketMessage.objects.create(
                ticket=ticket,
                author=u[requester],
                message="Mohon bantuannya, terima kasih.",
            )
            if assignee:
                TicketMessage.objects.create(
                    ticket=ticket,
                    author=u[assignee],
                    message="Halo, kami sedang memeriksanya.",
                    is_admin_response=True,
                    reply_to=first,
                )
        self.log("Tickets", len(specs))

    # -------------------------------------------------------- community goals

    def seed_community_goals(self):
        from apps.challenges.models import CommunityGoal

        for title, goal_type, target, start, end, published in COMMUNITY_GOALS:
            CommunityGoal.objects.create(
                title=title,
                description="Target bersama dari seeder untuk pengujian.",
                goal_type=goal_type,
                target=target,
                start_date=self.today + timedelta(days=start),
                end_date=self.today + timedelta(days=end),
                is_published=published,
            )
        self.log("Community goals", len(COMMUNITY_GOALS))

    # ------------------------------------------------- challenges and badges

    def settle_challenges(self):
        from apps.challenges import services
        from apps.challenges.models import ChallengeParticipation, UserBadge

        demo_users = list(self.users.values())
        for participation in ChallengeParticipation.objects.filter(
            user__in=demo_users
        ).select_related("challenge__badge", "user"):
            services.evaluate(participation)
        # Sari features her first badge; Budi has badges but features none
        first = (
            UserBadge.objects.filter(user=self.users["sari"])
            .order_by("awarded_at")
            .first()
        )
        if first:
            services.set_featured_badge(self.users["sari"], first.pk)
        # Admin owns a badge too, so names in the dashboard show one
        admin_badge, _ = UserBadge.objects.get_or_create(
            user=self.users["admin"], badge=self.badges["Penyemangat"]
        )
        services.set_featured_badge(self.users["admin"], admin_badge.pk)

    # ---------------------------------------------------------- notifications

    def seed_notifications(self):
        from apps.notifications.models import Notification
        from apps.notifications.services import Kind, notify

        u = self.users
        harvest = self.posts["harvest"]
        post_url = f"/feed/{harvest.pk}/"
        for name in ("budi", "citra", "dimas"):
            notify(
                u["sari"],
                Kind.POST_LIKED,
                f"{u[name].display_name} menyukai postinganmu",
                harvest.content[:120],
                url=post_url,
                actor=u[name],
                dedupe_key=f"post:{harvest.pk}",
            )
        notify(
            u["sari"],
            Kind.POST_COMMENTED,
            "Budi Santoso mengomentari postinganmu",
            "Keren banget! Pakai kompos apa?",
            url=post_url,
            actor=u["budi"],
        )
        notify(
            u["budi"],
            Kind.COMMENT_REPLIED,
            "Sari Wulandari membalas komentarmu",
            "@demo_budi pakai komposter takakura 😄",
            url=post_url,
            actor=u["sari"],
        )
        notify(
            u["citra"],
            Kind.ARTICLE_REJECTED,
            "Artikelmu perlu sedikit perubahan",
            "Tolong tambahkan sumber dan langkah keamanan.",
            url="/articles/mine/",
            actor=u["admin"],
        )
        notify(
            u["dimas"],
            Kind.DONATION_REJECTED,
            "Donasimu belum dapat diverifikasi",
            "Nominal pada bukti tidak sama.",
            url="/donations/history/",
        )
        # Admin inbox: things waiting for review
        for name in ("admin", "moderator"):
            notify(
                u[name],
                Kind.ARTICLE_SUBMITTED,
                "Artikel baru menunggu review",
                "“Kebun Hidroponik dari Botol Bekas” oleh Sari Wulandari.",
                url="/articles/browse/?status=PENDING",
                actor=u["sari"],
            )
            notify(
                u[name],
                Kind.DONATION_SUBMITTED,
                "Donasi baru menunggu verifikasi",
                "Rp 150.000 untuk “Bersihkan Sungai Ciliwung”.",
                url="/donations/verification/",
                actor=u["dimas"],
            )
        # Edge: many notifications for one account (bell shows 99+ and paginates)
        for index in range(105):
            Notification.objects.create(
                recipient=u["panjang"],
                kind=Kind.POST_LIKED,
                title=f"Notifikasi uji #{index + 1}",
                message="Untuk menguji badge 99+ dan halaman berpaginasi.",
                url="/feed/",
            )
        # Some already read
        Notification.objects.filter(recipient=u["budi"]).update(read_at=self.now)

    # ------------------------------------------------------------------ report

    def log(self, label, count):
        self.stdout.write(f"  {label:<14} {count}")

    def report(self):
        from apps.challenges.models import ChallengeParticipation, UserBadge
        from apps.notifications.models import Notification

        u = self.users
        completed = ChallengeParticipation.objects.filter(
            user__in=u.values(), completed_at__isnull=False
        ).count()
        self.log("Completions", completed)
        self.log("Badges given", UserBadge.objects.filter(user__in=u.values()).count())
        self.log(
            "Notifications",
            Notification.objects.filter(recipient__in=u.values()).count(),
        )
        self.stdout.write(self.style.SUCCESS("\nDemo data ready."))
        self.stdout.write(f"\nLog in with these usernames, password: {PASSWORD}\n")
        rows = [
            ("admin", "Admin: dashboard, reviews, verification, badges"),
            ("moderator", "Second admin (notified about submissions too)"),
            ("sari", "Power user: featured badge, popular post, completed challenges"),
            ("budi", "Partial progress, broken streak, published article"),
            ("citra", "Rejected article, rejected donation, own-post like"),
            ("dimas", "Pending donation, no badges, many reads"),
            ("noname", "No first/last name (username fallback)"),
            ("panjang", "Very long name, 105 notifications (99+), edge text"),
            ("baru", "Brand-new account with no activity (empty states)"),
            ("nonaktif", "Inactive account (login must fail)"),
        ]
        for username, purpose in rows:
            self.stdout.write(f"  {PREFIX + username:<16} {purpose}")
        self.stdout.write(
            """
UAT checklist
  Feed
    [ ] /feed/ paginates; "Populer" puts "Panen kompos pertama" first
    [ ] Carousel on 3, 10 and 20 photo posts (arrows, dots, counter, swipe)
    [ ] "Disukai oleh ..." opens the likers dialog; comment likes and their likers
    [ ] Long thread collapses to 2 replies; reply to a reply adds @mention
    [ ] 2000-char post, 500-char comment and <script> text render safely
    [ ] As baru: compose with photos (10 max, 10 MB total), see it count
  Challenges
    [ ] Active / upcoming / ended / one-day / draft (draft hidden from users)
    [ ] sari: "7 Hari Tanpa Plastik" completed, badge earned; budi streak 3
    [ ] Tracked goals show auto progress: read, donate, posts, likes, comments
    [ ] As admin: create a challenge with a goal + badge; manage badges
  Badges
    [ ] sari's name shows a badge chip on feed, comments and likers
    [ ] Profile #badges: switch featured badge, hide it, locked badges link out
  Articles
    [ ] As baru: write -> "Kirim untuk review"; admin approves or returns it
    [ ] citra sees the review note on the rejected article and can resubmit
    [ ] Read to the end (20 s) -> "Sudah dibaca"; reading challenge moves
    [ ] Admin status filters with counts; category page (delete the empty one)
  Donations
    [ ] Donor wall hides anonymous names; "Sumur Resapan" capped at 100%
    [ ] Ended / not started / closed campaigns refuse donations; draft hidden
    [ ] Admin verifies dimas' pending donation -> his challenge + notification
    [ ] Rejected donations show the reason in history and detail
  Notifications
    [ ] Bell count, popover, "Tandai semua dibaca", panjang shows 99+
    [ ] A new badge triggers the "Lencana baru" toast once
  Helpdesk
    [ ] Tickets in every status, assigned and unassigned
  Gamification
    [ ] Landing + /challenges/: 3 running community goals with "your share"
        ("5 cerita pertama" already reached; upcoming, ended, hidden not shown)
    [ ] /challenges/demo-likes/ as sari: leaderboard, "You" highlighted, ties
    [ ] Challenge you have not joined: only the "join to see" teaser
    [ ] Profile #impact: articles read, challenges finished, longest streak
    [ ] Admin: Dashboard > Challenges > Community goals (create/edit/delete)
"""
        )
