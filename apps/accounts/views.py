from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, UpdateView

from apps.core.mixins import AuthenticatedRequiredMixin
from apps.core.permissions import is_admin
from apps.dashboard.navigation import get_sidebar_sections

from .forms import ProfileForm, RegistrationForm
from .models import User
from .services import get_profile_completion, get_profile_stats


class AccountLayoutMixin:
    """Admins see their account pages inside the dashboard (with the sidebar),
    everyone else inside the public site (navbar + footer)."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if is_admin(self.request.user):
            context.update(
                base_template="dashboard/base.html",
                in_dashboard=True,
                sidebar_sections=get_sidebar_sections(self.request.user),
                dashboard_home_url=reverse("dashboard:home"),
                logout_url=reverse("accounts:logout"),
            )
        else:
            context.update(base_template="base.html", in_dashboard=False)
        return context


class RegisterView(CreateView):
    form_class = RegistrationForm
    template_name = "accounts/register.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(settings.LOGIN_REDIRECT_URL)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save()  # role defaults to User
        login(self.request, self.object)
        messages.success(self.request, f"Welcome to SELARAS, {self.object.username}!")
        return redirect(settings.LOGIN_REDIRECT_URL)


class UserLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        messages.success(self.request, "Logged in successfully.")
        return super().form_valid(form)


class ProfileView(AuthenticatedRequiredMixin, AccountLayoutMixin, UpdateView):
    model = User
    form_class = ProfileForm
    template_name = "accounts/profile.html"
    success_url = reverse_lazy("accounts:profile")

    def get_object(self, queryset=None):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Header and side cards show the saved profile, not unsaved form input
        saved = User.objects.get(pk=self.request.user.pk)
        context.update(
            profile_user=saved,
            completion=get_profile_completion(saved),
            stats=get_profile_stats(saved),
        )
        return context

    def form_valid(self, form):
        messages.success(self.request, "Profile updated successfully.")
        return super().form_valid(form)


class UserPasswordChangeView(
    AuthenticatedRequiredMixin, AccountLayoutMixin, auth_views.PasswordChangeView
):
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:password_change_done")

    def form_valid(self, form):
        messages.success(self.request, "Password changed successfully.")
        return super().form_valid(form)


class UserPasswordChangeDoneView(
    AuthenticatedRequiredMixin, auth_views.PasswordChangeDoneView
):
    template_name = "accounts/password_change_done.html"
