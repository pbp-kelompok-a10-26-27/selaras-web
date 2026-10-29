# Validators
import uuid
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError

# What the first bytes of a real image look like. The browser's Content-Type and the
# file extension are chosen by the sender, so neither is trusted. SVG is left out on
# purpose: it can carry scripts.
IMAGE_SIGNATURES = (
    (b"\xff\xd8\xff", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
)

IMAGE_TYPES_LABEL = "JPG, PNG, WebP, atau GIF"
IMAGE_URL_MAX_LENGTH = 500


def detect_image_extension(header: bytes) -> str | None:
    """File extension for the image type these leading bytes belong to, or None."""
    for signature, extension in IMAGE_SIGNATURES:
        if header.startswith(signature):
            return extension
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "webp"
    return None


def clean_image_upload(file, max_bytes: int):
    """Check that an upload is a real, small-enough image, and give it a random
    name with the right extension so the sender can't choose what gets stored.
    Returns the same file object, renamed."""

    if file.size > max_bytes:
        raise ValidationError(
            f"{file.name} terlalu besar. Maksimal {max_bytes // (1024 * 1024)} MB."
        )

    file.seek(0)
    extension = detect_image_extension(file.read(12))
    file.seek(0)
    if extension is None:
        raise ValidationError(f"{file.name} bukan gambar {IMAGE_TYPES_LABEL}.")

    file.name = f"{uuid.uuid4().hex}.{extension}"
    return file


def clean_image_url(value: str) -> str:
    """An http(s) link, trimmed. Whether it really is an image is up to the viewer's
    browser; we only make sure it can't be a javascript:, data: or file: URL."""

    value = value.strip()
    if len(value) > IMAGE_URL_MAX_LENGTH:
        raise ValidationError(f"Tautan maksimal {IMAGE_URL_MAX_LENGTH} karakter.")

    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.netloc or " " in value:
        raise ValidationError(f"“{value[:60]}” bukan tautan http(s) yang valid.")
    return value
