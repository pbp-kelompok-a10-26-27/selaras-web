from django.http import HttpResponse, JsonResponse

from apps.core.decorators import admin_required, login_required
from apps.core.utils import get_query_params


def challenge_list(request):
	"""Placeholder for searching and filtering published challenges."""
	query_params = get_query_params(request, ("search", "status", "start_date", "end_date"))
	return JsonResponse(
		{"message": "Challenge search is not implemented yet.", **query_params},
		status=501,
	)


def challenge_detail(request, slug):
	"""Placeholder for displaying challenge details."""
	return HttpResponse("Challenge detail is not implemented yet.", status=501)


@login_required
def join_challenge(request, slug):
	"""Placeholder for joining a challenge as the authenticated user."""
	return HttpResponse("Joining a challenge is not implemented yet.", status=501)


@login_required
def record_progress(request, slug):
	"""Placeholder for recording the authenticated user's daily progress."""
	return HttpResponse("Challenge progress is not implemented yet.", status=501)


@login_required
def challenge_history(request):
	"""Placeholder for viewing the authenticated user's challenge history."""
	return HttpResponse("Challenge history is not implemented yet.", status=501)


@admin_required
def challenge_create(request):
	"""Placeholder for admin challenge creation."""
	return HttpResponse("Challenge creation is not implemented yet.", status=501)


@admin_required
def challenge_update(request, slug):
	"""Placeholder for admin challenge editing."""
	return HttpResponse("Challenge update is not implemented yet.", status=501)


@admin_required
def challenge_delete(request, slug):
	"""Placeholder for admin challenge deletion."""
	return HttpResponse("Challenge deletion is not implemented yet.", status=501)
