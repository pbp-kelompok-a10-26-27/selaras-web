from django.http import HttpResponse, JsonResponse

from apps.core.decorators import admin_required, login_required
from apps.core.utils import get_query_params


@login_required
def ticket_list(request):
	"""Placeholder for searching and filtering the user's support tickets."""
	query_params = get_query_params(request, ("search", "status", "priority"))
	return JsonResponse(
		{"message": "Ticket search is not implemented yet.", **query_params},
		status=501,
	)


@login_required
def ticket_detail(request, ticket_id):
	"""Placeholder for displaying a ticket and its responses."""
	return HttpResponse("Ticket detail is not implemented yet.", status=501)


@login_required
def ticket_create(request):
	"""Placeholder for creating a support ticket."""
	return HttpResponse("Ticket creation is not implemented yet.", status=501)


@login_required
def ticket_message_create(request, ticket_id):
	"""Placeholder for adding a response to an accessible ticket."""
	return HttpResponse("Ticket response is not implemented yet.", status=501)


@admin_required
def ticket_update(request, ticket_id):
	"""Placeholder for support staff status updates and ticket closure."""
	return HttpResponse("Ticket update is not implemented yet.", status=501)
