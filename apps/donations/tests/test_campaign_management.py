from datetime import datetime
from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.donations.models import Campaign


class CampaignManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="test-password",
            role=User.Role.ADMIN,
        )
        cls.user = User.objects.create_user(
            username="member", email="member@example.com", password="test-password"
        )

    def campaign_data(self, **overrides):
        data = {
            "title": "River cleanup",
            "description": "Remove litter from the river bank.",
            "target_amount": "1000.00",
            "status": Campaign.Status.DRAFT,
            "starts_at": "2030-10-01T10:00",
            "ends_at": "2030-10-31T10:00",
        }
        data.update(overrides)
        return data

    def campaign_datetime(self, year, month, day, hour, minute):
        return datetime(
            year,
            month,
            day,
            hour,
            minute,
            tzinfo=timezone.get_current_timezone(),
        )

    def create_campaign(self, **overrides):
        fields = {
            "title": "Existing campaign",
            "description": "Existing campaign description.",
            "target_amount": Decimal("500.00"),
            "status": Campaign.Status.DRAFT,
        }
        fields.update(overrides)
        return Campaign.objects.create(**fields)

    def test_anonymous_users_are_redirected_from_create_and_edit(self):
        campaign = self.create_campaign()

        for url in (
            reverse("donations:campaign_create"),
            reverse("donations:campaign_update", args=[campaign.slug]),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(
                    response["Location"].startswith(reverse("accounts:login"))
                )

    def test_regular_user_is_denied_create_and_edit_get_and_post(self):
        campaign = self.create_campaign()
        self.client.force_login(self.user)
        requests = (
            ("get", reverse("donations:campaign_create"), None),
            ("post", reverse("donations:campaign_create"), self.campaign_data()),
            ("get", reverse("donations:campaign_update", args=[campaign.slug]), None),
            (
                "post",
                reverse("donations:campaign_update", args=[campaign.slug]),
                self.campaign_data(title="Unauthorized change"),
            ),
        )

        for method, url, data in requests:
            with self.subTest(method=method, url=url):
                response = (
                    getattr(self.client, method)(url, data)
                    if data
                    else getattr(self.client, method)(url)
                )
                self.assertEqual(response.status_code, 403)

        campaign.refresh_from_db()
        self.assertEqual(campaign.title, "Existing campaign")
        self.assertEqual(Campaign.objects.count(), 1)

    def test_admin_can_open_create_and_edit_forms_in_dashboard_layout(self):
        campaign = self.create_campaign(
            starts_at=self.campaign_datetime(2030, 10, 1, 10, 0)
        )
        self.client.force_login(self.admin)

        create_response = self.client.get(reverse("donations:campaign_create"))
        edit_response = self.client.get(
            reverse("donations:campaign_update", args=[campaign.slug])
        )

        self.assertEqual(create_response.status_code, 200)
        self.assertTemplateUsed(create_response, "dashboard/base.html")
        self.assertTemplateUsed(create_response, "donations/admin/campaign_form.html")
        self.assertEqual(edit_response.status_code, 200)
        self.assertContains(edit_response, 'value="2030-10-01T10:00"')
        self.assertContains(create_response, 'name="csrfmiddlewaretoken"')

    def test_admin_can_create_campaign_with_valid_fields_and_status(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("donations:campaign_create"),
            self.campaign_data(status=Campaign.Status.PUBLISHED),
        )

        campaign = Campaign.objects.get()
        self.assertRedirects(
            response,
            reverse("donations:campaign_detail", args=[campaign.slug]),
        )
        self.assertEqual(campaign.title, "River cleanup")
        self.assertEqual(campaign.description, "Remove litter from the river bank.")
        self.assertEqual(campaign.target_amount, Decimal("1000.00"))
        self.assertEqual(campaign.status, Campaign.Status.PUBLISHED)
        self.assertIsNotNone(campaign.starts_at)
        self.assertIsNotNone(campaign.ends_at)

    def test_admin_can_edit_campaign_and_existing_slug_is_preserved(self):
        campaign = self.create_campaign(
            starts_at=self.campaign_datetime(2030, 10, 1, 10, 0),
            ends_at=self.campaign_datetime(2030, 10, 31, 10, 0),
        )
        original_slug = campaign.slug
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("donations:campaign_update", args=[campaign.slug]),
            self.campaign_data(
                title="A refreshed river cleanup",
                description="Updated campaign details.",
                target_amount="2500.50",
                status=Campaign.Status.PUBLISHED,
                starts_at="2031-01-02T09:30",
                ends_at="2031-02-03T16:45",
            ),
        )

        campaign.refresh_from_db()
        self.assertRedirects(
            response,
            reverse("donations:campaign_detail", args=[original_slug]),
        )
        self.assertEqual(campaign.slug, original_slug)
        self.assertEqual(campaign.title, "A refreshed river cleanup")
        self.assertEqual(campaign.description, "Updated campaign details.")
        self.assertEqual(campaign.target_amount, Decimal("2500.50"))
        self.assertEqual(campaign.status, Campaign.Status.PUBLISHED)
        self.assertEqual(timezone.localtime(campaign.starts_at).hour, 9)
        self.assertEqual(campaign.ends_at.minute, 45)

    def test_create_rejects_nonpositive_target_and_invalid_date_range(self):
        self.client.force_login(self.admin)
        invalid_submissions = (
            self.campaign_data(target_amount="0"),
            self.campaign_data(target_amount="-1"),
            self.campaign_data(
                starts_at="2030-10-31T10:00", ends_at="2030-10-01T10:00"
            ),
        )

        for data in invalid_submissions:
            with self.subTest(data=data):
                response = self.client.post(reverse("donations:campaign_create"), data)
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.context["form"].is_valid())
                self.assertEqual(Campaign.objects.count(), 0)

    def test_edit_rejects_invalid_target_and_date_range_without_saving(self):
        campaign = self.create_campaign(
            starts_at=self.campaign_datetime(2030, 10, 1, 10, 0),
            ends_at=self.campaign_datetime(2030, 10, 31, 10, 0),
        )
        original_title = campaign.title
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("donations:campaign_update", args=[campaign.slug]),
            self.campaign_data(
                title="Should not be saved",
                target_amount="0",
                starts_at="2030-10-31T10:00",
                ends_at="2030-10-01T10:00",
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("target_amount", response.context["form"].errors)
        self.assertIn("ends_at", response.context["form"].errors)
        campaign.refresh_from_db()
        self.assertEqual(campaign.title, original_title)

    def test_duplicate_title_slug_collision_uses_next_free_suffix(self):
        Campaign.objects.create(
            title="Forest cleanup",
            description="First campaign.",
            target_amount=Decimal("100.00"),
            status=Campaign.Status.DRAFT,
        )
        Campaign.objects.create(
            title="Reserved slug",
            slug="forest-cleanup-2",
            description="Occupies the second candidate slug.",
            target_amount=Decimal("100.00"),
            status=Campaign.Status.DRAFT,
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("donations:campaign_create"),
            self.campaign_data(title="Forest cleanup"),
        )

        created = Campaign.objects.get(title="Forest cleanup", slug="forest-cleanup-3")
        self.assertRedirects(
            response,
            reverse("donations:campaign_detail", args=[created.slug]),
        )

    def test_campaign_create_post_requires_csrf(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)

        response = csrf_client.post(
            reverse("donations:campaign_create"), self.campaign_data()
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Campaign.objects.count(), 0)
