from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.text import slugify

from apps.core.permissions import is_admin

from .models import Campaign, Donation


def create_campaign_with_unique_slug(campaign):
    """Insert a campaign with a unique title-derived slug, retrying collisions."""
    if campaign.pk is not None:
        raise ValueError("Only unsaved campaigns can be created by this helper.")

    base_slug = slugify(campaign.title) or "campaign"
    max_length = Campaign._meta.get_field("slug").max_length
    suffix_number = 1

    while True:
        suffix = "" if suffix_number == 1 else f"-{suffix_number}"
        slug_base = base_slug[: max_length - len(suffix)].rstrip("-") or "campaign"
        candidate = f"{slug_base}{suffix}"

        if Campaign.objects.filter(slug=candidate).exists():
            suffix_number += 1
            continue

        try:
            # Keep each insert in its own savepoint. If a concurrent create
            # claims this slug after the exists() check, the failed insert is
            # rolled back before we query or try the next suffix.
            with transaction.atomic():
                campaign.slug = candidate
                campaign.save(force_insert=True)
        except IntegrityError:
            if not Campaign.objects.filter(slug=candidate).exists():
                raise
            suffix_number += 1
            continue

        return campaign


def campaign_queryset():
    """Return campaigns annotated with the amount of approved donations."""
    return Campaign.objects.annotate(
        approved_total=Coalesce(
            Sum(
                "donations__amount",
                filter=Q(donations__status=Donation.Status.APPROVED),
            ),
            Value(Decimal("0.00")),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    )


def campaigns_visible_to(user):
    """Admins can review every campaign; public visitors see published ones."""
    campaigns = campaign_queryset()
    if not is_admin(user):
        campaigns = campaigns.filter(status=Campaign.Status.PUBLISHED)
    return campaigns.order_by("-created_at", "title")


def campaign_progress_percent(campaign):
    """Return progress for display, capped at 100 percent."""
    if campaign.target_amount <= 0:
        return Decimal("0")

    percentage = campaign.approved_total / campaign.target_amount * 100
    return min(percentage, Decimal("100"))


def campaign_accepts_donations(campaign, now=None):
    """Check publication status and optional start/end bounds."""
    now = now or timezone.now()
    if campaign.status != Campaign.Status.PUBLISHED:
        return False
    if campaign.starts_at and now < campaign.starts_at:
        return False
    if campaign.ends_at and now > campaign.ends_at:
        return False
    return True


def verify_pending_donation(donation_id, status, now=None):
    """Atomically verify a pending donation, leaving completed records untouched."""
    allowed_statuses = (Donation.Status.APPROVED, Donation.Status.REJECTED)
    if status not in allowed_statuses:
        raise ValueError("Verification status must be APPROVED or REJECTED.")

    now = now or timezone.now()
    updated = Donation.objects.filter(
        pk=donation_id, status=Donation.Status.PENDING
    ).update(status=status, verified_at=now, updated_at=now)
    return updated == 1
