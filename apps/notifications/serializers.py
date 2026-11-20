from rest_framework import serializers

from .models import Notification


def safe_site_path(value: str) -> str:
    """Notification links are web paths ("/feed/"). Anything else (another site,
    a protocol-relative "//host", javascript:) is never handed to the app."""
    if value.startswith("/") and not value.startswith(("//", "/\\")):
        return value
    return ""


class NotificationSerializer(serializers.ModelSerializer):
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    actor_name = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()
    is_read = serializers.BooleanField(read_only=True)
    icon = serializers.CharField(read_only=True)
    tone = serializers.CharField(read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "kind",
            "kind_display",
            "title",
            "message",
            "url",
            "icon",
            "tone",
            "actor_name",
            "is_read",
            "read_at",
            "created_at",
        ]

    def get_actor_name(self, notification):
        actor = notification.actor
        return actor.display_name if actor else None

    def get_url(self, notification) -> str:
        return safe_site_path(notification.url)
