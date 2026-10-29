from io import StringIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.articles.models import Article
from apps.challenges.models import Challenge, ChallengeParticipation, UserBadge
from apps.donations.models import Campaign, Donation
from apps.feeds.models import Post
from apps.notifications.models import Notification


class SeedDemoTests(TestCase):
    def setUp(self):
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        media_settings = override_settings(MEDIA_ROOT=media.name)
        media_settings.enable()
        self.addCleanup(media_settings.disable)

    def seed(self, *args):
        out = StringIO()
        with self.captureOnCommitCallbacks(execute=True):
            call_command("seed_demo", "--force", *args, stdout=out)
        return out.getvalue()

    def test_refuses_without_debug_unless_forced(self):
        with self.assertRaises(CommandError):
            call_command("seed_demo", stdout=StringIO())

    def test_seeds_every_module_and_clears_again(self):
        output = self.seed()
        self.assertIn("Demo data ready.", output)
        users = get_user_model().objects.filter(email__endswith="@seed.selaras.test")
        self.assertEqual(users.count(), 10)
        self.assertFalse(users.get(username="demo_nonaktif").is_active)

        # Completions and badges come from real activity, not hard-coded rows
        sari = users.get(username="demo_sari")
        self.assertTrue(
            ChallengeParticipation.objects.filter(
                user=sari, challenge__slug="demo-checkin", completed_at__isnull=False
            ).exists()
        )
        self.assertTrue(
            ChallengeParticipation.objects.filter(
                user=sari, challenge__slug="demo-donate", completed_at__isnull=False
            ).exists()
        )
        self.assertTrue(UserBadge.objects.filter(user=sari, is_featured=True).exists())
        self.assertFalse(
            ChallengeParticipation.objects.filter(
                user__username="demo_dimas",
                challenge__slug="demo-donate",
                completed_at__isnull=False,
            ).exists()
        )

        # Edge cases are present
        self.assertEqual(
            Post.objects.get(author__username="demo_admin").images.count(), 20
        )
        self.assertTrue(Post.objects.filter(content__regex=r"^.{2000}$").exists())
        self.assertEqual(
            set(
                Article.objects.filter(author__in=users).values_list(
                    "status", flat=True
                )
            ),
            {"DRAFT", "PENDING", "PUBLISHED", "REJECTED"},
        )
        self.assertEqual(
            Challenge.objects.filter(
                slug__startswith="demo-", is_published=False
            ).count(),
            1,
        )
        self.assertTrue(
            Donation.objects.filter(status="REJECTED", rejection_reason__gt="").exists()
        )
        self.assertGreater(
            Notification.objects.filter(recipient__username="demo_panjang").count(), 99
        )

        # Pages render with the seeded data
        self.client.force_login(sari)
        for url in (
            "/feed/?sort=popular",
            "/articles/browse/",
            "/challenges/demo-read/",
            "/donations/campaigns/demo-done/",
            "/accounts/profile/",
            "/notifications/",
        ):
            self.assertEqual(self.client.get(url).status_code, 200, url)

        # Running again does nothing; --clear removes everything it made
        self.assertIn("already exists", self.seed())
        self.seed("--clear")
        self.assertFalse(users.exists())
        self.assertFalse(Campaign.objects.filter(slug__startswith="demo-").exists())
        self.assertFalse(Challenge.objects.filter(slug__startswith="demo-").exists())
