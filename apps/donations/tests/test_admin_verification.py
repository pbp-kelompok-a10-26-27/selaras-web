from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.donations.models import Campaign, Donation


class AdminDonationVerificationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="test-password",
            role=User.Role.ADMIN,
        )
        cls.user = User.objects.create_user(
            username="donor", email="donor@example.com", password="test-password"
        )
        cls.other_user = User.objects.create_user(
            username="other", email="other@example.com", password="test-password"
        )
        cls.campaign = Campaign.objects.create(
            title="River cleanup",
            description="Remove litter from the river.",
            target_amount=Decimal("1000.00"),
            status=Campaign.Status.PUBLISHED,
        )

    def setUp(self):
        storages = {
            **settings.STORAGES,
            "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        }
        storage_settings = override_settings(STORAGES=storages)
        storage_settings.enable()
        self.addCleanup(storage_settings.disable)

    def make_donation(self, donor=None, status=Donation.Status.PENDING, proof=None):
        return Donation.objects.create(
            campaign=self.campaign,
            donor=donor or self.user,
            amount=Decimal("125.50"),
            status=status,
            proof=proof or "",
        )

    def proof_upload(self):
        return SimpleUploadedFile(
            "transfer.pdf", b"%PDF-1.7 receipt", content_type="application/pdf"
        )

    def verify_url(self, donation):
        return reverse("donations:verify", args=[donation.pk])

    def test_anonymous_users_are_redirected_from_admin_routes(self):
        donation = self.make_donation(proof=self.proof_upload())
        urls = (
            reverse("donations:verification_queue"),
            self.verify_url(donation),
            reverse("donations:admin_proof", args=[donation.pk]),
        )

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(
                    response["Location"].startswith(reverse("accounts:login"))
                )

    def test_regular_users_are_denied_queue_detail_post_and_admin_proof(self):
        donation = self.make_donation(proof=self.proof_upload())
        self.client.force_login(self.user)

        self.assertEqual(
            self.client.get(reverse("donations:verification_queue")).status_code, 403
        )
        self.assertEqual(self.client.get(self.verify_url(donation)).status_code, 403)
        self.assertEqual(
            self.client.post(
                self.verify_url(donation), {"status": "APPROVED"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                reverse("donations:admin_proof", args=[donation.pk])
            ).status_code,
            403,
        )
        donation.refresh_from_db()
        self.assertEqual(donation.status, Donation.Status.PENDING)

    def test_admin_can_filter_queue_by_valid_status(self):
        pending = self.make_donation()
        approved = self.make_donation(self.other_user, Donation.Status.APPROVED)
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("donations:verification_queue"),
            {"status": Donation.Status.PENDING},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["donations"]), [pending])
        self.assertContains(response, pending.donor.username)
        self.assertNotContains(
            response, reverse("donations:verify", args=[approved.pk])
        )

    def test_invalid_queue_filter_is_ignored(self):
        pending = self.make_donation()
        approved = self.make_donation(self.other_user, Donation.Status.APPROVED)
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("donations:verification_queue"), {"status": "INVALID"}
        )

        self.assertEqual(response.context["status"], "")
        self.assertEqual(
            {donation.pk for donation in response.context["donations"]},
            {pending.pk, approved.pk},
        )

    def test_get_verification_detail_does_not_change_status(self):
        donation = self.make_donation(proof=self.proof_upload())
        self.client.force_login(self.admin)

        response = self.client.get(self.verify_url(donation))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PENDING")
        self.assertContains(
            response, reverse("donations:admin_proof", args=[donation.pk])
        )
        donation.refresh_from_db()
        self.assertEqual(donation.status, Donation.Status.PENDING)
        self.assertIsNone(donation.verified_at)

    def test_approve_sets_status_and_server_verification_time(self):
        donation = self.make_donation()
        self.client.force_login(self.admin)
        before = timezone.now()

        response = self.client.post(
            self.verify_url(donation), {"status": Donation.Status.APPROVED}
        )

        after = timezone.now()
        self.assertRedirects(response, self.verify_url(donation))
        donation.refresh_from_db()
        self.assertEqual(donation.status, Donation.Status.APPROVED)
        self.assertGreaterEqual(donation.verified_at, before)
        self.assertLessEqual(donation.verified_at, after)

    def test_reject_sets_status_and_server_verification_time(self):
        donation = self.make_donation()
        self.client.force_login(self.admin)
        before = timezone.now()

        self.client.post(
            self.verify_url(donation), {"status": Donation.Status.REJECTED}
        )

        after = timezone.now()
        donation.refresh_from_db()
        self.assertEqual(donation.status, Donation.Status.REJECTED)
        self.assertGreaterEqual(donation.verified_at, before)
        self.assertLessEqual(donation.verified_at, after)

    def test_repeated_or_conflicting_verification_does_not_overwrite_result(self):
        donation = self.make_donation()
        self.client.force_login(self.admin)
        self.client.post(
            self.verify_url(donation), {"status": Donation.Status.APPROVED}
        )
        donation.refresh_from_db()
        original_verified_at = donation.verified_at

        response = self.client.post(
            self.verify_url(donation), {"status": Donation.Status.REJECTED}, follow=True
        )

        donation.refresh_from_db()
        self.assertEqual(donation.status, Donation.Status.APPROVED)
        self.assertEqual(donation.verified_at, original_verified_at)
        self.assertContains(response, "sudah diverifikasi")

    def test_invalid_status_does_not_verify_donation(self):
        donation = self.make_donation()
        self.client.force_login(self.admin)

        response = self.client.post(
            self.verify_url(donation), {"status": "CANCELLED"}, follow=True
        )

        donation.refresh_from_db()
        self.assertEqual(donation.status, Donation.Status.PENDING)
        self.assertIsNone(donation.verified_at)
        self.assertContains(response, "Pilih setujui atau tolak")

    def test_verification_post_requires_csrf(self):
        donation = self.make_donation()
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)

        response = csrf_client.post(
            self.verify_url(donation), {"status": Donation.Status.APPROVED}
        )

        self.assertEqual(response.status_code, 403)
        donation.refresh_from_db()
        self.assertEqual(donation.status, Donation.Status.PENDING)
        self.assertIsNone(donation.verified_at)

    def test_admin_proof_download_is_protected_and_keeps_owner_route(self):
        donation = self.make_donation(proof=self.proof_upload())
        self.client.force_login(self.admin)

        admin_response = self.client.get(
            reverse("donations:admin_proof", args=[donation.pk])
        )

        self.assertEqual(admin_response.status_code, 200)
        self.assertIn("attachment", admin_response["Content-Disposition"])
        self.assertEqual(
            b"".join(admin_response.streaming_content), b"%PDF-1.7 receipt"
        )
        self.assertEqual(
            self.client.get(reverse("donations:proof", args=[donation.pk])).status_code,
            404,
        )

    def test_only_approved_donations_count_toward_campaign_progress(self):
        pending = self.make_donation()
        self.make_donation(self.other_user, Donation.Status.REJECTED)
        self.client.force_login(self.admin)

        initial = self.client.get(
            reverse("donations:campaign_detail", args=[self.campaign.slug])
        )
        self.assertEqual(initial.context["campaign"].approved_total, Decimal("0.00"))

        self.client.post(self.verify_url(pending), {"status": Donation.Status.APPROVED})
        updated = self.client.get(
            reverse("donations:campaign_detail", args=[self.campaign.slug])
        )

        self.assertEqual(updated.context["campaign"].approved_total, Decimal("125.50"))

    def test_verified_donation_has_no_decision_buttons(self):
        donation = self.make_donation(status=Donation.Status.REJECTED)
        donation.verified_at = timezone.now() - timedelta(days=1)
        donation.save(update_fields=["verified_at"])
        self.client.force_login(self.admin)

        response = self.client.get(self.verify_url(donation))

        self.assertNotContains(response, 'value="APPROVED"')
        self.assertNotContains(response, 'value="REJECTED"')
