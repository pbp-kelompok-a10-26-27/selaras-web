from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from apps.donations.forms import (
    MAX_PROOF_UPLOAD_SIZE,
    CampaignForm,
    DonationForm,
)


class CampaignFormTests(SimpleTestCase):
    def campaign_data(self, **overrides):
        data = {
            "title": "River cleanup",
            "description": "Remove litter from the river bank.",
            "target_amount": "1000.00",
            "status": "DRAFT",
            "starts_at": "2026-10-01T10:00",
            "ends_at": "2026-10-31T10:00",
        }
        data.update(overrides)
        return data

    def test_accepts_positive_target(self):
        form = CampaignForm(data=self.campaign_data())

        self.assertTrue(form.is_valid(), form.errors)

    def test_rejects_zero_and_negative_target(self):
        for target in ("0", "-1"):
            with self.subTest(target=target):
                form = CampaignForm(data=self.campaign_data(target_amount=target))

                self.assertFalse(form.is_valid())
                self.assertIn("target_amount", form.errors)

    def test_accepts_end_date_equal_to_or_after_start_date(self):
        for end_date in ("2026-10-01T10:00", "2026-10-31T10:00"):
            with self.subTest(end_date=end_date):
                form = CampaignForm(data=self.campaign_data(ends_at=end_date))

                self.assertTrue(form.is_valid(), form.errors)

    def test_rejects_end_date_before_start_date(self):
        form = CampaignForm(
            data=self.campaign_data(
                starts_at="2026-10-31T10:00", ends_at="2026-10-01T10:00"
            )
        )

        self.assertFalse(form.is_valid())
        self.assertIn("ends_at", form.errors)


class DonationFormTests(SimpleTestCase):
    def donation_form(self, *, amount="25000.00", proof=None):
        files = {"proof": proof} if proof else {}
        return DonationForm(data={"amount": amount}, files=files)

    def valid_upload(self, name="transfer.png", content=b"\x89PNG\r\n\x1a\nimage-data"):
        return SimpleUploadedFile(
            name, content, content_type="application/octet-stream"
        )

    def test_accepts_positive_amount(self):
        form = self.donation_form(proof=self.valid_upload())

        self.assertTrue(form.is_valid(), form.errors)

    def test_rejects_zero_and_negative_amount(self):
        for amount in ("0", "-1"):
            with self.subTest(amount=amount):
                form = self.donation_form(amount=amount, proof=self.valid_upload())

                self.assertFalse(form.is_valid())
                self.assertIn("amount", form.errors)

    def test_requires_proof_upload(self):
        form = self.donation_form(proof=None)

        self.assertFalse(form.is_valid())
        self.assertIn("proof", form.errors)

    def test_rejects_unsupported_file_extension(self):
        form = self.donation_form(
            proof=self.valid_upload(name="transfer.txt", content=b"plain text")
        )

        self.assertFalse(form.is_valid())
        self.assertIn("proof", form.errors)

    def test_rejects_file_with_mismatched_signature(self):
        form = self.donation_form(
            proof=self.valid_upload(name="transfer.pdf", content=b"not a PDF")
        )

        self.assertFalse(form.is_valid())
        self.assertIn("proof", form.errors)

    def test_rejects_file_larger_than_five_mib(self):
        form = self.donation_form(
            proof=self.valid_upload(
                name="transfer.pdf",
                content=b"%PDF-" + b"x" * MAX_PROOF_UPLOAD_SIZE,
            )
        )

        self.assertFalse(form.is_valid())
        self.assertIn("proof", form.errors)

    def test_accepts_supported_image_and_pdf_uploads(self):
        supported_files = (
            ("proof.bmp", b"BM" + b"x" * 14),
            ("proof.gif", b"GIF89a" + b"x" * 10),
            ("proof.jpg", b"\xff\xd8\xff" + b"x" * 13),
            ("proof.pdf", b"%PDF-1.7" + b"x" * 8),
            ("proof.png", b"\x89PNG\r\n\x1a\n" + b"x" * 8),
            ("proof.tiff", b"II*\x00" + b"x" * 12),
            ("proof.webp", b"RIFF" + b"xxxx" + b"WEBP" + b"x" * 4),
        )

        for name, content in supported_files:
            with self.subTest(name=name):
                form = self.donation_form(proof=self.valid_upload(name, content))

                self.assertTrue(form.is_valid(), form.errors)
