from django.urls import path

from .api_views import (
    AvatarAPIView,
    BadgeCollectionAPIView,
    FeaturedBadgeAPIView,
    LoginAPIView,
    LogoutAPIView,
    MeAPIView,
    PasswordChangeAPIView,
    PasswordResetAPIView,
    ProfileSummaryAPIView,
    RegisterAPIView,
)

app_name = "accounts_drf"

urlpatterns = [
    # Auth
    path("register/", RegisterAPIView.as_view(), name="register"),
    path("login/", LoginAPIView.as_view(), name="login"),
    path("logout/", LogoutAPIView.as_view(), name="logout"),
    path("password/change/", PasswordChangeAPIView.as_view(), name="password-change"),
    path("password/reset/", PasswordResetAPIView.as_view(), name="password-reset"),
    # Profile
    path("me/", MeAPIView.as_view(), name="me"),
    path("me/summary/", ProfileSummaryAPIView.as_view(), name="me-summary"),
    path("me/avatar/", AvatarAPIView.as_view(), name="me-avatar"),
    # Badges
    path("me/badges/", BadgeCollectionAPIView.as_view(), name="me-badges"),
    path(
        "me/badges/featured/",
        FeaturedBadgeAPIView.as_view(),
        name="me-badges-featured",
    ),
]
