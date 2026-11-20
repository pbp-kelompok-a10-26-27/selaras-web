from django.db import transaction
from django.urls import reverse
from rest_framework import serializers

from .models import Ticket, TicketAttachment, TicketMessage
from .services import save_attachments, validate_attachments
from .views import (
    MESSAGE_MAX_LENGTH,
    TICKET_DESCRIPTION_MAX_LENGTH,
    can_post_message,
    can_reply_to_ticket,
)

REPLY_PREVIEW_LENGTH = 160


def user_brief(user) -> dict | None:
    """Just enough about a person to show their name and role, never contact data."""
    if user is None:
        return None
    return {"name": user.display_name, "role": user.get_role_display()}


class TicketListSerializer(serializers.ModelSerializer):
    requester_name = serializers.CharField(
        source="requester.display_name", read_only=True
    )
    assignee = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    priority_display = serializers.CharField(
        source="get_priority_display", read_only=True
    )
    messages_count = serializers.SerializerMethodField()

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
            "assignee",
            "messages_count",
            "created_at",
            "updated_at",
        ]

    def get_assignee(self, ticket):
        return user_brief(ticket.assigned_to)

    def get_messages_count(self, ticket) -> int:
        # The list view annotates this; fall back to a query for a lone ticket
        count = getattr(ticket, "messages_count", None)
        return ticket.messages.count() if count is None else count


class AttachmentSerializer(serializers.ModelSerializer):
    kind = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    class Meta:
        model = TicketAttachment
        fields = ["id", "kind", "url"]

    def get_kind(self, attachment) -> str:
        return "link" if attachment.is_link else "file"

    def get_url(self, attachment) -> str:
        # Uploads are private: they are fetched through a permission-checked
        # endpoint (send the token header), never a public media URL.
        if attachment.is_link:
            return attachment.url
        path = reverse("helpdesk_drf:attachment-download", args=[attachment.pk])
        request = self.context.get("request")
        return request.build_absolute_uri(path) if request else path


class TicketDetailSerializer(TicketListSerializer):
    requester = serializers.SerializerMethodField()
    attachments = AttachmentSerializer(many=True, read_only=True)
    can_reply = serializers.SerializerMethodField()

    class Meta(TicketListSerializer.Meta):
        fields = [
            *TicketListSerializer.Meta.fields,
            "requester",
            "attachments",
            "can_reply",
            "closed_at",
        ]

    def get_requester(self, ticket):
        return user_brief(ticket.requester)

    def get_can_reply(self, ticket) -> bool:
        user = self.context["request"].user
        return can_reply_to_ticket(ticket) and can_post_message(user, ticket)


class TicketCreateSerializer(serializers.ModelSerializer):
    """New ticket. Send as multipart to include screenshots: ``attachments`` (image
    files, repeat the field) and ``image_links`` (URLs, repeat the field); five
    images or links in total."""

    description = serializers.CharField(max_length=TICKET_DESCRIPTION_MAX_LENGTH)
    attachments = serializers.ListField(
        child=serializers.FileField(), required=False, write_only=True
    )
    image_links = serializers.ListField(
        child=serializers.CharField(allow_blank=True), required=False, write_only=True
    )

    class Meta:
        model = Ticket
        fields = ["subject", "description", "priority", "attachments", "image_links"]

    def validate(self, attrs):
        files = attrs.pop("attachments", [])
        links = [link for link in attrs.pop("image_links", []) if link.strip()]
        files, links, errors = validate_attachments(files, links)
        if errors:
            raise serializers.ValidationError({"attachments": errors})
        attrs["_files"], attrs["_links"] = files, links
        return attrs

    def create(self, validated_data):
        files = validated_data.pop("_files")
        links = validated_data.pop("_links")
        with transaction.atomic():
            ticket = Ticket.objects.create(
                requester=self.context["request"].user, **validated_data
            )
            save_attachments(ticket, files, links)
        ticket.messages_count = 0  # brand new, so nothing to query
        return ticket


class ReplyPreviewSerializer(serializers.ModelSerializer):
    """The quoted message shown above a reply."""

    author_name = serializers.SerializerMethodField()
    excerpt = serializers.SerializerMethodField()

    class Meta:
        model = TicketMessage
        fields = ["id", "author_name", "is_admin_response", "excerpt"]

    def get_author_name(self, message) -> str:
        return message.author.display_name

    def get_excerpt(self, message) -> str:
        return message.message[:REPLY_PREVIEW_LENGTH]


class TicketMessageSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    is_own = serializers.SerializerMethodField()
    reply_to = ReplyPreviewSerializer(read_only=True)

    class Meta:
        model = TicketMessage
        fields = [
            "id",
            "author",
            "is_admin_response",
            "is_own",
            "message",
            "reply_to",
            "created_at",
        ]

    def get_author(self, message):
        return user_brief(message.author)

    def get_is_own(self, message) -> bool:
        return message.author_id == self.context["request"].user.id


class TicketMessageCreateSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=MESSAGE_MAX_LENGTH)
    reply_to = serializers.IntegerField(required=False, allow_null=True)

    def validate_reply_to(self, value):
        if value is None:
            return None
        # The quoted message must belong to this same ticket
        quoted = (
            TicketMessage.objects.select_related("author")
            .filter(ticket=self.context["ticket"], id=value)
            .first()
        )
        if quoted is None:
            raise serializers.ValidationError("Pesan yang kamu balas sudah tidak ada.")
        return quoted

    def create(self, validated_data):
        user = self.context["request"].user
        return TicketMessage.objects.create(
            ticket=self.context["ticket"],
            author=user,
            is_admin_response=user.is_admin,
            message=validated_data["message"],
            reply_to=validated_data.get("reply_to"),
        )
