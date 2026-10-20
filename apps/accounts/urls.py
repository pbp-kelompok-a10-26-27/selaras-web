from django.contrib.auth import views as auth_views
from django.urls import path
from django.urls import reverse_lazy

from .views import (
    ProfileView,
    RegisterView,
    UserLoginView,
    UserPasswordChangeDoneView,
    UserPasswordChangeView,
)

app_name = "accounts"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", UserLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("password/change/", UserPasswordChangeView.as_view(), name="password_change"),
    path("password/change/done/", UserPasswordChangeDoneView.as_view(), name="password_change_done"),
    path("password/reset/", auth_views.PasswordResetView.as_view(
        template_name="accounts/password_reset.html",
        email_template_name="accounts/password_reset_email.txt",
        success_url=reverse_lazy("accounts:password_reset_done"),
    ), name="password_reset"),
    path("password/reset/done/", auth_views.PasswordResetDoneView.as_view(
        template_name="accounts/password_reset_done.html",
    ), name="password_reset_done"),
    path("password/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="accounts/password_reset_confirm.html",
        success_url=reverse_lazy("accounts:password_reset_complete"),
    ), name="password_reset_confirm"),
    path("password/reset/complete/", auth_views.PasswordResetCompleteView.as_view(
        template_name="accounts/password_reset_complete.html",
    ), name="password_reset_complete"),
]
