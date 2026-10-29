from django.core.exceptions import ValidationError

from apps.core.validators import clean_image_upload, clean_image_url

from .models import TicketAttachment

ATTACHMENT_MAX_BYTES = 5 * 1024 * 1024


def validate_attachments(files, links):
    """Check the uploads and image links sent with a new ticket, before anything is
    saved. Returns (cleaned_files, cleaned_links, errors) where errors is a list of
    messages (empty when everything is fine)."""

    errors = []
    if len(files) + len(links) > TicketAttachment.MAX_PER_TICKET:
        errors.append(f"Maksimal {TicketAttachment.MAX_PER_TICKET} gambar atau tautan.")
        return [], [], errors

    cleaned_files = []
    for file in files:
        try:
            cleaned_files.append(clean_image_upload(file, ATTACHMENT_MAX_BYTES))
        except ValidationError as error:
            errors.extend(error.messages)

    cleaned_links = []
    for link in links:
        try:
            url = clean_image_url(link)
        except ValidationError as error:
            errors.extend(error.messages)
            continue
        if url not in cleaned_links:
            cleaned_links.append(url)

    return cleaned_files, cleaned_links, errors


def save_attachments(ticket, files, links):
    TicketAttachment.objects.bulk_create(
        [TicketAttachment(ticket=ticket, file=file) for file in files]
        + [TicketAttachment(ticket=ticket, url=url) for url in links]
    )
