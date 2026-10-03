from django.http import HttpResponse, JsonResponse

from apps.core.decorators import admin_required, login_required
from apps.core.utils import get_query_params


def article_list(request):
	"""Placeholder for searching and filtering published educational articles."""
	query_params = get_query_params(request, ("search", "category", "status"))
	return JsonResponse(
		{"message": "Article search is not implemented yet.", **query_params},
		status=501,
	)


def article_detail(request, slug):
	"""Placeholder for displaying one educational article by slug."""
	return HttpResponse("Article detail is not implemented yet.", status=501)


@login_required
def article_create(request):
	"""Placeholder for authenticated article creation."""
	return HttpResponse("Article creation is not implemented yet.", status=501)


@admin_required
def article_update(request, slug):
	"""Placeholder for admin article editing and publication management."""
	return HttpResponse("Article update is not implemented yet.", status=501)


@admin_required
def article_delete(request, slug):
	"""Placeholder for admin article deletion."""
	return HttpResponse("Article deletion is not implemented yet.", status=501)
