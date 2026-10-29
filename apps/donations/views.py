from django.contrib import messages
from django.core.exceptions import SuspiciousFileOperation
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from apps.core.decorators import admin_required, login_required
from apps.core.permissions import is_admin
from apps.dashboard.views import render_dashboard

from .forms import CampaignForm, DonationForm, DonationUpdateForm
from .models import Campaign, Donation
from .services import (
    campaign_accepts_donations,
    campaign_progress_percent,
    campaign_stats,
    campaigns_visible_to,
    create_campaign_with_unique_slug,
    donor_impact,
    notify_new_donation,
    recent_donors,
    verify_pending_donation,
)


def _donation_challenges(user):
    """The user's running donation challenges, for the side panels."""
    from apps.challenges.models import Challenge
    from apps.challenges.services import active_progress

    return active_progress(user, goal_types=(Challenge.GoalType.DONATION_AMOUNT,))


def campaign_list(request):
    """Show published campaigns publicly and all campaigns to admins."""
    campaigns = campaigns_visible_to(request.user)
    search = request.GET.get("search", "").strip()[:100]
    status = request.GET.get("status", "").strip()

    if search:
        campaigns = campaigns.filter(
            Q(title__icontains=search) | Q(description__icontains=search)
        )
    if is_admin(request.user) and status in Campaign.Status.values:
        campaigns = campaigns.filter(status=status)

    for campaign in campaigns:
        campaign.progress_percent = campaign_progress_percent(campaign)
        campaign.accepts_donations = campaign_accepts_donations(campaign)

    return render(
        request,
        "donations/donations.html",
        {
            "campaigns": campaigns,
            "search": search,
            "status_filter": status if is_admin(request.user) else "",
            "status_choices": Campaign.Status.choices if is_admin(request.user) else (),
            "is_admin": is_admin(request.user),
        },
    )


def campaign_detail(request, slug):
    """Show campaign details without exposing unpublished campaigns publicly."""
    campaign = get_object_or_404(campaigns_visible_to(request.user), slug=slug)
    campaign.progress_percent = campaign_progress_percent(campaign)
    campaign.accepts_donations = campaign_accepts_donations(campaign)

    return render(
        request,
        "donations/campaign_detail.html",
        {
            "campaign": campaign,
            "recent_donors": recent_donors(campaign),
            "stats": campaign_stats(campaign),
            "milestones": (25, 50, 75),
            "challenge_progress": _donation_challenges(request.user),
        },
    )


@admin_required
@require_http_methods(["GET", "POST"])
def campaign_create(request):
    """Allow admins to create a validated campaign."""
    form = CampaignForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
    )
    if request.method == "POST" and form.is_valid():
        campaign = form.save(commit=False)
        create_campaign_with_unique_slug(campaign)
        messages.success(request, "Kampanye berhasil dibuat.")
        return redirect("donations:campaign_detail", slug=campaign.slug)

    return render_dashboard(
        request,
        "donations/admin/campaign_form.html",
        {"form": form, "is_create": True},
        active_section="donations",
    )


@admin_required
@require_http_methods(["GET", "POST"])
def campaign_update(request, slug):
    """Allow admins to edit a campaign while keeping its existing URL slug."""
    campaign = get_object_or_404(Campaign, slug=slug)
    form = CampaignForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
        instance=campaign,
    )
    if request.method == "POST" and form.is_valid():
        campaign = form.save()
        messages.success(request, "Kampanye berhasil diperbarui.")
        return redirect("donations:campaign_detail", slug=campaign.slug)

    return render_dashboard(
        request,
        "donations/admin/campaign_form.html",
        {"form": form, "campaign": campaign, "is_create": False},
        active_section="donations",
    )


@login_required
@require_http_methods(["GET", "POST"])
def donation_create(request, slug):
    """Record a manual donation for an available campaign."""
    campaign = get_object_or_404(campaigns_visible_to(request.user), slug=slug)

    # Recheck availability for both GET and POST. In particular, never save a
    # donation if the campaign closed while the donor's form was open.
    if not campaign_accepts_donations(campaign):
        messages.warning(
            request,
            "Kampanye ini sedang tidak menerima donasi. Silakan pilih kampanye lain.",
        )
        return redirect("donations:campaign_detail", slug=campaign.slug)

    # The form page previews how a donation moves this campaign's progress bar
    campaign.progress_percent = campaign_progress_percent(campaign)

    form = DonationForm(
        request.POST or None,
        request.FILES or None,
    )
    if request.method == "POST" and form.is_valid():
        donation = form.save(commit=False)
        donation.campaign = campaign
        donation.donor = request.user
        # Do not assign status: the Donation model's PENDING default applies.
        donation.save()
        notify_new_donation(donation)
        messages.success(
            request,
            "Donasi berhasil dicatat dan sedang menunggu verifikasi admin.",
        )
        return redirect("donations:campaign_detail", slug=campaign.slug)

    return render(
        request,
        "donations/donation_form.html",
        {
            "form": form,
            "campaign": campaign,
            "challenge_progress": _donation_challenges(request.user),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def donation_update(request, donation_id):
    """Let a donor update only their own still-pending donation."""
    owned_donations = Donation.objects.filter(donor=request.user).select_related(
        "campaign"
    )

    if request.method == "POST":
        # Lock and re-read the owned record on every POST so a stale form
        # cannot change a donation after an admin has verified it.
        with transaction.atomic():
            donation = get_object_or_404(
                owned_donations.select_for_update(), pk=donation_id
            )
            if donation.status != Donation.Status.PENDING:
                messages.warning(
                    request, "Donasi yang sudah diverifikasi tidak dapat diedit."
                )
                return redirect("donations:detail", donation_id=donation.pk)

            form = DonationUpdateForm(
                request.POST,
                request.FILES,
                instance=donation,
            )
            if form.is_valid():
                updated_donation = form.save(commit=False)
                updated_donation.save(
                    update_fields=[
                        "amount",
                        "proof",
                        "message",
                        "is_anonymous",
                        "updated_at",
                    ]
                )
                messages.success(request, "Donasi berhasil diperbarui.")
                return redirect("donations:detail", donation_id=donation.pk)
    else:
        donation = get_object_or_404(owned_donations, pk=donation_id)
        if donation.status != Donation.Status.PENDING:
            messages.warning(
                request, "Donasi yang sudah diverifikasi tidak dapat diedit."
            )
            return redirect("donations:detail", donation_id=donation.pk)
        form = DonationUpdateForm(instance=donation)

    return render(
        request,
        "donations/donation_edit_form.html",
        {
            "form": form,
            "donation": donation,
            "proof_available": _proof_exists(donation),
        },
    )


@login_required
def donation_detail(request, donation_id):
    """Show only a donation owned by the current user."""
    donation = get_object_or_404(
        Donation.objects.select_related("campaign").filter(donor=request.user),
        pk=donation_id,
    )
    proof_available = _proof_exists(donation)
    return render(
        request,
        "donations/donation_detail.html",
        {"donation": donation, "proof_available": proof_available},
    )


@login_required
def donation_history(request):
    """List and filter only donations belonging to the current user."""
    status = request.GET.get("status", "").strip()
    if status not in Donation.Status.values:
        status = ""

    donations = Donation.objects.filter(donor=request.user).select_related("campaign")
    if status:
        donations = donations.filter(status=status)

    return render(
        request,
        "donations/donation_history.html",
        {
            "donations": donations.order_by("-created_at", "-pk"),
            "status": status,
            "status_choices": Donation.Status.choices,
            "impact": donor_impact(request.user),
            "challenge_progress": _donation_challenges(request.user),
        },
    )


@login_required
@require_GET
def donation_proof(request, donation_id):
    """Download proof only after verifying the current user owns the donation."""
    donation = get_object_or_404(
        Donation.objects.filter(donor=request.user), pk=donation_id
    )
    if not donation.proof:
        raise Http404("Donation proof was not found.")

    try:
        proof_file = donation.proof.open("rb")
    except (OSError, ValueError, SuspiciousFileOperation) as exc:
        raise Http404("Donation proof was not found.") from exc

    filename = donation.proof.name.rsplit("/", 1)[-1]
    return FileResponse(proof_file, as_attachment=True, filename=filename)


def _proof_exists(donation):
    """Return whether a referenced proof is present, without exposing its URL."""
    if not donation.proof:
        return False
    try:
        return donation.proof.storage.exists(donation.proof.name)
    except (OSError, ValueError, SuspiciousFileOperation):
        return False


QUEUE_ICONS = {
    Donation.Status.PENDING: "clock",
    Donation.Status.APPROVED: "circle-check",
    Donation.Status.REJECTED: "circle-x",
}


@admin_required
def donation_verification_queue(request):
    """All donations for admins: allowlisted status filter, search, and paging.
    Waiting donations are shown oldest first so nobody waits forever."""
    status = request.GET.get("status", "").strip()
    if status not in Donation.Status.values:
        status = ""
    search = request.GET.get("search", "").strip()[:100]

    donations = Donation.objects.select_related("campaign", "donor")
    counts = donations.aggregate(
        all=Count("pk"),
        **{
            value.lower(): Count("pk", filter=Q(status=value))
            for value in Donation.Status.values
        },
    )
    if status:
        donations = donations.filter(status=status)
    if search:
        donations = donations.filter(
            Q(campaign__title__icontains=search)
            | Q(donor__username__icontains=search)
            | Q(donor__first_name__icontains=search)
            | Q(donor__last_name__icontains=search)
            | Q(donor__email__icontains=search)
        )
    ordering = (
        ("created_at", "pk")
        if status == Donation.Status.PENDING
        else ("-created_at", "-pk")
    )
    page_obj = Paginator(donations.order_by(*ordering), 20).get_page(
        request.GET.get("page")
    )

    return render_dashboard(
        request,
        "donations/admin/donation_list.html",
        {
            "donations": page_obj,
            "page_obj": page_obj,
            "status": status,
            "search": search,
            "status_tabs": [
                ("", "Semua", "layers", counts["all"]),
                *(
                    (value, label, QUEUE_ICONS[value], counts[value.lower()])
                    for value, label in Donation.Status.choices
                ),
            ],
        },
        active_section="donations",
    )


@admin_required
@require_http_methods(["GET", "POST"])
def donation_verify(request, donation_id):
    """Review a donation and accept one decision while it remains pending."""
    donation = get_object_or_404(
        Donation.objects.select_related("campaign", "donor", "verified_by"),
        pk=donation_id,
    )

    if request.method == "POST":
        status = request.POST.get("status", "")
        if status not in (Donation.Status.APPROVED, Donation.Status.REJECTED):
            messages.error(request, "Pilih setujui atau tolak, ya.")
        elif verify_pending_donation(
            donation.pk,
            status,
            admin=request.user,
            reason=request.POST.get("rejection_reason", ""),
        ):
            messages.success(
                request,
                "Donasi disetujui."
                if status == Donation.Status.APPROVED
                else "Donasi ditolak. Donatur sudah diberi tahu alasannya.",
            )
        else:
            messages.warning(
                request,
                "Donasi ini sudah diverifikasi. Status dan waktu verifikasinya "
                "tidak diubah.",
            )
        return redirect("donations:verify", donation_id=donation.pk)

    return render_dashboard(
        request,
        "donations/admin/donation_verify.html",
        {"donation": donation, "proof_available": _proof_exists(donation)},
        active_section="donations",
    )


@admin_required
@require_GET
def admin_donation_proof(request, donation_id):
    """Download a donor's proof from the separately protected admin flow."""
    donation = get_object_or_404(Donation, pk=donation_id)
    return _proof_response(donation)


def _proof_response(donation):
    if not donation.proof:
        raise Http404("Donation proof was not found.")

    try:
        proof_file = donation.proof.open("rb")
    except (OSError, ValueError, SuspiciousFileOperation) as exc:
        raise Http404("Donation proof was not found.") from exc

    filename = donation.proof.name.rsplit("/", 1)[-1]
    return FileResponse(proof_file, as_attachment=True, filename=filename)
