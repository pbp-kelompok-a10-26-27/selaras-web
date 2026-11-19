from rest_framework import serializers

from .models import Ticket


class TicketListSerializer(serializers.ModelSerializer):
    requester_name = serializers.CharField(
        source="requester.display_name", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    priority_display = serializers.CharField(
        source="get_priority_display", read_only=True
    )

    class Meta:
        model = Ticket
        fields = [
            "id",
            "subject",
            "description",
            "status",
            "status_display",
            "priority",
            "priority_display",
            "requester_name",
            "created_at",
        ]
