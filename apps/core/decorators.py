from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from apps.core.permissions import is_admin


def admin_required(view_func):
    """
    Restrict a view to Admin users.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")

        if not is_admin(request.user):
            messages.error(request, "You do not have permission to access this page.")
            return redirect("home")

        return view_func(request, *args, **kwargs)

    return wrapper