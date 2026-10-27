from pathlib import Path

from django import forms
from django.core.exceptions import ValidationError

from .models import Campaign, Donation

# Configurable assumption: proof uploads are limited to 5 MiB (5 * 1024 * 1024
# bytes). Change this constant if the project agrees on a different limit.
MAX_PROOF_UPLOAD_SIZE = 5 * 1024 * 1024

# Restrict uploads to common raster image formats and PDF. The signature checks
# below make sure the file content agrees with its extension.
PROOF_FILE_SIGNATURES = {
    ".bmp": lambda header: header.startswith(b"BM"),
    ".gif": lambda header: header.startswith((b"GIF87a", b"GIF89a")),
    ".jpeg": lambda header: header.startswith(b"\xff\xd8\xff"),
    ".jpg": lambda header: header.startswith(b"\xff\xd8\xff"),
    ".pdf": lambda header: header.startswith(b"%PDF-"),
    ".png": lambda header: header.startswith(b"\x89PNG\r\n\x1a\n"),
    ".tif": lambda header: header.startswith((b"II*\x00", b"MM\x00*")),
    ".tiff": lambda header: header.startswith((b"II*\x00", b"MM\x00*")),
    ".webp": lambda header: (
        len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP"
    ),
}


def validate_proof_file(uploaded_file):
    """Validate proof size and basic file signature on the server."""
    if uploaded_file.size > MAX_PROOF_UPLOAD_SIZE:
        raise ValidationError("Proof files must be 5 MB or smaller.")

    extension = Path(uploaded_file.name).suffix.lower()
    signature_check = PROOF_FILE_SIGNATURES.get(extension)
    if signature_check is None:
        raise ValidationError("Upload a common image file or a PDF.")

    # Check the actual file header instead of trusting the filename or the
    # browser-provided content type. Restore the stream for Django's storage.
    current_position = uploaded_file.tell()
    try:
        uploaded_file.seek(0)
        header = uploaded_file.read(16)
    finally:
        uploaded_file.seek(current_position)

    if not signature_check(header):
        raise ValidationError("The file contents do not match the selected file type.")


class CampaignForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = (
            "title",
            "description",
            "target_amount",
            "status",
            "starts_at",
            "ends_at",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def clean_target_amount(self):
        target_amount = self.cleaned_data["target_amount"]
        if target_amount <= 0:
            raise ValidationError("Campaign target must be greater than zero.")
        return target_amount

    def clean(self):
        cleaned_data = super().clean()
        starts_at = cleaned_data.get("starts_at")
        ends_at = cleaned_data.get("ends_at")

        if starts_at and ends_at and ends_at < starts_at:
            self.add_error("ends_at", "End date must be on or after the start date.")

        return cleaned_data


class DonationForm(forms.ModelForm):
    class Meta:
        model = Donation
        fields = ("amount", "proof")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The model allows an empty file for legacy/admin records, but the
        # donation submission requirement says proof must be supplied.
        self.fields["proof"].required = True

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= 0:
            raise ValidationError("Donation amount must be greater than zero.")
        return amount

    def clean_proof(self):
        proof = self.cleaned_data.get("proof")
        if proof:
            validate_proof_file(proof)
        return proof