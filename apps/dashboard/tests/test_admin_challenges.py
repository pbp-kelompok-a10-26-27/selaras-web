from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.challenges.models import Challenge, ChallengeParticipation


def make_challenge(title, start=-1, end=5, published=True):
    today = timezone.localdate()
    return Challenge.objects.create(
        title=title,
        description=f"About {title}",
        start_date=today + timedelta(days=start),
        end_date=today + timedelta(days=end),
        is_published=published,
    )


class AdminChallengeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="boss", email="boss@example.com", password="x", role="admin"
        )
        cls.member = User.objects.create_user(
            username="alya", email="alya@example.com", password="x"
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_list_is_admin_only(self):
        url = reverse("dashboard:admin_challenge_list")
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_list_renders_with_status_badges(self):
        make_challenge("Plastic Free Week")
        make_challenge("Hidden", published=False)
        response = self.client.get(reverse("dashboard:admin_challenge_list"))
        self.assertContains(response, "Challenge baru")
        self.assertContains(response, 'data-status="active"')
        self.assertContains(response, 'data-status="draft"')

    def test_sidebar_link_is_enabled(self):
        response = self.client.get(reverse("dashboard:admin_challenge_list"))
        self.assertContains(response, 'href="/dashboard/challenges/"')

    def test_filters_and_chips(self):
        make_challenge("Plastic Free Week")
        make_challenge("Hidden", published=False)
        url = reverse("dashboard:admin_challenge_list")

        response = self.client.get(url, {"status": "draft"})
        self.assertEqual([c.title for c in response.context["challenges"]], ["Hidden"])
        self.assertContains(response, "Hapus filter status")

        response = self.client.get(url, {"search": "plastic"})
        self.assertEqual(response.context["pagination"]["count"], 1)
        self.assertContains(response, "Hapus pencarian")

        response = self.client.get(url, {"status": "nope"})
        self.assertEqual(response.context["status_filter"], "all")

    def test_pagination(self):
        for index in range(23):
            make_challenge(f"Challenge {index:02d}")
        url = reverse("dashboard:admin_challenge_list")

        first = self.client.get(url).context
        self.assertEqual(len(first["challenges"]), 10)
        self.assertEqual(first["pagination"]["total_pages"], 3)
        self.assertIsNone(first["pagination"]["prev_url"])
        self.assertIn("page=2", first["pagination"]["next_url"])

        last = self.client.get(url, {"page": 3}).context
        self.assertEqual(len(last["challenges"]), 3)
        self.assertIsNone(last["pagination"]["next_url"])

        # Bad or out-of-range pages never error
        self.assertEqual(self.client.get(url, {"page": "abc"}).status_code, 200)
        self.assertEqual(
            self.client.get(url, {"page": 99}).context["pagination"]["page"], 3
        )

    def test_pager_keeps_filters(self):
        for index in range(12):
            make_challenge(f"Cleanup {index:02d}")
        response = self.client.get(
            reverse("dashboard:admin_challenge_list"), {"search": "cleanup"}
        )
        self.assertIn("search=cleanup", response.context["pagination"]["next_url"])

    def test_create_challenge(self):
        today = timezone.localdate()
        response = self.client.post(
            reverse("dashboard:admin_challenge_create"),
            {
                "title": "Bike Month",
                "description": "Ride instead of drive.",
                "start_date": today,
                "end_date": today + timedelta(days=7),
                "is_published": "on",
            },
            follow=True,
        )
        self.assertContains(
            response, "Challenge \u201cBike Month\u201d berhasil dibuat."
        )
        self.assertTrue(Challenge.objects.get(title="Bike Month").is_published)

    def test_form_rejects_end_before_start(self):
        today = timezone.localdate()
        response = self.client.post(
            reverse("dashboard:admin_challenge_create"),
            {
                "title": "Backwards",
                "description": "x",
                "start_date": today,
                "end_date": today - timedelta(days=1),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "Tanggal selesai tidak boleh sebelum tanggal mulai."
        )
        self.assertFalse(Challenge.objects.exists())

    def test_form_pages_render(self):
        challenge = make_challenge("Plastic Free Week")
        self.assertContains(
            self.client.get(reverse("dashboard:admin_challenge_create")),
            "Challenge baru",
        )
        self.assertContains(
            self.client.get(
                reverse("dashboard:admin_challenge_update", args=[challenge.slug])
            ),
            "Edit challenge: Plastic Free Week",
        )

    def test_update_challenge(self):
        challenge = make_challenge("Plastic Free Week")
        response = self.client.post(
            reverse("dashboard:admin_challenge_update", args=[challenge.slug]),
            {
                "title": "Plastic Free Month",
                "description": challenge.description,
                "start_date": challenge.start_date,
                "end_date": challenge.end_date,
            },
            follow=True,
        )
        self.assertContains(response, "berhasil diperbarui.")
        challenge.refresh_from_db()
        self.assertEqual(challenge.title, "Plastic Free Month")
        self.assertFalse(challenge.is_published)

    def test_delete_without_participants(self):
        challenge = make_challenge("Delete me")
        response = self.client.post(
            reverse("dashboard:admin_challenge_delete", args=[challenge.slug]),
            follow=True,
        )
        self.assertFalse(Challenge.objects.filter(pk=challenge.pk).exists())
        self.assertContains(response, "berhasil dihapus.")

    def test_delete_blocked_with_participants(self):
        challenge = make_challenge("Popular")
        ChallengeParticipation.objects.create(user=self.member, challenge=challenge)
        response = self.client.post(
            reverse("dashboard:admin_challenge_delete", args=[challenge.slug]),
            follow=True,
        )
        self.assertTrue(Challenge.objects.filter(pk=challenge.pk).exists())
        self.assertContains(response, "tidak bisa dihapus karena sudah punya 1 peserta")

    def test_delete_requires_post(self):
        challenge = make_challenge("Safe")
        response = self.client.get(
            reverse("dashboard:admin_challenge_delete", args=[challenge.slug])
        )
        self.assertEqual(response.status_code, 405)
        self.assertTrue(Challenge.objects.filter(pk=challenge.pk).exists())
