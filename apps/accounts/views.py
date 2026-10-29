import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, UpdateView

from apps.core.decorators import login_required
from apps.core.mixins import AuthenticatedRequiredMixin
from apps.core.permissions import is_admin
from apps.core.validators import IMAGE_TYPES_LABEL, clean_image_upload
from apps.dashboard.navigation import get_sidebar_sections

from .forms import ProfileForm, RegistrationForm
from .models import User
from .services import (
    get_badge_collection,
    get_impact_summary,
    get_profile_completion,
    get_profile_stats,
)


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
        messages.success(
            self.request, f"Selamat datang di SELARAS, {self.object.username}!"
        )
        return redirect(settings.LOGIN_REDIRECT_URL)


logger = logging.getLogger(__name__)

# Batas login gagal per IP + username sebelum dikunci sementara
LOGIN_MAX_FAILURES = 5
LOGIN_LOCKOUT_SECONDS = 15 * 60


def _login_key(request, username):
    ip = request.META.get("REMOTE_ADDR", "")
    return f"login-failures:{ip}:{username.strip().lower()[:150]}"


class UserLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        username = request.POST.get("username", "")
        if cache.get(_login_key(request, username), 0) >= LOGIN_MAX_FAILURES:
            logger.warning(
                "Login diblokir sementara: username=%r ip=%s",
                username[:150],
                request.META.get("REMOTE_ADDR"),
            )
            # Form tanpa data, supaya tidak ada percobaan autentikasi lagi
            form = self.get_form_class()(request, initial={"username": username})
            form.cleaned_data = {}
            form.add_error(
                None, "Terlalu banyak percobaan masuk. Coba lagi dalam 15 menit."
            )
            return self.render_to_response(self.get_context_data(form=form), status=429)
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        key = _login_key(self.request, self.request.POST.get("username", ""))
        failures = cache.get(key, 0) + 1
        cache.set(key, failures, LOGIN_LOCKOUT_SECONDS)
        logger.warning(
            "Login gagal (%s/%s): username=%r ip=%s",
            failures,
            LOGIN_MAX_FAILURES,
            self.request.POST.get("username", "")[:150],
            self.request.META.get("REMOTE_ADDR"),
        )
        return super().form_invalid(form)

    def form_valid(self, form):
        cache.delete(_login_key(self.request, self.request.POST.get("username", "")))
        messages.success(self.request, "Berhasil masuk. Selamat datang lagi!")
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
            badges=get_badge_collection(saved),
            impact=get_impact_summary(saved),
        )
        return context

    def form_valid(self, form):
        messages.success(self.request, "Profil berhasil diperbarui.")
        return super().form_valid(form)


class UserPasswordChangeView(
    AuthenticatedRequiredMixin, AccountLayoutMixin, auth_views.PasswordChangeView
):
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:password_change_done")

    def form_valid(self, form):
        messages.success(self.request, "Kata sandi berhasil diganti.")
        return super().form_valid(form)


class UserPasswordChangeDoneView(
    AuthenticatedRequiredMixin, AccountLayoutMixin, auth_views.PasswordChangeDoneView
):
    template_name = "accounts/password_change_done.html"


AVATAR_MAX_BYTES = 2 * 1024 * 1024


@login_required
@require_POST
def avatar_upload(request):
    """Replace the signed-in user's profile picture (the page crops it to a square
    before sending, so this only checks that it's a real, small image)."""

    file = request.FILES.get("avatar")
    if file is None:
        return JsonResponse(
            {"error": f"Pilih gambar {IMAGE_TYPES_LABEL} dulu, ya."}, status=400
        )

    try:
        file = clean_image_upload(file, AVATAR_MAX_BYTES)
    except ValidationError as error:
        return JsonResponse({"error": error.messages[0]}, status=400)

    user = request.user
    previous = user.avatar.name
    user.avatar = file
    user.save(update_fields=["avatar", "updated_at"])
    if previous:
        user.avatar.storage.delete(previous)

    return JsonResponse({"avatar_url": user.avatar_url})


@login_required
@require_POST
def avatar_remove(request):
    user = request.user
    previous = user.avatar.name
    if previous:
        user.avatar = ""
        user.save(update_fields=["avatar", "updated_at"])
        user.avatar.storage.delete(previous)
    return JsonResponse({"avatar_url": ""})


@login_required
@require_POST
def featured_badge(request):
    """Pilih lencana yang tampil di samping nama (kosong untuk melepas)."""
    from apps.challenges.services import set_featured_badge

    raw = request.POST.get("user_badge", "").strip()
    chosen = int(raw) if raw.isdigit() else None
    updated = set_featured_badge(request.user, chosen)
    if chosen and not updated:
        message = "Pilih salah satu lencana yang sudah kamu dapat."
        if request.headers.get("Accept", "").startswith("application/json"):
            return JsonResponse({"error": message}, status=400)
        messages.error(request, message)
    elif request.headers.get("Accept", "").startswith("application/json"):
        return JsonResponse({"featured": chosen})
    else:
        messages.success(
            request,
            "Lencana terpasang di samping namamu."
            if chosen
            else "Lencana utama dilepas.",
        )
    return redirect(reverse("accounts:profile") + "#badges")
