from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.donations.models import Campaign, Donation


class CampaignPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="donor", email="donor@example.com", password="test-password"
        )
        cls.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="test-password",
            role=User.Role.ADMIN,
        )
        cls.published = Campaign.objects.create(
            title="River cleanup",
            description="Remove litter from the river.",
            target_amount=Decimal("100.00"),
            status=Campaign.Status.PUBLISHED,
        )
        cls.draft = Campaign.objects.create(
            title="Tree nursery",
            description="Grow native tree seedlings.",
            target_amount=Decimal("200.00"),
            status=Campaign.Status.DRAFT,
        )
        cls.closed = Campaign.objects.create(
            title="Closed garden",
            description="The campaign has ended.",
            target_amount=Decimal("300.00"),
            status=Campaign.Status.CLOSED,
        )

    def add_donation(self, campaign, amount, status):
        return Donation.objects.create(
            campaign=campaign,
            donor=self.user,
            amount=Decimal(amount),
            status=status,
        )

    def test_public_campaign_list_shows_published_campaigns_only(self):
        response = self.client.get(reverse("donations:campaign_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.published.title)
        self.assertNotContains(response, self.draft.title)
        self.assertNotContains(response, self.closed.title)

    def test_regular_user_cannot_use_status_filter_to_see_drafts(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("donations:campaign_list"), {"status": Campaign.Status.DRAFT}
        )

        self.assertContains(response, self.published.title)
        self.assertNotContains(response, self.draft.title)

    def test_admin_campaign_list_includes_all_statuses(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("donations:campaign_list"))

        self.assertContains(response, self.published.title)
        self.assertContains(response, self.draft.title)
        self.assertContains(response, self.closed.title)

    def test_campaign_search_matches_title_or_description(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("donations:campaign_list"), {"search": "native tree"}
        )

        self.assertContains(response, self.draft.title)
        self.assertNotContains(response, self.published.title)

    def test_detail_aggregates_approved_donations_only(self):
        self.add_donation(self.published, "40.00", Donation.Status.APPROVED)
        self.add_donation(self.published, "35.00", Donation.Status.PENDING)
        self.add_donation(self.published, "25.00", Donation.Status.REJECTED)

        response = self.client.get(
            reverse("donations:campaign_detail", args=[self.published.slug])
        )

        self.assertEqual(response.status_code, 200)
        campaign = response.context["campaign"]
        self.assertEqual(campaign.approved_total, Decimal("40.00"))
        self.assertEqual(campaign.progress_percent, Decimal("40.0"))
        self.assertContains(response, "Rp 40")
        self.assertContains(response, "Rp 100")

    def test_progress_is_capped_but_actual_approved_total_is_preserved(self):
        self.add_donation(self.published, "125.50", Donation.Status.APPROVED)

        response = self.client.get(
            reverse("donations:campaign_detail", args=[self.published.slug])
        )

        campaign = response.context["campaign"]
        self.assertEqual(campaign.approved_total, Decimal("125.50"))
        self.assertEqual(campaign.progress_percent, Decimal("100"))
        self.assertContains(response, "Rp 125,50")
        self.assertContains(response, 'aria-valuenow="100"')

    def test_unpublished_campaign_detail_is_not_public(self):
        response = self.client.get(
            reverse("donations:campaign_detail", args=[self.draft.slug])
        )

        self.assertEqual(response.status_code, 404)

    def test_admin_can_view_unpublished_campaign_detail(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("donations:campaign_detail", args=[self.draft.slug])
        )

        self.assertEqual(response.status_code, 200)

    def test_campaign_availability_respects_status_and_dates(self):
        now = timezone.now()
        available = Campaign.objects.create(
            title="Available now",
            description="Open campaign.",
            target_amount=Decimal("100.00"),
            status=Campaign.Status.PUBLISHED,
            starts_at=now - timedelta(days=1),
            ends_at=now + timedelta(days=1),
        )
        future = Campaign.objects.create(
            title="Starts later",
            description="Future campaign.",
            target_amount=Decimal("100.00"),
            status=Campaign.Status.PUBLISHED,
            starts_at=now + timedelta(days=1),
        )
        expired = Campaign.objects.create(
            title="Already ended",
            description="Expired campaign.",
            target_amount=Decimal("100.00"),
            status=Campaign.Status.PUBLISHED,
            ends_at=now - timedelta(days=1),
        )

        self.client.force_login(self.admin)
        response = self.client.get(reverse("donations:campaign_list"))
        availability = {
            campaign.title: campaign.accepts_donations
            for campaign in response.context["campaigns"]
        }

        self.assertTrue(availability[available.title])
        self.assertFalse(availability[future.title])
        self.assertFalse(availability[expired.title])
        self.assertFalse(availability[self.closed.title])

    def test_published_campaign_without_dates_is_available(self):
        response = self.client.get(
            reverse("donations:campaign_detail", args=[self.published.slug])
        )

        self.assertTrue(response.context["campaign"].accepts_donations)
