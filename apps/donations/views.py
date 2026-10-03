from django.http import HttpResponse, JsonResponse

from apps.core.decorators import admin_required, login_required
from apps.core.utils import get_query_params


def campaign_list(request):
	"""Placeholder for searching and filtering environmental campaigns."""
	query_params = get_query_params(request, ("search", "status"))
	return JsonResponse(
		{"message": "Campaign search is not implemented yet.", **query_params},
		status=501,
	)


def campaign_detail(request, slug):
	"""Placeholder for displaying campaign details and progress."""
	return HttpResponse("Campaign detail is not implemented yet.", status=501)


@admin_required
def campaign_create(request):
	"""Placeholder for admin campaign creation."""
	return HttpResponse("Campaign creation is not implemented yet.", status=501)


@admin_required
def campaign_update(request, slug):
	"""Placeholder for admin campaign editing and publication."""
	return HttpResponse("Campaign update is not implemented yet.", status=501)


@login_required
def donation_create(request, slug):
	"""Placeholder for submitting a manual donation record."""
	return HttpResponse("Donation creation is not implemented yet.", status=501)


@login_required
def donation_detail(request, donation_id):
	"""Placeholder for viewing a user's donation record."""
	return HttpResponse("Donation detail is not implemented yet.", status=501)


@login_required
def donation_history(request):
	"""Placeholder for filtering the authenticated user's donation history."""
	query_params = get_query_params(request, ("status",))
	return JsonResponse(
		{"message": "Donation history filtering is not implemented yet.", **query_params},
		status=501,
	)


@admin_required
def donation_verify(request, donation_id):
	"""Placeholder for approving or rejecting a donation."""
	return HttpResponse("Donation verification is not implemented yet.", status=501)
