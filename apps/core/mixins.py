from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied

from apps.core.permissions import is_admin


class AuthenticatedRequiredMixin(LoginRequiredMixin):
    """Shared authentication mixin. Login URL comes from settings.LOGIN_URL."""


class AdminRequiredMixin(AuthenticatedRequiredMixin, UserPassesTestMixin):
    """Anonymous -> login page (keeps ?next=). Logged in but not admin -> 403."""

    def test_func(self):
        return is_admin(self.request.user)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied
        return super().handle_no_permission()


class OwnerRequiredMixin(AuthenticatedRequiredMixin):
    """Restricts a view's queryset to objects owned by the current user.
    Other users' objects return 404. Set owner_field if the FK isn't 'user'."""

    owner_field = "user"

    def get_queryset(self):
        return super().get_queryset().filter(**{self.owner_field: self.request.user})