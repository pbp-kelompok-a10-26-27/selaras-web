from django.contrib.auth.mixins import LoginRequiredMixin


class AuthenticatedRequiredMixin(LoginRequiredMixin):
    
    """
    Shared authentication mixin for class-based views.
    """

    login_url = "accounts:login"