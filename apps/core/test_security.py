"""Pengujian keamanan dasar berdasarkan OWASP Top 10 (2021).

Setiap kelas mewakili satu kategori. Tes ini menyerang view sungguhan dengan
akun berbeda, payload injeksi, dan unggahan palsu.
"""

import re
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.articles.models import Article, ArticleCategory
from apps.challenges.models import Badge, Challenge, ChallengeParticipation, UserBadge
from apps.donations.models import Campaign, Donation
from apps.feeds.models import Comment, Post
from apps.helpdesk.models import Ticket
from apps.notifications.services import Kind, notify

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
XSS = '<script>alert("xss")</script>'
SQLI = ["' OR '1'='1", "'; DROP TABLE feeds_post; --", '" OR ""="', "1 UNION SELECT 1"]


class SecurityTestCase(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "Rahasia-123!"
        )
        self.bob = User.objects.create_user("bob", "bob@example.com", "Rahasia-123!")
        self.admin = User.objects.create_user(
            "admin", "admin@example.com", "Rahasia-123!", role="admin"
        )
        self.campaign = Campaign.objects.create(
            title="Hutan",
            description="x",
            target_amount=Decimal("1000000"),
            status=Campaign.Status.PUBLISHED,
        )
        self.category = ArticleCategory.objects.create(name="Keamanan")

    def donation(self, donor, **extra):
        donation = Donation(campaign=self.campaign, donor=donor, amount=Decimal("1000"))
        donation.proof.save(
            "bukti.png", SimpleUploadedFile("bukti.png", PNG), save=False
        )
        for key, value in extra.items():
            setattr(donation, key, value)
        donation.save()
        return donation


class A01BrokenAccessControlTests(SecurityTestCase):
    def test_donations_are_private_to_their_donor(self):
        mine = self.donation(self.alice)
        self.client.force_login(self.bob)
        for name in ("donations:detail", "donations:edit", "donations:proof"):
            response = self.client.get(reverse(name, args=[mine.pk]))
            self.assertEqual(response.status_code, 404, name)
        response = self.client.post(
            reverse("donations:edit", args=[mine.pk]), {"amount": "1"}
        )
        self.assertEqual(response.status_code, 404)
        mine.refresh_from_db()
        self.assertEqual(mine.amount, Decimal("1000"))

    def test_donation_proofs_are_not_publicly_served(self):
        mine = self.donation(self.alice)
        path = Path(mine.proof.path)
        # Disimpan di luar MEDIA_ROOT dengan nama acak
        self.assertFalse(str(path).startswith(str(settings.MEDIA_ROOT)))
        self.assertNotIn("bukti", path.name)
        self.assertRegex(path.stem, r"^[0-9a-f]{32}$")
        self.client.logout()
        self.assertEqual(self.client.get(f"/media/{mine.proof.name}").status_code, 404)

    def test_non_admins_cannot_reach_admin_actions(self):
        donation = self.donation(self.alice)
        article = Article.objects.create(
            title="Kiriman",
            content="x",
            category=self.category,
            author=self.alice,
            status=Article.Status.PENDING,
        )
        badge = Badge.objects.create(name="Rahasia")
        self.client.force_login(self.bob)
        gets = [
            reverse("dashboard:home"),
            reverse("dashboard:admin_challenge_list"),
            reverse("dashboard:admin_badge_list"),
            reverse("dashboard:admin_goal_list"),
            reverse("dashboard:admin_ticket_list"),
            reverse("donations:verification_queue"),
            reverse("donations:verify", args=[donation.pk]),
            reverse("donations:admin_proof", args=[donation.pk]),
            reverse("donations:campaign_create"),
            reverse("articles:categories"),
        ]
        for url in gets:
            self.assertEqual(self.client.get(url).status_code, 403, url)

        self.client.post(
            reverse("donations:verify", args=[donation.pk]), {"status": "APPROVED"}
        )
        self.client.post(
            reverse("articles:review", args=[article.slug]), {"decision": "approve"}
        )
        self.client.post(reverse("dashboard:admin_badge_delete", args=[badge.slug]))
        donation.refresh_from_db()
        article.refresh_from_db()
        self.assertEqual(donation.status, Donation.Status.PENDING)
        self.assertEqual(article.status, Article.Status.PENDING)
        self.assertTrue(Badge.objects.filter(pk=badge.pk).exists())

    def test_anonymous_users_are_sent_to_login(self):
        for url in (
            reverse("accounts:profile"),
            reverse("donations:history"),
            reverse("notifications:list"),
            reverse("articles:html-create"),
            reverse("dashboard:home"),
        ):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, url)
            self.assertIn("/accounts/login/", response["Location"])

    def test_users_cannot_change_other_peoples_content(self):
        post = Post.objects.create(author=self.alice, content="punya alice")
        comment = Comment.objects.create(post=post, author=self.alice, content="hai")
        self.client.force_login(self.bob)

        self.assertEqual(
            self.client.post(reverse("feeds:delete", args=[post.pk])).status_code, 403
        )
        self.assertEqual(
            self.client.post(reverse("feeds:moderate", args=[post.pk])).status_code, 403
        )
        self.assertEqual(
            self.client.post(
                reverse("feeds:comment_delete", args=[comment.pk])
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.delete(f"/api/v1/posts/{post.pk}").status_code, 403
        )
        self.assertEqual(
            self.client.patch(
                f"/api/v1/comments/{comment.pk}",
                '{"content": "diubah"}',
                content_type="application/json",
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.delete(f"/api/v1/admin/posts/{post.pk}").status_code, 403
        )
        self.assertTrue(Post.objects.filter(pk=post.pk).exists())
        comment.refresh_from_db()
        self.assertEqual(comment.content, "hai")

    def test_unpublished_articles_stay_with_their_writer(self):
        draft = Article.objects.create(
            title="Draf alice", content="x", category=self.category, author=self.alice
        )
        self.client.force_login(self.bob)
        self.assertEqual(
            self.client.get(
                reverse("articles:html-detail", args=[draft.slug])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("articles:html-update", args=[draft.slug])
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse("articles:html-delete", args=[draft.slug])
            ).status_code,
            403,
        )
        self.assertTrue(Article.objects.filter(pk=draft.pk).exists())

    def test_users_cannot_publish_or_mark_unpublished_reads(self):
        self.client.force_login(self.bob)
        self.client.post(
            reverse("articles:html-create"),
            {
                "title": "Langsung terbit?",
                "content": "x",
                "category": self.category.pk,
                "status": "PUBLISHED",
            },
        )
        self.assertEqual(
            Article.objects.get(title="Langsung terbit?").status, Article.Status.PENDING
        )
        draft = Article.objects.create(
            title="Draf", content="x", category=self.category, author=self.admin
        )
        self.assertEqual(
            self.client.post(
                reverse("articles:mark-read", args=[draft.slug])
            ).status_code,
            404,
        )

    def test_helpdesk_tickets_and_notifications_are_private(self):
        ticket = Ticket.objects.create(
            requester=self.alice, subject="Akun", description="x"
        )
        note = notify(self.alice, Kind.POST_LIKED, "Halo alice")
        self.client.force_login(self.bob)
        self.assertIn(
            self.client.get(
                reverse("helpdesk:ticket_detail", args=[ticket.pk])
            ).status_code,
            (403, 404),
        )
        self.assertEqual(
            self.client.get(reverse("notifications:open", args=[note.pk])).status_code,
            404,
        )
        note.refresh_from_db()
        self.assertIsNone(note.read_at)

    def test_cannot_feature_someone_elses_badge(self):
        badge = Badge.objects.create(name="Punya alice")
        owned = UserBadge.objects.create(user=self.alice, badge=badge)
        self.client.force_login(self.bob)
        self.client.post(reverse("accounts:featured_badge"), {"user_badge": owned.pk})
        owned.refresh_from_db()
        self.assertFalse(owned.is_featured)

    def test_open_redirects_are_blocked(self):
        today = timezone.localdate()
        challenge = Challenge.objects.create(
            title="Uji",
            description="x",
            start_date=today,
            end_date=today + timedelta(days=3),
            is_published=True,
        )
        ChallengeParticipation.objects.create(challenge=challenge, user=self.bob)
        self.client.force_login(self.bob)
        response = self.client.post(
            reverse("challenges:leave", args=[challenge.slug]),
            {"next": "https://evil.example/phish"},
        )
        self.assertNotIn("evil.example", response["Location"])

        note = notify(self.bob, Kind.POST_LIKED, "x", url="//evil.example/")
        response = self.client.get(reverse("notifications:open", args=[note.pk]))
        self.assertNotIn("evil.example", response["Location"])

        self.client.logout()
        response = self.client.post(
            reverse("accounts:login") + "?next=https://evil.example/",
            {"username": "bob", "password": "Rahasia-123!"},
        )
        self.assertNotIn("evil.example", response["Location"])


class A02CryptographicFailuresTests(SecurityTestCase):
    def test_passwords_are_hashed_and_never_shown(self):
        self.assertTrue(self.alice.password.startswith(("pbkdf2_", "argon2", "bcrypt")))
        self.assertNotIn("Rahasia-123!", self.alice.password)
        self.client.force_login(self.alice)
        self.assertNotContains(
            self.client.get(reverse("accounts:profile")), self.alice.password
        )

    def test_session_and_csrf_cookies_are_hardened(self):
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, "Lax")
        response = self.client.post(
            reverse("accounts:login"), {"username": "alice", "password": "Rahasia-123!"}
        )
        session = response.cookies[settings.SESSION_COOKIE_NAME]
        self.assertTrue(session["httponly"])

    def test_production_settings_refuse_weak_secrets(self):
        loaded = _load_production_settings({"SECRET_KEY": "k" * 60})
        self.assertFalse(loaded["DEBUG"])
        self.assertTrue(loaded["SESSION_COOKIE_SECURE"])
        self.assertTrue(loaded["CSRF_COOKIE_SECURE"])
        self.assertTrue(loaded["SECURE_SSL_REDIRECT"])
        self.assertGreater(loaded["SECURE_HSTS_SECONDS"], 0)
        whitenoise = "whitenoise.middleware.WhiteNoiseMiddleware"
        self.assertIn(whitenoise, loaded["MIDDLEWARE"])
        with self.assertRaises(ImproperlyConfigured):
            _load_production_settings({"SECRET_KEY": "pendek"})

    def test_production_uses_postgres_when_pws_database_is_set(self):
        loaded = _load_production_settings(
            {
                "SECRET_KEY": "k" * 60,
                "DB_HOST": "db.example",
                "DB_NAME": "selaras",
                "SCHEMA": "tugas_kelompok",
            }
        )
        database = loaded["DATABASES"]["default"]
        self.assertEqual(database["ENGINE"], "django.db.backends.postgresql")
        self.assertIn("search_path=tugas_kelompok", database["OPTIONS"]["options"])


def _load_production_settings(env):
    """Muat config/settings/production.py dengan environment tertentu."""
    import importlib
    import sys
    from unittest import mock

    keys = ("SECRET_KEY", "DB_HOST", "DB_NAME", "SCHEMA", "SECURE_SSL_REDIRECT")
    clean = {key: "" for key in keys}
    with mock.patch.dict("os.environ", {**clean, **env}):
        for name in ("config.settings.production", "config.settings.base"):
            sys.modules.pop(name, None)
        module = importlib.import_module("config.settings.production")
        values = {name: getattr(module, name) for name in dir(module) if name.isupper()}
        values["MIDDLEWARE"] = list(values["MIDDLEWARE"])
    for name in ("config.settings.production", "config.settings.base"):
        sys.modules.pop(name, None)
    return values


class A03InjectionTests(SecurityTestCase):
    def test_sql_injection_in_search_parameters_is_harmless(self):
        Post.objects.create(author=self.alice, content="aman")
        self.client.force_login(self.admin)
        for payload in SQLI:
            for url, param in (
                (reverse("articles:html-list"), "search"),
                (reverse("challenges:list"), "search"),
                (reverse("donations:campaign_list"), "search"),
                ("/api/v1/admin/posts", "q"),
            ):
                response = self.client.get(url, {param: payload})
                self.assertIn(response.status_code, (200, 400, 422), (url, payload))
            response = self.client.get("/api/v1/admin/posts", {"q": payload})
            self.assertEqual(response.json()["data"], [])
        self.assertEqual(Post.objects.count(), 1)

    def test_user_content_is_escaped_everywhere(self):
        post = Post.objects.create(author=self.alice, content=f"halo {XSS} @bob")
        Comment.objects.create(post=post, author=self.bob, content=XSS)
        Article.objects.create(
            title=XSS,
            summary=XSS,
            content=XSS,
            category=self.category,
            author=self.admin,
            status=Article.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        self.donation(self.bob, message=XSS, status=Donation.Status.APPROVED)
        notify(self.alice, Kind.POST_COMMENTED, XSS, XSS)
        Ticket.objects.create(requester=self.alice, subject=XSS, description=XSS)
        get_user_model().objects.filter(pk=self.bob.pk).update(first_name=XSS)

        self.client.force_login(self.alice)
        pages = [
            reverse("feeds:list"),
            reverse("feeds:detail", args=[post.pk]),
            reverse("articles:html-list"),
            reverse("donations:campaign_detail", args=[self.campaign.slug]),
            reverse("notifications:list"),
        ]
        for url in pages:
            body = self.client.get(url).content.decode()
            self.assertNotIn(XSS, body, url)
        self.assertIn(
            "&lt;script&gt;", self.client.get(reverse("feeds:list")).content.decode()
        )

    def test_json_endpoints_do_not_reflect_raw_html_as_html(self):
        self.client.force_login(self.alice)
        response = self.client.get(reverse("notifications:feed"))
        self.assertEqual(response["Content-Type"], "application/json")


class A04InsecureDesignTests(SecurityTestCase):
    def test_business_rules_cannot_be_bypassed(self):
        self.client.force_login(self.alice)
        for amount in ("-5000", "0", "abc"):
            self.client.post(
                reverse("donations:donate", args=[self.campaign.slug]),
                {"amount": amount, "proof": SimpleUploadedFile("b.png", PNG)},
            )
        self.assertFalse(Donation.objects.exists())

        # Donasi yang belum diverifikasi tidak menambah progres kampanye
        self.donation(self.alice, amount=Decimal("999999"))
        response = self.client.get(
            reverse("donations:campaign_detail", args=[self.campaign.slug])
        )
        self.assertEqual(response.context["campaign"].approved_total, Decimal("0"))

    def test_feed_writes_are_rate_limited(self):
        self.client.force_login(self.alice)
        post = Post.objects.create(author=self.bob, content="x")
        statuses = {
            self.client.post(f"/api/v1/posts/{post.pk}/like").status_code
            for _ in range(65)
        }
        self.assertIn(429, statuses)


class A05SecurityMisconfigurationTests(SecurityTestCase):
    def test_security_headers_are_sent(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["Referrer-Policy"], "same-origin")
        self.assertEqual(response["Cross-Origin-Opener-Policy"], "same-origin")

    def test_errors_do_not_leak_internals(self):
        self.assertFalse(settings.DEBUG)
        response = self.client.get("/halaman-yang-tidak-ada/")
        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, "Traceback", status_code=404)
        self.assertNotContains(response, "urlpatterns", status_code=404)

    def test_no_html_comments_leak_to_the_browser(self):
        self.client.force_login(self.alice)
        for url in (reverse("home"), reverse("accounts:login"), reverse("feeds:list")):
            if url == reverse("accounts:login"):
                self.client.logout()
            body = self.client.get(url).content.decode()
            self.assertIsNone(re.search(r"<!--(?!\[if)", body), url)


class A06VulnerableComponentsTests(TestCase):
    def test_external_scripts_are_pinned_and_integrity_checked(self):
        templates = list(Path(settings.BASE_DIR, "templates").rglob("*.html")) + list(
            Path(settings.BASE_DIR, "apps").rglob("*.html")
        )
        for template in templates:
            source = template.read_text(encoding="utf-8")
            for tag in re.findall(r"<script[^>]+src=\"https?://[^\"]+\"[^>]*>", source):
                self.assertIn("integrity=", tag, template)
                self.assertRegex(tag, r"@\d+\.\d+\.\d+/", template)
            self.assertNotIn("mcp.figma.com", source, template)


class A07AuthenticationFailuresTests(SecurityTestCase):
    def test_weak_passwords_are_rejected_at_signup(self):
        for password in ("12345678", "password", "bobby"):
            self.client.post(
                reverse("accounts:register"),
                {
                    "username": "baru",
                    "email": "baru@example.com",
                    "password1": password,
                    "password2": password,
                },
            )
        self.assertFalse(get_user_model().objects.filter(username="baru").exists())

    def test_login_is_locked_after_repeated_failures(self):
        url = reverse("accounts:login")
        with self.assertLogs("apps.accounts.views", level="WARNING") as logs:
            for _ in range(5):
                self.client.post(url, {"username": "alice", "password": "salah"})
            blocked = self.client.post(
                url, {"username": "alice", "password": "Rahasia-123!"}
            )
        self.assertEqual(blocked.status_code, 429)
        self.assertContains(blocked, "Terlalu banyak percobaan", status_code=429)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertTrue(any("Login gagal" in line for line in logs.output))
        self.assertTrue(all("salah" not in line for line in logs.output))

    def test_logout_requires_post_and_password_reset_does_not_reveal_accounts(self):
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        self.client.logout()
        known = self.client.post(
            reverse("accounts:password_reset"), {"email": "alice@example.com"}
        )
        unknown = self.client.post(
            reverse("accounts:password_reset"), {"email": "nobody@example.com"}
        )
        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(known["Location"], unknown["Location"])

    def test_csrf_is_enforced(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.alice)
        post = Post.objects.create(author=self.bob, content="x")
        self.assertEqual(
            client.post(
                reverse("feeds:like", args=[post.pk]), {"action": "like"}
            ).status_code,
            403,
        )
        self.assertEqual(
            client.post(reverse("accounts:featured_badge"), {}).status_code, 403
        )


class A08IntegrityFailuresTests(SecurityTestCase):
    def test_uploads_are_checked_by_content_not_name(self):
        self.client.force_login(self.alice)
        fake = SimpleUploadedFile(
            "foto.png", b"<?php system($_GET['c']); ?>", content_type="image/png"
        )
        response = self.client.post(
            reverse("feeds:create"), {"content": "x", "images": fake}
        )
        self.assertEqual(response.status_code, 422)
        self.assertFalse(Post.objects.exists())

        html = SimpleUploadedFile(
            "bukti.pdf",
            b"<html><script>alert(1)</script>",
            content_type="application/pdf",
        )
        self.client.post(
            reverse("donations:donate", args=[self.campaign.slug]),
            {"amount": "1000", "proof": html},
        )
        self.assertFalse(Donation.objects.exists())

        avatar = SimpleUploadedFile(
            "a.gif", b"GIF89a<script>", content_type="image/gif"
        )
        response = self.client.post(
            reverse("accounts:avatar_upload"), {"avatar": avatar}
        )
        self.assertIn(response.status_code, (200, 400))

    def test_uploaded_names_are_randomised(self):
        self.client.force_login(self.alice)
        image = SimpleUploadedFile(
            "../../etc/passwd.png", PNG, content_type="image/png"
        )
        self.client.post(reverse("feeds:create"), {"content": "x", "images": image})
        name = Post.objects.get().images.get().image.name
        self.assertNotIn("..", name)
        self.assertNotIn("passwd", name)


class A09LoggingTests(SecurityTestCase):
    def test_failed_logins_are_logged_without_secrets(self):
        with self.assertLogs("apps.accounts.views", level="WARNING") as logs:
            self.client.post(
                reverse("accounts:login"), {"username": "alice", "password": "tebakan"}
            )
        self.assertIn("alice", logs.output[0])
        self.assertNotIn("tebakan", logs.output[0])


class A10SsrfTests(SecurityTestCase):
    def test_weather_lookup_only_calls_its_fixed_host(self):
        from unittest import mock

        from apps.challenges import weather

        for lat, lon in (
            ("http://169.254.169.254", "0"),
            ("1&x=1", "2"),
            ("nan", "nan"),
            ("1000", "1000"),
        ):
            with mock.patch.object(
                weather.urllib.request, "urlopen", side_effect=OSError
            ) as opened:
                data = weather.get_current_weather_suggestion(lat=lat, lon=lon)
            request = opened.call_args[0][0]
            self.assertTrue(request.full_url.startswith("https://api.open-meteo.com/"))
            self.assertNotIn("169.254", request.full_url)
            self.assertNotIn("&x=", request.full_url)
            self.assertFalse(data["is_custom_location"])

    def test_helpdesk_image_links_are_never_fetched_by_the_server(self):
        from unittest import mock

        self.client.force_login(self.alice)
        with mock.patch("urllib.request.urlopen") as opened:
            self.client.post(
                reverse("helpdesk:ticket_create_api"),
                {
                    "subject": "Gambar",
                    "description": "x",
                    "priority": "low",
                    "image_links": "http://127.0.0.1:8000/admin/",
                },
            )
        opened.assert_not_called()
