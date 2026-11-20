from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.challenges.models import Badge, Challenge, UserBadge
from apps.challenges.serializers import BadgeSerializer
from apps.core.validators import clean_image_upload

from .models import User

AVATAR_MAX_BYTES = 2 * 1024 * 1024


def _absolute_avatar_url(user, request) -> str:
    """Mobile clients have no site origin, so avatar links must be absolute."""
    url = user.avatar_url
    return request.build_absolute_uri(url) if url and request else url


def _normalize_email(value: str, instance: User | None = None) -> str:
    email = value.strip().lower()
    taken = User.objects.filter(email__iexact=email)
    if instance is not None:
        taken = taken.exclude(pk=instance.pk)
    if taken.exists():
        raise serializers.ValidationError("Email ini sudah terdaftar.")
    return email


class UserSerializer(serializers.ModelSerializer):
    """The signed-in user's own profile."""

    display_name = serializers.ReadOnlyField()
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "display_name",
            "bio",
            "avatar_url",
            "role",
            "date_joined",
        ]
        read_only_fields = ["id", "username", "role", "date_joined"]

    def get_avatar_url(self, user) -> str:
        return _absolute_avatar_url(user, self.context.get("request"))

    def validate_email(self, value):
        return _normalize_email(value, self.instance)


class ProfileUpdateSerializer(UserSerializer):
    """Same shape as the profile, but only these fields can be written
    (never role / is_staff), mirroring ProfileForm."""

    class Meta(UserSerializer.Meta):
        read_only_fields = [
            field
            for field in UserSerializer.Meta.fields
            if field not in ("first_name", "last_name", "email", "bio")
        ]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    password_confirm = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )

    class Meta:
        model = User
        fields = ["username", "email", "password", "password_confirm"]

    def validate_email(self, value):
        return _normalize_email(value)

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError(
                {"password_confirm": "Kedua kata sandi tidak sama."}
            )
        candidate = User(username=attrs["username"], email=attrs["email"])
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"password": error.messages}) from error
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)  # role defaults to User


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"),
            username=attrs["username"],
            password=attrs["password"],
        )
        if user is None or not user.is_active:
            raise serializers.ValidationError(
                "Nama pengguna atau kata sandi salah.", code="authorization"
            )
        attrs["user"] = user
        return attrs


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )
    new_password = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )
    new_password_confirm = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )

    def validate_old_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Kata sandi lama salah.")
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": "Kedua kata sandi tidak sama."}
            )
        try:
            validate_password(attrs["new_password"], user=self.context["request"].user)
        except DjangoValidationError as error:
            raise serializers.ValidationError(
                {"new_password": error.messages}
            ) from error
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class AvatarUploadSerializer(serializers.Serializer):
    avatar = serializers.FileField()

    def validate_avatar(self, file):
        # Django ValidationError is converted to a 400 by DRF
        return clean_image_upload(file, AVATAR_MAX_BYTES)


class FeaturedBadgeSerializer(serializers.Serializer):
    # UserBadge id (from /me/badges/), or null to unpin
    user_badge = serializers.IntegerField(allow_null=True)


class BadgeChallengeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Challenge
        fields = ["id", "title", "slug"]


class EarnedBadgeSerializer(serializers.ModelSerializer):
    badge = BadgeSerializer(read_only=True)
    challenge = BadgeChallengeSerializer(read_only=True)

    class Meta:
        model = UserBadge
        fields = ["id", "badge", "challenge", "awarded_at", "is_featured"]


class LockedBadgeSerializer(BadgeSerializer):
    challenges = serializers.SerializerMethodField()

    class Meta(BadgeSerializer.Meta):
        model = Badge
        fields = [*BadgeSerializer.Meta.fields, "challenges"]

    def get_challenges(self, badge):
        # set by services.get_badge_collection: published challenges only
        return BadgeChallengeSerializer(badge.open_challenges, many=True).data
