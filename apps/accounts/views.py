from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView

from apps.core.mixins import AuthenticatedRequiredMixin

from .forms import ProfileForm, RegistrationForm
from .models import User


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


class ProfileView(AuthenticatedRequiredMixin, UpdateView):
    model = User
    form_class = ProfileForm
    template_name = "accounts/profile.html"
    success_url = reverse_lazy("accounts:profile")

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Profile updated successfully.")
        return super().form_valid(form)


class UserPasswordChangeView(AuthenticatedRequiredMixin, auth_views.PasswordChangeView):
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:password_change_done")

    def form_valid(self, form):
        messages.success(self.request, "Password changed successfully.")
        return super().form_valid(form)


class UserPasswordChangeDoneView(
    AuthenticatedRequiredMixin, auth_views.PasswordChangeDoneView
):
    template_name = "accounts/password_change_done.html"
