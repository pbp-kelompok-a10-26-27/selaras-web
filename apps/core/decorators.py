from functools import wraps
from django.contrib import messages
from django.contrib.auth.decorators import login_required as django_login_required
from django.shortcuts import redirect
from apps.core.permissions import is_admin

login_required = django_login_required


def admin_required(view_func):
    """Restrict a view function strictly to Admin users."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")

        if not is_admin(request.user):
            messages.error(request, "You do not have permission to access this page.")
            return redirect("dashboard:user")

        return view_func(request, *args, **kwargs)

    return wrapper