"""Photos attached to feed posts: validation and storage shared by the HTML form
and the JSON API."""

import logging
import uuid

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile

from apps.core.permissions import is_admin

from .models import (
    MAX_POST_IMAGES,
    MAX_POST_IMAGES_ADMIN,
    MAX_POST_UPLOAD_BYTES,
    PostImage,
)

logger = logging.getLogger(__name__)

SIGNATURES = (
    (b"\xff\xd8\xff", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", ".png"),
)
MAX_MB = MAX_POST_UPLOAD_BYTES // (1024 * 1024)


def max_images_for(user):
    return MAX_POST_IMAGES_ADMIN if is_admin(user) else MAX_POST_IMAGES


def image_extension(upload):
    upload.seek(0)
    signature = upload.read(12)
    upload.seek(0)
    for prefix, extension in SIGNATURES:
        if signature.startswith(prefix):
            return extension
    if signature.startswith(b"RIFF") and signature[8:12] == b"WEBP":
        return ".webp"
    return None


def validate_images(uploads, user):
    """Check count, total size and real file type; give each a random name.

    Raises ValidationError with code "too_many", "too_large", "invalid" or
    "unsupported" so the API can pick a status code.
    """
    uploads = [upload for upload in uploads if upload]
    limit = max_images_for(user)
    if len(uploads) > limit:
        raise ValidationError(f"Maksimal {limit} foto per postingan.", code="too_many")
    if sum(getattr(upload, "size", 0) for upload in uploads) > MAX_POST_UPLOAD_BYTES:
        message = (
            f"Ukuran foto maksimal {MAX_MB} MB."
            if len(uploads) == 1
            else f"Total ukuran foto maksimal {MAX_MB} MB."
        )
        raise ValidationError(message, code="too_large")
    for upload in uploads:
        if not isinstance(upload, UploadedFile):
            raise ValidationError("File foto tidak valid.", code="invalid")
        extension = image_extension(upload)
        if extension is None:
            raise ValidationError(
                "Foto harus berformat JPEG, PNG, atau WebP.", code="unsupported"
            )
        upload.name = f"{uuid.uuid4().hex}{extension}"
    return uploads


def save_images(post, uploads, start=0):
    """Store validated uploads as the post's photos. Returns the saved names so a
    failed transaction can remove them again."""
    saved = []
    try:
        for offset, upload in enumerate(uploads):
            image = PostImage(post=post, position=start + offset)
            image.image.save(upload.name, upload, save=False)
            saved.append(image.image.name)
            image.save()
    except Exception:
        for name in saved:
            delete_file(name)
        raise
    return saved


def delete_file(name):
    try:
        PostImage._meta.get_field("image").storage.delete(name)
    except OSError:
        logger.warning("Unable to delete feed image %s", name, exc_info=True)


def stored_names(post):
    return list(post.images.values_list("image", flat=True))
