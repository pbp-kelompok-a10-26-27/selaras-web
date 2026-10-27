from decimal import Decimal

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.donations.models import Campaign, Donation


class DonationHistoryAndDetailTests(TestCase):
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

    def setUp(self):
        storages = {
            **settings.STORAGES,
            "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        }
        storage_settings = override_settings(STORAGES=storages)
        storage_settings.enable()
        self.addCleanup(storage_settings.disable)

    def make_donation(self, donor, status=Donation.Status.PENDING, proof=None):
        return Donation.objects.create(
            campaign=self.campaign,
            donor=donor,
            amount=Decimal("125.50"),
            status=status,
            proof=proof or "",
        )

    def proof_upload(self):
        return SimpleUploadedFile(
            "transfer.pdf", b"%PDF-1.7 receipt", content_type="application/pdf"
        )

    def test_anonymous_users_are_redirected_from_history_detail_and_proof(self):
        donation = self.make_donation(self.user, proof=self.proof_upload())
        self.client.logout()

        for url in (
            reverse("donations:history"),
            reverse("donations:detail", args=[donation.pk]),
            reverse("donations:proof", args=[donation.pk]),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response["Location"].startswith(reverse("accounts:login")))

    def test_history_contains_only_the_current_users_donations_and_statuses(self):
        own = [
            self.make_donation(self.user, status=status)
            for status in Donation.Status.values
        ]
        another = self.make_donation(self.other_user)
        self.client.force_login(self.user)

        response = self.client.get(reverse("donations:history"))

        self.assertEqual(
            {donation.pk for donation in response.context["donations"]},
            {donation.pk for donation in own},
        )
        for status in Donation.Status.values:
            self.assertContains(response, status)
        self.assertNotContains(
            response, reverse("donations:detail", args=[another.pk])
        )
        self.assertContains(response, reverse("donations:edit", args=[own[0].pk]))

    def test_admin_general_history_is_still_limited_to_admins_own_donations(self):
        own = self.make_donation(self.admin)
        another = self.make_donation(self.user)
        self.client.force_login(self.admin)

        response = self.client.get(reverse("donations:history"))

        self.assertEqual(list(response.context["donations"]), [own])
        self.assertNotContains(
            response, reverse("donations:detail", args=[another.pk])
        )

    def test_valid_status_filter_only_filters_current_users_donations(self):
        approved = self.make_donation(self.user, status=Donation.Status.APPROVED)
        self.make_donation(self.user, status=Donation.Status.PENDING)
        self.make_donation(self.other_user, status=Donation.Status.APPROVED)
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("donations:history"), {"status": Donation.Status.APPROVED}
        )

        self.assertEqual(list(response.context["donations"]), [approved])

    def test_invalid_status_filter_is_ignored_and_does_not_expand_history(self):
        own = self.make_donation(self.user)
        another = self.make_donation(self.other_user)
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("donations:history"), {"status": "NOT_A_STATUS"}
        )

        self.assertEqual(response.context["status"], "")
        self.assertEqual(list(response.context["donations"]), [own])
        self.assertNotContains(
            response, reverse("donations:detail", args=[another.pk])
        )

    def test_detail_shows_campaign_amount_date_and_each_status(self):
        self.client.force_login(self.user)

        for status in Donation.Status.values:
            with self.subTest(status=status):
                donation = self.make_donation(self.user, status=status)
                response = self.client.get(
                    reverse("donations:detail", args=[donation.pk])
                )

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, self.campaign.title)
                self.assertContains(response, "Rp 125.50")
                self.assertContains(response, donation.created_at.strftime("%Y"))
                self.assertContains(response, status)
                edit_url = reverse("donations:edit", args=[donation.pk])
                if status == Donation.Status.PENDING:
                    self.assertContains(response, edit_url)
                else:
                    self.assertNotContains(response, edit_url)

    def test_user_and_admin_cannot_open_another_donors_detail(self):
        donation = self.make_donation(self.other_user)

        for viewer in (self.user, self.admin):
            with self.subTest(viewer=viewer.username):
                self.client.force_login(viewer)
                response = self.client.get(
                    reverse("donations:detail", args=[donation.pk])
                )
                self.assertEqual(response.status_code, 404)

    def test_owner_downloads_proof_through_protected_route(self):
        donation = self.make_donation(self.user, proof=self.proof_upload())
        self.client.force_login(self.user)

        detail = self.client.get(reverse("donations:detail", args=[donation.pk]))
        proof = self.client.get(reverse("donations:proof", args=[donation.pk]))

        self.assertContains(detail, reverse("donations:proof", args=[donation.pk]))
        self.assertNotContains(detail, "/media/")
        self.assertEqual(proof.status_code, 200)
        self.assertIn("attachment", proof["Content-Disposition"])
        self.assertEqual(b"".join(proof.streaming_content), b"%PDF-1.7 receipt")

    def test_other_user_cannot_download_donation_proof(self):
        donation = self.make_donation(self.other_user, proof=self.proof_upload())
        self.client.force_login(self.user)

        response = self.client.get(reverse("donations:proof", args=[donation.pk]))

        self.assertEqual(response.status_code, 404)

    def test_missing_or_unavailable_proof_is_handled_without_exposing_a_url(self):
        donation = self.make_donation(self.user)
        missing_file = self.make_donation(self.user)
        missing_file.proof.name = "donations/missing.pdf"
        missing_file.save(update_fields=["proof"])
        self.client.force_login(self.user)

        detail = self.client.get(reverse("donations:detail", args=[donation.pk]))
        self.assertContains(detail, "Bukti tidak tersedia.")

        missing_detail = self.client.get(
            reverse("donations:detail", args=[missing_file.pk])
        )
        self.assertContains(missing_detail, "Bukti tidak tersedia.")
        self.assertEqual(
            self.client.get(reverse("donations:proof", args=[donation.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("donations:proof", args=[missing_file.pk])
            ).status_code,
            404,
        )
