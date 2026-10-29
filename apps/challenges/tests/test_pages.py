from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.challenges.models import (
    Challenge,
    ChallengeParticipation,
    ChallengeProgress,
)


def make_challenge(title, start=-1, end=5, published=True):
    today = timezone.localdate()
    return Challenge.objects.create(
        title=title,
        description=f"About {title}",
        start_date=today + timedelta(days=start),
        end_date=today + timedelta(days=end),
        is_published=published,
    )


class ChallengeStatusTests(TestCase):
    def test_status_by_dates_and_publication(self):
        self.assertEqual(make_challenge("Running").status, "active")
        self.assertEqual(make_challenge("Soon", start=3, end=9).status, "upcoming")
        self.assertEqual(make_challenge("Over", start=-9, end=-2).status, "ended")
        self.assertEqual(make_challenge("Hidden", published=False).status, "draft")

    def test_draft_wins_over_dates(self):
        past = make_challenge("Old draft", start=-9, end=-2, published=False)
        self.assertEqual(past.status, "draft")


class PublicChallengePageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="alya", email="alya@example.com", password="x"
        )
        cls.active = make_challenge("Plastic Free Week")
        cls.upcoming = make_challenge("Bike Month", start=4, end=30)
        cls.ended = make_challenge("Old Cleanup", start=-20, end=-10)
        cls.draft = make_challenge("Secret Draft", published=False)

    def test_list_extends_base_and_is_indonesian(self):
        response = self.client.get(reverse("challenges:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<html lang="id">')
        self.assertContains(response, "Plastic Free Week")
        self.assertContains(response, "Bangun kebiasaan ramah lingkungan")
        self.assertNotContains(response, "Build eco-friendly habits")
        self.assertNotContains(response, "Secret Draft")

    def test_list_shows_result_count(self):
        response = self.client.get(reverse("challenges:list"))
        self.assertEqual(response.context["result_count"], 3)
        self.assertContains(response, "3 challenge")

    def test_status_filters(self):
        url = reverse("challenges:list")
        titles = lambda status: {  # noqa: E731
            c.title
            for c in self.client.get(url, {"status": status}).context["challenges"]
        }
        self.assertEqual(titles("active"), {"Plastic Free Week"})
        self.assertEqual(titles("upcoming"), {"Bike Month"})
        self.assertEqual(titles("ended"), {"Old Cleanup"})

    def test_search_filters_by_title(self):
        response = self.client.get(reverse("challenges:list"), {"search": "bike"})
        self.assertEqual(
            [c.title for c in response.context["challenges"]], ["Bike Month"]
        )

    def test_my_challenges_filter_needs_login(self):
        response = self.client.get(reverse("challenges:list"), {"status": "my"})
        self.assertEqual(response.context["status_filter"], "all")
        self.assertEqual(len(response.context["challenges"]), 3)

    def test_ajax_returns_html_and_count(self):
        response = self.client.get(
            reverse("challenges:list"),
            {"ajax": "1", "status": "ended"},
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertIn("Old Cleanup", data["html"])
        self.assertIn('data-status="ended"', data["html"])

    def test_empty_state_has_reset_button(self):
        response = self.client.get(reverse("challenges:list"), {"search": "zzz"})
        self.assertContains(response, "Challenge nggak ditemukan")
        self.assertContains(response, "btn-reset-filters")

    def test_detail_for_anonymous_prompts_login(self):
        response = self.client.get(
            reverse("challenges:detail", args=[self.active.slug])
        )
        self.assertContains(response, "Masuk untuk gabung")

    def test_draft_detail_is_hidden(self):
        response = self.client.get(reverse("challenges:detail", args=[self.draft.slug]))
        self.assertEqual(response.status_code, 404)

    def test_join_progress_and_leave_flow(self):
        self.client.force_login(self.user)
        self.client.post(reverse("challenges:join", args=[self.active.slug]))
        self.assertTrue(
            ChallengeParticipation.objects.filter(
                user=self.user, challenge=self.active
            ).exists()
        )

        response = self.client.post(
            reverse("challenges:progress", args=[self.active.slug]),
            {"notes": "Carried my own bottle"},
            follow=True,
        )
        self.assertEqual(ChallengeProgress.objects.count(), 1)
        self.assertContains(response, "Carried my own bottle")
        self.assertContains(response, "tersimpan")

        response = self.client.post(
            reverse("challenges:leave", args=[self.active.slug]),
            {"next": reverse("challenges:history")},
            follow=True,
        )
        self.assertFalse(ChallengeParticipation.objects.exists())
        self.assertContains(response, "Kamu keluar dari")

    def test_cannot_join_ended_challenge(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("challenges:join", args=[self.ended.slug]), follow=True
        )
        self.assertFalse(ChallengeParticipation.objects.exists())
        self.assertContains(response, "sudah berakhir")

    def test_history_requires_login(self):
        response = self.client.get(reverse("challenges:history"))
        self.assertEqual(response.status_code, 302)

    def test_history_page_renders_in_indonesian(self):
        ChallengeParticipation.objects.create(user=self.user, challenge=self.active)
        self.client.force_login(self.user)
        response = self.client.get(reverse("challenges:history"))
        self.assertContains(response, "Challenge saya")
        self.assertContains(response, "Berjalan")
        self.assertNotContains(response, "My challenges")

    def test_old_admin_routes_redirect_to_dashboard(self):
        admin = User.objects.create_user(
            username="boss", email="boss@example.com", password="x", role="admin"
        )
        self.client.force_login(admin)
        self.assertRedirects(
            self.client.get(reverse("challenges:create")),
            reverse("dashboard:admin_challenge_create"),
        )
        self.assertRedirects(
            self.client.get(reverse("challenges:update", args=[self.active.slug])),
            reverse("dashboard:admin_challenge_update", args=[self.active.slug]),
        )

    def test_admin_sees_dashboard_shortcut(self):
        admin = User.objects.create_user(
            username="boss", email="boss@example.com", password="x", role="admin"
        )
        self.client.force_login(admin)
        response = self.client.get(reverse("challenges:list"))
        self.assertContains(response, "Kelola challenge")
        response = self.client.get(
            reverse("challenges:detail", args=[self.active.slug])
        )
        self.assertContains(response, "Edit di dashboard")
