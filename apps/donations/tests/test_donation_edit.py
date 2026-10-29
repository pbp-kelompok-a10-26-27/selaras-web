from decimal import Decimal

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.donations.models import Campaign, Donation


class DonationEditTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="donor", email="donor@example.com", password="test-password"
        )
        cls.other_user = User.objects.create_user(
            username="another-donor",
            email="another@example.com",
            password="test-password",
        )
        cls.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="test-password",
            role=User.Role.ADMIN,
        )
        cls.campaign = Campaign.objects.create(
            title="River cleanup",
            description="Remove litter from the river.",
            target_amount=Decimal("1000.00"),
            status=Campaign.Status.PUBLISHED,
        )
        cls.other_campaign = Campaign.objects.create(
            title="Forest restoration",
            description="Restore native forest.",
            target_amount=Decimal("2000.00"),
            status=Campaign.Status.PUBLISHED,
        )

    def setUp(self):
        test_storages = {
            **settings.STORAGES,
            "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        }
        storage_settings = override_settings(STORAGES=test_storages)
        storage_settings.enable()
        self.addCleanup(storage_settings.disable)
        self.client.force_login(self.user)

    def make_donation(self, donor=None, status=Donation.Status.PENDING, proof=None):
        return Donation.objects.create(
            campaign=self.campaign,
            donor=donor or self.user,
            amount=Decimal("125.50"),
            status=status,
            proof=proof or "",
        )

    def proof_upload(self, name="transfer.pdf", content=b"%PDF-1.7 receipt"):
        return SimpleUploadedFile(name, content, content_type="application/pdf")

    def edit_url(self, donation):
        return reverse("donations:edit", args=[donation.pk])

    def test_owner_can_open_pending_donation_edit_form(self):
        donation = self.make_donation(proof=self.proof_upload())

        response = self.client.get(self.edit_url(donation))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "donations/donation_edit_form.html")
        self.assertFalse(response.context["form"].fields["proof"].required)
        self.assertContains(response, "Unggah file baru hanya jika ingin menggantinya")

    def test_post_updates_amount_and_preserves_existing_proof_without_upload(self):
        donation = self.make_donation(proof=self.proof_upload())
        original_proof_name = donation.proof.name

        response = self.client.post(self.edit_url(donation), {"amount": "250.00"})

        self.assertRedirects(response, reverse("donations:detail", args=[donation.pk]))
        donation.refresh_from_db()
        self.assertEqual(donation.amount, Decimal("250.00"))
        self.assertEqual(donation.proof.name, original_proof_name)

    def test_post_can_replace_proof_and_reuses_upload_validation(self):
        donation = self.make_donation(proof=self.proof_upload())
        old_proof_name = donation.proof.name

        response = self.client.post(
            self.edit_url(donation),
            {
                "amount": "250.00",
                "proof": self.proof_upload("replacement.pdf", b"%PDF-1.7 new proof"),
            },
        )

        self.assertRedirects(response, reverse("donations:detail", args=[donation.pk]))
        donation.refresh_from_db()
        self.assertNotEqual(donation.proof.name, old_proof_name)

    def test_invalid_amount_does_not_save_changes(self):
        donation = self.make_donation(proof=self.proof_upload())

        response = self.client.post(self.edit_url(donation), {"amount": "0"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("amount", response.context["form"].errors)
        donation.refresh_from_db()
        self.assertEqual(donation.amount, Decimal("125.50"))

    def test_uploaded_proof_still_rejects_unsupported_extension_and_signature(self):
        donation = self.make_donation(proof=self.proof_upload())
        invalid_uploads = (
            self.proof_upload("receipt.exe", b"%PDF-1.7 fake extension"),
            self.proof_upload("receipt.pdf", b"not a PDF signature"),
        )

        for upload in invalid_uploads:
            with self.subTest(name=upload.name):
                response = self.client.post(
                    self.edit_url(donation),
                    {"amount": "250.00", "proof": upload},
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn("proof", response.context["form"].errors)
                donation.refresh_from_db()
                self.assertEqual(donation.amount, Decimal("125.50"))

    def test_other_user_and_admin_cannot_edit_donations_they_do_not_own(self):
        donation = self.make_donation(donor=self.other_user)

        for viewer in (self.user, self.admin):
            with self.subTest(viewer=viewer.username):
                self.client.force_login(viewer)
                response = self.client.post(
                    self.edit_url(donation), {"amount": "999.00"}
                )
                self.assertEqual(response.status_code, 404)
                donation.refresh_from_db()
                self.assertEqual(donation.amount, Decimal("125.50"))

    def test_anonymous_user_is_redirected_and_only_get_post_are_allowed(self):
        donation = self.make_donation()
        self.client.logout()

        response = self.client.get(self.edit_url(donation))
        self.assertEqual(response.status_code, 302)

        self.client.force_login(self.user)
        self.assertEqual(self.client.put(self.edit_url(donation)).status_code, 405)

    def test_post_rechecks_pending_status_after_stale_edit_form(self):
        for status in (Donation.Status.APPROVED, Donation.Status.REJECTED):
            with self.subTest(status=status):
                donation = self.make_donation(proof=self.proof_upload())
                edit_response = self.client.get(self.edit_url(donation))
                self.assertEqual(edit_response.status_code, 200)
                Donation.objects.filter(pk=donation.pk).update(status=status)

                response = self.client.post(
                    self.edit_url(donation), {"amount": "500.00"}
                )

                self.assertRedirects(
                    response, reverse("donations:detail", args=[donation.pk])
                )
                donation.refresh_from_db()
                self.assertEqual(donation.amount, Decimal("125.50"))
                self.assertEqual(donation.status, status)

    def test_verified_donations_cannot_be_opened_for_edit(self):
        for status in (Donation.Status.APPROVED, Donation.Status.REJECTED):
            with self.subTest(status=status):
                donation = self.make_donation(status=status)
                response = self.client.get(self.edit_url(donation))
                self.assertRedirects(
                    response, reverse("donations:detail", args=[donation.pk])
                )

    def test_posted_protected_fields_are_ignored(self):
        donation = self.make_donation(proof=self.proof_upload())

        response = self.client.post(
            self.edit_url(donation),
            {
                "amount": "250.00",
                "donor": self.other_user.pk,
                "campaign": self.other_campaign.pk,
                "status": Donation.Status.APPROVED,
                "verified_at": "2026-10-28T12:00",
            },
        )

        self.assertRedirects(response, reverse("donations:detail", args=[donation.pk]))
        donation.refresh_from_db()
        self.assertEqual(donation.amount, Decimal("250.00"))
        self.assertEqual(donation.donor, self.user)
        self.assertEqual(donation.campaign, self.campaign)
        self.assertEqual(donation.status, Donation.Status.PENDING)
        self.assertIsNone(donation.verified_at)
