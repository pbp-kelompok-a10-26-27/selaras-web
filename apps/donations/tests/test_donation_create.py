from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.donations.models import Campaign, Donation


class DonationCreateViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="donor", email="donor@example.com", password="test-password"
        )
        cls.campaign = Campaign.objects.create(
            title="River cleanup",
            description="Remove litter from the river.",
            target_amount=Decimal("1000.00"),
            status=Campaign.Status.PUBLISHED,
        )

    def setUp(self):
        test_storages = {
            **settings.STORAGES,
            "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        }
        media_settings = override_settings(STORAGES=test_storages)
        media_settings.enable()
        self.addCleanup(media_settings.disable)
        self.client.force_login(self.user)

    def donation_url(self, campaign=None):
        campaign = campaign or self.campaign
        return reverse("donations:donate", args=[campaign.slug])

    def proof_upload(self):
        return SimpleUploadedFile(
            "transfer.pdf",
            b"%PDF-1.7 proof contents",
            content_type="application/pdf",
        )

    def test_anonymous_user_is_redirected_to_login(self):
        self.client.logout()

        response = self.client.get(self.donation_url())

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={self.donation_url()}",
            fetch_redirect_response=False,
        )

    def test_get_renders_donation_form_for_available_campaign(self):
        response = self.client.get(self.donation_url())

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "donations/donation_form.html")
        self.assertContains(response, 'enctype="multipart/form-data"')

    def test_valid_post_saves_current_user_and_model_default_status(self):
        response = self.client.post(
            self.donation_url(),
            {
                "amount": "250.00",
                "proof": self.proof_upload(),
                "donor": "attacker-controlled-value",
                "status": Donation.Status.APPROVED,
            },
            follow=True,
        )

        self.assertRedirects(
            response,
            reverse("donations:campaign_detail", args=[self.campaign.slug]),
        )
        donation = Donation.objects.get()
        self.assertEqual(donation.amount, Decimal("250.00"))
        self.assertEqual(donation.campaign, self.campaign)
        self.assertEqual(donation.donor, self.user)
        self.assertEqual(donation.status, Donation.Status.PENDING)
        self.assertTrue(donation.proof.name.startswith("donations/"))
        self.assertContains(response, "menunggu verifikasi admin")

    def test_invalid_amount_or_missing_proof_does_not_create_donation(self):
        response = self.client.post(self.donation_url(), {"amount": "0"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("amount", response.context["form"].errors)
        self.assertIn("proof", response.context["form"].errors)
        self.assertEqual(Donation.objects.count(), 0)

    def test_unavailable_campaign_post_redirects_with_message_without_saving(self):
        now = timezone.now()
        unavailable_campaigns = (
            Campaign.objects.create(
                title="Future campaign",
                description="Not started yet.",
                target_amount=Decimal("100.00"),
                status=Campaign.Status.PUBLISHED,
                starts_at=now + timedelta(days=1),
            ),
            Campaign.objects.create(
                title="Expired campaign",
                description="Already ended.",
                target_amount=Decimal("100.00"),
                status=Campaign.Status.PUBLISHED,
                ends_at=now - timedelta(days=1),
            ),
        )

        for campaign in unavailable_campaigns:
            with self.subTest(campaign=campaign.title):
                response = self.client.post(
                    self.donation_url(campaign),
                    {"amount": "250.00", "proof": self.proof_upload()},
                    follow=True,
                )

                self.assertRedirects(
                    response,
                    reverse("donations:campaign_detail", args=[campaign.slug]),
                )
                self.assertContains(response, "tidak menerima donasi")
                self.assertFalse(Donation.objects.filter(campaign=campaign).exists())

    def test_closed_campaign_is_not_available_to_regular_user(self):
        closed = Campaign.objects.create(
            title="Closed campaign",
            description="Closed by admin.",
            target_amount=Decimal("100.00"),
            status=Campaign.Status.CLOSED,
        )

        response = self.client.post(
            self.donation_url(closed),
            {"amount": "250.00", "proof": self.proof_upload()},
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Donation.objects.filter(campaign=closed).exists())

    def test_post_rechecks_availability_after_form_was_opened(self):
        self.assertEqual(self.client.get(self.donation_url()).status_code, 200)
        Campaign.objects.filter(pk=self.campaign.pk).update(
            ends_at=timezone.now() - timedelta(seconds=1)
        )

        response = self.client.post(
            self.donation_url(),
            {"amount": "250.00", "proof": self.proof_upload()},
            follow=True,
        )

        self.assertRedirects(
            response,
            reverse("donations:campaign_detail", args=[self.campaign.slug]),
        )
        self.assertContains(response, "tidak menerima donasi")
        self.assertEqual(Donation.objects.count(), 0)

    def test_methods_other_than_get_and_post_are_rejected(self):
        response = self.client.put(self.donation_url())

        self.assertEqual(response.status_code, 405)
