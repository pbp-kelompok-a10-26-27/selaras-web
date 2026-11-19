from rest_framework import serializers

from .models import Badge, Challenge


class BadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = ["id", "name", "slug", "description", "icon", "tone"]


class ChallengeListSerializer(serializers.ModelSerializer):
    badge = BadgeSerializer(read_only=True)
    status = serializers.ReadOnlyField()
    duration_days = serializers.ReadOnlyField()

    class Meta:
        model = Challenge
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "start_date",
            "end_date",
            "goal_type",
            "goal_target",
            "badge",
            "status",
            "duration_days",
        ]
