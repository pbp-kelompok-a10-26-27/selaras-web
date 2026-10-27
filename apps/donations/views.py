from django.contrib import messages
from django.core.exceptions import SuspiciousFileOperation
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from apps.core.decorators import admin_required, login_required
from apps.core.permissions import is_admin
from apps.dashboard.views import render_dashboard

from .forms import CampaignForm, DonationForm
from .models import Campaign, Donation
from .services import (
    campaign_accepts_donations,
    campaign_progress_percent,
    campaigns_visible_to,
    create_campaign_with_unique_slug,
    verify_pending_donation,
)


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

    return render(request, "donations/campaign_detail.html", {"campaign": campaign})


@admin_required
@require_http_methods(["GET", "POST"])
def campaign_create(request):
    """Allow admins to create a validated campaign."""
    form = CampaignForm(
        request.POST if request.method == "POST" else None,
    )
    if request.method == "POST" and form.is_valid():
        campaign = form.save(commit=False)
        create_campaign_with_unique_slug(campaign)
        messages.success(request, "Campaign created successfully.")
        return redirect("donations:campaign_detail", slug=campaign.slug)

    return render_dashboard(
        request,
        "donations/admin/campaign_form.html",
        {"form": form, "is_create": True},
    )


@admin_required
@require_http_methods(["GET", "POST"])
def campaign_update(request, slug):
    """Allow admins to edit a campaign while keeping its existing URL slug."""
    campaign = get_object_or_404(Campaign, slug=slug)
    form = CampaignForm(
        request.POST if request.method == "POST" else None,
        instance=campaign,
    )
    if request.method == "POST" and form.is_valid():
        campaign = form.save()
        messages.success(request, "Campaign updated successfully.")
        return redirect("donations:campaign_detail", slug=campaign.slug)

    return render_dashboard(
        request,
        "donations/admin/campaign_form.html",
        {"form": form, "campaign": campaign, "is_create": False},
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
        messages.success(
            request,
            "Donasi berhasil dicatat dan sedang menunggu verifikasi admin.",
        )
        return redirect("donations:campaign_detail", slug=campaign.slug)

    return render(
        request,
        "donations/donation_form.html",
        {"form": form, "campaign": campaign},
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


@admin_required
def donation_verification_queue(request):
    """Show all donations to admins, with an optional allowlisted status filter."""
    status = request.GET.get("status", "").strip()
    if status not in Donation.Status.values:
        status = ""

    donations = Donation.objects.select_related("campaign", "donor")
    if status:
        donations = donations.filter(status=status)

    return render_dashboard(
        request,
        "donations/admin/donation_list.html",
        {
            "donations": donations.order_by("-created_at", "-pk"),
            "status": status,
            "status_choices": Donation.Status.choices,
        },
    )


@admin_required
@require_http_methods(["GET", "POST"])
def donation_verify(request, donation_id):
    """Review a donation and accept one decision while it remains pending."""
    donation = get_object_or_404(
        Donation.objects.select_related("campaign", "donor"), pk=donation_id
    )

    if request.method == "POST":
        status = request.POST.get("status", "")
        if status not in (Donation.Status.APPROVED, Donation.Status.REJECTED):
            messages.error(request, "Pilih keputusan approve atau reject yang valid.")
        elif verify_pending_donation(donation.pk, status):
            messages.success(request, f"Donasi berhasil ditandai {status}.")
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
