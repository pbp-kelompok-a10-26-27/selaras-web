from decimal import Decimal

from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.core.permissions import is_admin

from .models import Campaign, Donation


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
