from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.donations.models import Campaign, Donation
from apps.donations.services import DEFAULT_REJECTION_REASON
from apps.notifications.models import Notification


class DonorWallTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.donor = User.objects.create_user(
            "sari", "sari@example.com", "pw", first_name="Sari"
        )
        self.shy = User.objects.create_user(
            "budi", "budi@example.com", "pw", first_name="Budi"
        )
        self.admin = User.objects.create_user(
            "admin", "admin@example.com", "pw", role="admin"
        )
        self.campaign = Campaign.objects.create(
            title="Hutan kota",
            description="Tanam pohon.",
            target_amount=Decimal("1000000"),
            status=Campaign.Status.PUBLISHED,
        )

    def test_campaign_shows_verified_donors_and_hides_anonymous_names(self):
        Donation.objects.create(
            campaign=self.campaign,
            donor=self.donor,
            amount=Decimal("50000"),
            message="Semangat!",
            status=Donation.Status.APPROVED,
        )
        Donation.objects.create(
            campaign=self.campaign,
            donor=self.shy,
            amount=Decimal("75000"),
            is_anonymous=True,
            status=Donation.Status.APPROVED,
        )
        Donation.objects.create(
            campaign=self.campaign, donor=self.shy, amount=Decimal("10000")
        )
        response = self.client.get(
            reverse("donations:campaign_detail", args=[self.campaign.slug])
        )
        self.assertContains(response, "Sari")
        self.assertContains(response, "Semangat!")
        self.assertContains(response, "Orang baik")
        self.assertNotContains(response, "Budi")
        self.assertEqual(response.context["stats"]["donor_count"], 2)
        self.assertEqual(response.context["stats"]["donation_count"], 2)

    def test_donating_notifies_admins_and_saves_message(self):
        self.client.force_login(self.donor)
        from django.core.files.uploadedfile import SimpleUploadedFile

        proof = SimpleUploadedFile(
            "proof.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 8, content_type="image/png"
        )
        self.client.post(
            reverse("donations:donate", args=[self.campaign.slug]),
            {
                "amount": "25000",
                "proof": proof,
                "message": "Untuk bumi",
                "is_anonymous": "on",
            },
        )
        donation = Donation.objects.get()
        self.assertTrue(donation.is_anonymous)
        self.assertEqual(donation.message, "Untuk bumi")
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.admin, kind=Notification.Kind.DONATION_SUBMITTED
            ).exists()
        )

    def test_rejection_reason_reaches_the_donor(self):
        donation = Donation.objects.create(
            campaign=self.campaign, donor=self.donor, amount=Decimal("20000")
        )
        self.client.force_login(self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse("donations:verify", args=[donation.pk]),
                {"status": "REJECTED", "rejection_reason": "Nominal tidak sama."},
            )
        donation.refresh_from_db()
        self.assertEqual(donation.rejection_reason, "Nominal tidak sama.")
        self.assertEqual(donation.verified_by, self.admin)
        note = Notification.objects.get(recipient=self.donor)
        self.assertEqual(note.kind, Notification.Kind.DONATION_REJECTED)
        self.assertEqual(note.message, "Nominal tidak sama.")

        self.client.force_login(self.donor)
        detail = self.client.get(reverse("donations:detail", args=[donation.pk]))
        self.assertContains(detail, "Alasan dari admin")
        self.assertContains(detail, "Nominal tidak sama.")

    def test_rejecting_without_reason_uses_a_general_one(self):
        donation = Donation.objects.create(
            campaign=self.campaign, donor=self.donor, amount=Decimal("20000")
        )
        self.client.force_login(self.admin)
        self.client.post(
            reverse("donations:verify", args=[donation.pk]), {"status": "REJECTED"}
        )
        donation.refresh_from_db()
        self.assertEqual(donation.rejection_reason, DEFAULT_REJECTION_REASON)

    def test_history_shows_impact_totals(self):
        Donation.objects.create(
            campaign=self.campaign,
            donor=self.donor,
            amount=Decimal("40000"),
            status=Donation.Status.APPROVED,
        )
        Donation.objects.create(
            campaign=self.campaign, donor=self.donor, amount=Decimal("5000")
        )
        self.client.force_login(self.donor)
        response = self.client.get(reverse("donations:history"))
        impact = response.context["impact"]
        self.assertEqual(impact["approved_total"], Decimal("40000"))
        self.assertEqual(impact["campaigns_supported"], 1)
        self.assertEqual(impact["pending_count"], 1)
        self.assertContains(response, "Total tersalurkan")

    def test_donation_urls_use_uuids(self):
        donation = Donation.objects.create(
            campaign=self.campaign, donor=self.donor, amount=Decimal("20000")
        )
        self.assertIn(str(donation.pk), reverse("donations:detail", args=[donation.pk]))
        self.client.force_login(self.donor)
        self.assertEqual(self.client.get("/donations/1/").status_code, 404)
