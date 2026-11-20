import logging

from django.contrib.auth.forms import PasswordResetForm
from django.core.cache import cache
from rest_framework import generics, status
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    AvatarUploadSerializer,
    EarnedBadgeSerializer,
    FeaturedBadgeSerializer,
    LockedBadgeSerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    PasswordResetRequestSerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    UserSerializer,
)
from .services import (
    get_badge_collection,
    get_impact_summary,
    get_profile_completion,
    get_profile_stats,
)
from .views import LOGIN_LOCKOUT_SECONDS, LOGIN_MAX_FAILURES, _login_key

logger = logging.getLogger(__name__)


class AuthenticatedAPIView(APIView):
    """Base for endpoints that need a signed-in user.

    Flutter sends ``Authorization: Token <key>``. Token auth is used instead of the
    project-wide SessionAuthentication, which would demand a CSRF token from a
    client that has no cookies.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]


def _auth_payload(user, request, token=None) -> dict:
    token = token or Token.objects.get_or_create(user=user)[0]
    return {
        "token": token.key,
        "user": UserSerializer(user, context={"request": request}).data,
    }


# --------------------------------------------------------------------- auth


class RegisterAPIView(generics.CreateAPIView):
    """POST: create an account (role is always "user") and return its token."""

    serializer_class = RegisterSerializer
    authentication_classes = []
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(_auth_payload(user, request), status=status.HTTP_201_CREATED)


class LoginAPIView(APIView):
    """POST: exchange username + password for a token.

    Shares the web login's lockout (5 failures per IP + username, 15 minutes).
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        username = str(request.data.get("username", ""))
        key = _login_key(request, username)

        if cache.get(key, 0) >= LOGIN_MAX_FAILURES:
            logger.warning(
                "API login diblokir sementara: username=%r ip=%s",
                username[:150],
                request.META.get("REMOTE_ADDR"),
            )
            return Response(
                {"detail": "Terlalu banyak percobaan masuk. Coba lagi dalam 15 menit."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        serializer = LoginSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            failures = cache.get(key, 0) + 1
            cache.set(key, failures, LOGIN_LOCKOUT_SECONDS)
            logger.warning(
                "API login gagal (%s/%s): username=%r ip=%s",
                failures,
                LOGIN_MAX_FAILURES,
                username[:150],
                request.META.get("REMOTE_ADDR"),
            )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        cache.delete(key)
        return Response(_auth_payload(serializer.validated_data["user"], request))


class LogoutAPIView(AuthenticatedAPIView):
    """POST: revoke the token used for this request."""

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordChangeAPIView(AuthenticatedAPIView):
    """POST: change the password. The old token is revoked and a new one returned,
    so other devices must sign in again."""

    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password", "updated_at"])
        Token.objects.filter(user=request.user).delete()
        return Response(_auth_payload(request.user, request))


class PasswordResetAPIView(APIView):
    """POST: email a reset link. Always answers 200 so it can't be used to find out
    which emails are registered."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        form = PasswordResetForm({"email": serializer.validated_data["email"]})
        if form.is_valid():
            form.save(
                request=request._request,
                email_template_name="accounts/password_reset_email.txt",
            )
        return Response(
            {"detail": "Jika email terdaftar, tautan pengaturan ulang sudah dikirim."}
        )


# ------------------------------------------------------------------ profile


class MeAPIView(AuthenticatedAPIView, generics.RetrieveUpdateAPIView):
    """GET: the signed-in user's profile.

    PATCH: edit first_name, last_name, email, bio.
    """

    http_method_names = ["get", "patch", "head", "options"]

    def get_serializer_class(self):
        return (
            UserSerializer if self.request.method == "GET" else ProfileUpdateSerializer
        )

    def get_object(self):
        return self.request.user


class ProfileSummaryAPIView(AuthenticatedAPIView):
    """GET: profile completion, headline stats and activity totals."""

    def get(self, request):
        stats = [
            {key: value for key, value in stat.items() if key != "href"}
            for stat in get_profile_stats(request.user)
        ]
        return Response(
            {
                "completion": get_profile_completion(request.user),
                "stats": stats,
                "impact": get_impact_summary(request.user),
            }
        )


class AvatarAPIView(AuthenticatedAPIView):
    """POST (multipart, field ``avatar``): replace the picture. DELETE: remove it."""

    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = AvatarUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        previous = user.avatar.name
        user.avatar = serializer.validated_data["avatar"]
        user.save(update_fields=["avatar", "updated_at"])
        if previous:
            user.avatar.storage.delete(previous)
        return Response(UserSerializer(user, context={"request": request}).data)

    def delete(self, request):
        user = request.user
        previous = user.avatar.name
        if previous:
            user.avatar = ""
            user.save(update_fields=["avatar", "updated_at"])
            user.avatar.storage.delete(previous)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------- badges


class BadgeCollectionAPIView(AuthenticatedAPIView):
    """GET: badges the user has earned, and the ones still to unlock."""

    def get(self, request):
        collection = get_badge_collection(request.user)
        featured = collection["featured"]
        return Response(
            {
                "earned": EarnedBadgeSerializer(collection["earned"], many=True).data,
                "locked": LockedBadgeSerializer(collection["locked"], many=True).data,
                "featured": featured.pk if featured else None,
                "total": collection["total"],
            }
        )


class FeaturedBadgeAPIView(AuthenticatedAPIView):
    """POST ``{"user_badge": <id>}``: show that badge beside the name.
    ``{"user_badge": null}`` removes it."""

    def post(self, request):
        from apps.challenges.services import set_featured_badge

        serializer = FeaturedBadgeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        chosen = serializer.validated_data["user_badge"]

        updated = set_featured_badge(request.user, chosen)
        if chosen and not updated:
            return Response(
                {"user_badge": ["Pilih salah satu lencana yang sudah kamu dapat."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"featured": chosen})
