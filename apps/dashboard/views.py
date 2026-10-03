from django.http import HttpResponse

from apps.core.decorators import admin_required, login_required


@admin_required
def admin_dashboard(request):
    """Placeholder for the admin overview and management dashboard."""
    return HttpResponse("Admin dashboard is not implemented yet.", status=501)


@login_required
def user_dashboard(request):
    """Placeholder for the authenticated user's activity dashboard."""
    return HttpResponse("User dashboard is not implemented yet.", status=501)