from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.core.decorators import admin_required, login_required
from apps.core.permissions import is_admin
from apps.core.utils import get_query_params

from .forms import DonationForm
from .models import Campaign
from .services import (
    campaign_accepts_donations,
    campaign_progress_percent,
    campaigns_visible_to,
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
def campaign_create(request):
    """Placeholder for admin campaign creation."""
    return HttpResponse("Campaign creation is not implemented yet.", status=501)


@admin_required
def campaign_update(request, slug):
    """Placeholder for admin campaign editing and publication."""
    return HttpResponse("Campaign update is not implemented yet.", status=501)


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
    """Placeholder for viewing a user's donation record."""
    return HttpResponse("Donation detail is not implemented yet.", status=501)


@login_required
def donation_history(request):
    """Placeholder for filtering the authenticated user's donation history."""
    query_params = get_query_params(request, ("status",))
    return JsonResponse(
        {
            "message": "Donation history filtering is not implemented yet.",
            **query_params,
        },
        status=501,
    )


@admin_required
def donation_verify(request, donation_id):
    """Placeholder for approving or rejecting a donation."""
    return HttpResponse("Donation verification is not implemented yet.", status=501)
