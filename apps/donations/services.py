from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from apps.core.permissions import is_admin
from apps.core.templatetags.ui_extras import rupiah
from apps.notifications.services import Kind, notify, notify_admins

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


DEFAULT_REJECTION_REASON = "Bukti transfer belum dapat kami verifikasi."


def verify_pending_donation(donation_id, status, now=None, admin=None, reason=""):
    """Atomically verify a pending donation, leaving completed records untouched.

    Saved through the model (not a queryset update) so post_save listeners, such as
    challenge tracking, see the approval.
    """
    allowed_statuses = (Donation.Status.APPROVED, Donation.Status.REJECTED)
    if status not in allowed_statuses:
        raise ValueError("Verification status must be APPROVED or REJECTED.")

    now = now or timezone.now()
    with transaction.atomic():
        donation = (
            Donation.objects.select_for_update()
            .select_related("campaign", "donor")
            .filter(pk=donation_id, status=Donation.Status.PENDING)
            .first()
        )
        if donation is None:
            return False
        donation.status = status
        donation.verified_at = now
        donation.verified_by = admin
        donation.rejection_reason = (
            (reason.strip() or DEFAULT_REJECTION_REASON)[:300]
            if status == Donation.Status.REJECTED
            else ""
        )
        donation.save(
            update_fields=(
                "status",
                "verified_at",
                "verified_by",
                "rejection_reason",
                "updated_at",
            )
        )
        transaction.on_commit(lambda: _notify_donor(donation))
    return True


def _notify_donor(donation):
    url = reverse("donations:detail", args=(donation.pk,))
    amount = f"Rp {rupiah(donation.amount)}"
    if donation.status == Donation.Status.APPROVED:
        notify(
            donation.donor,
            Kind.DONATION_APPROVED,
            "Donasimu sudah diverifikasi",
            f"{amount} untuk “{donation.campaign.title}” kini tercatat. Terima kasih!",
            url=url,
        )
    else:
        notify(
            donation.donor,
            Kind.DONATION_REJECTED,
            "Donasimu belum dapat diverifikasi",
            donation.rejection_reason,
            url=url,
        )


def notify_new_donation(donation):
    notify_admins(
        Kind.DONATION_SUBMITTED,
        "Donasi baru menunggu verifikasi",
        f"Rp {rupiah(donation.amount)} untuk “{donation.campaign.title}”.",
        url=reverse("donations:verify", args=(donation.pk,)),
        actor=donation.donor,
    )


def recent_donors(campaign, limit=8):
    """Latest approved donations for the campaign's donor wall."""
    return (
        Donation.objects.filter(campaign=campaign, status=Donation.Status.APPROVED)
        .select_related("donor")
        .order_by("-verified_at", "-created_at")[:limit]
    )


def campaign_stats(campaign):
    approved = Donation.objects.filter(
        campaign=campaign, status=Donation.Status.APPROVED
    )
    return {
        "donor_count": approved.values("donor").distinct().count(),
        "donation_count": approved.count(),
    }


def donor_impact(user):
    """Totals for a donor's history page."""
    donations = Donation.objects.filter(donor=user)
    approved = donations.filter(status=Donation.Status.APPROVED)
    return {
        "approved_total": approved.aggregate(total=Sum("amount"))["total"]
        or Decimal("0"),
        "campaigns_supported": approved.values("campaign").distinct().count(),
        "pending_count": donations.filter(status=Donation.Status.PENDING).count(),
        "rejected_count": donations.filter(status=Donation.Status.REJECTED).count(),
    }
