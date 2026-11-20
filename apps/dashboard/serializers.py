from django.db.models import Count, Q, Sum
from django.urls import reverse
from rest_framework import serializers

from apps.accounts.models import User
from apps.articles.models import Article
from apps.challenges.models import Badge, Challenge, CommunityGoal
from apps.challenges.services import goal_progress, impact_summary
from apps.donations.models import Campaign, Donation
from apps.donations.services import (
    campaign_accepts_donations,
    campaign_progress_percent,
)
from apps.feeds.models import Comment, Post
from apps.helpdesk.models import Ticket, TicketAttachment, TicketMessage
from apps.helpdesk.views import can_post_message, can_reply_to_ticket

from .views import ADMIN_STATUS_ACTIONS, _user_guard, can_manage_ticket

REPLY_PREVIEW_LENGTH = 160
CONTENT_PREVIEW_LENGTH = 120


def user_brief(user) -> dict | None:
    if user is None:
        return None
    return {
        "id": str(user.pk),
        "name": user.display_name,
        "role": user.get_role_display(),
    }


def _absolute(request, path: str) -> str:
    return request.build_absolute_uri(path) if request and path else path


def _count(obj, attr, fallback):
    """List views annotate counts; for a lone object fall back to a query."""
    value = getattr(obj, attr, None)
    return fallback() if value is None else value


# ---------------------------------------------------------------- helpdesk


class AdminTicketSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    priority_display = serializers.CharField(
        source="get_priority_display", read_only=True
    )
    requester = serializers.SerializerMethodField()
    assignee = serializers.SerializerMethodField()
    messages_count = serializers.SerializerMethodField()
    is_assigned_to_me = serializers.SerializerMethodField()
    can_assign_to_me = serializers.SerializerMethodField()
    can_reply = serializers.SerializerMethodField()

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
            "requester",
            "assignee",
            "messages_count",
            "is_assigned_to_me",
            "can_assign_to_me",
            "can_reply",
            "created_at",
            "updated_at",
        ]

    @property
    def admin(self):
        return self.context["request"].user

    def get_requester(self, ticket):
        brief = user_brief(ticket.requester)
        # Admins may contact the requester
        return {**brief, "email": ticket.requester.email} if brief else None

    def get_assignee(self, ticket):
        return user_brief(ticket.assigned_to)

    def get_messages_count(self, ticket) -> int:
        return _count(ticket, "messages_count", ticket.messages.count)

    def get_is_assigned_to_me(self, ticket) -> bool:
        return ticket.assigned_to_id == self.admin.id

    def get_can_assign_to_me(self, ticket) -> bool:
        return ticket.assigned_to_id is None

    def get_can_reply(self, ticket) -> bool:
        return can_post_message(self.admin, ticket) and can_reply_to_ticket(ticket)


class AdminAttachmentSerializer(serializers.ModelSerializer):
    kind = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    class Meta:
        model = TicketAttachment
        fields = ["id", "kind", "url"]

    def get_kind(self, attachment) -> str:
        return "link" if attachment.is_link else "file"

    def get_url(self, attachment) -> str:
        if attachment.is_link:
            return attachment.url
        path = reverse("dashboard_drf:attachment-download", args=[attachment.pk])
        return _absolute(self.context.get("request"), path)


class AdminTicketDetailSerializer(AdminTicketSerializer):
    attachments = AdminAttachmentSerializer(many=True, read_only=True)
    can_update_status = serializers.SerializerMethodField()

    class Meta(AdminTicketSerializer.Meta):
        fields = [
            *AdminTicketSerializer.Meta.fields,
            "closed_at",
            "attachments",
            "can_update_status",
        ]

    def get_can_update_status(self, ticket) -> bool:
        return can_manage_ticket(self.admin, ticket)


class AdminTicketStatusSerializer(serializers.Serializer):
    # Only these three can be set; "open" is a ticket's starting state
    status = serializers.ChoiceField(
        choices=[(value, label) for value, label, _icon, _color in ADMIN_STATUS_ACTIONS]
    )


class ReplyPreviewSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    excerpt = serializers.SerializerMethodField()

    class Meta:
        model = TicketMessage
        fields = ["id", "author_name", "is_admin_response", "excerpt"]

    def get_author_name(self, message) -> str:
        return message.author.display_name

    def get_excerpt(self, message) -> str:
        return message.message[:REPLY_PREVIEW_LENGTH]


class AdminTicketMessageSerializer(serializers.ModelSerializer):
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


class AdminTicketMessageCreateSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=5000)
    reply_to = serializers.IntegerField(required=False, allow_null=True)

    def validate_reply_to(self, value):
        if value is None:
            return None
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


# ------------------------------------------------------------- challenges


class ChallengeAdminSerializer(serializers.ModelSerializer):
    badge = serializers.PrimaryKeyRelatedField(
        queryset=Badge.objects.all(), required=False, allow_null=True
    )
    status = serializers.ReadOnlyField()
    duration_days = serializers.ReadOnlyField()
    participants_count = serializers.SerializerMethodField()

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
            "is_published",
            "status",
            "duration_days",
            "participants_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["slug"]

    def get_participants_count(self, challenge) -> int:
        return _count(challenge, "participants_count", challenge.participations.count)

    def validate(self, attrs):
        # Same rules as challenges.forms.ChallengeForm, with PATCH falling back to
        # what's already saved
        current = self.instance

        def value(name, default=None):
            return attrs.get(name, getattr(current, name, default))

        goal_type = value("goal_type") or Challenge.GoalType.CHECK_IN
        attrs["goal_type"] = goal_type
        if goal_type == Challenge.GoalType.CHECK_IN:
            # Check-in challenges use their length in days as the target
            attrs["goal_target"] = None
        elif not value("goal_target"):
            raise serializers.ValidationError(
                {"goal_target": "Isi angka yang harus dicapai peserta."}
            )

        start, end = value("start_date"), value("end_date")
        if start and end and end < start:
            raise serializers.ValidationError(
                {"end_date": "Tanggal selesai tidak boleh sebelum tanggal mulai."}
            )
        return attrs


class BadgeAdminSerializer(serializers.ModelSerializer):
    name = serializers.CharField(max_length=100)
    challenge_count = serializers.SerializerMethodField()
    holder_count = serializers.SerializerMethodField()

    class Meta:
        model = Badge
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "icon",
            "tone",
            "challenge_count",
            "holder_count",
        ]
        read_only_fields = ["slug"]

    def validate_name(self, value):
        name = value.strip()
        duplicate = Badge.objects.filter(name__iexact=name)
        if self.instance:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise serializers.ValidationError("Lencana dengan nama ini sudah ada.")
        return name

    def get_challenge_count(self, badge) -> int:
        return _count(badge, "challenge_count", badge.challenges.count)

    def get_holder_count(self, badge) -> int:
        return _count(badge, "holder_count", badge.awarded_to.count)


class CommunityGoalAdminSerializer(serializers.ModelSerializer):
    target = serializers.IntegerField(min_value=1)
    status = serializers.ReadOnlyField()
    progress = serializers.SerializerMethodField()

    class Meta:
        model = CommunityGoal
        fields = [
            "id",
            "title",
            "description",
            "goal_type",
            "target",
            "start_date",
            "end_date",
            "is_published",
            "status",
            "progress",
        ]

    def get_progress(self, goal) -> dict:
        data = goal_progress(goal)
        return {
            "current": data["current"],
            "percent": data["percent"],
            "reached": data["reached"],
            "is_money": data["is_money"],
            "unit": str(data["unit"]),
            "days_left": data["days_left"],
        }

    def validate(self, attrs):
        current = self.instance
        start = attrs.get("start_date", getattr(current, "start_date", None))
        end = attrs.get("end_date", getattr(current, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError(
                {"end_date": "Tanggal selesai tidak boleh sebelum tanggal mulai."}
            )
        return attrs


# ------------------------------------------------------------------- users


class AdminUserSerializer(serializers.ModelSerializer):
    display_name = serializers.ReadOnlyField()
    avatar_url = serializers.SerializerMethodField()
    # Annotated by the list view only
    post_count = serializers.IntegerField(read_only=True)
    article_count = serializers.IntegerField(read_only=True)
    # Why this account can't be changed by the signed-in admin (or null)
    guard = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "display_name",
            "avatar_url",
            "role",
            "is_active",
            "date_joined",
            "last_login",
            "post_count",
            "article_count",
            "guard",
        ]

    def get_avatar_url(self, user) -> str:
        return _absolute(self.context.get("request"), user.avatar_url)

    def get_guard(self, user):
        return _user_guard(self.context["request"].user, user)


class AdminUserUpdateSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=User.Role.choices, required=False)
    is_active = serializers.BooleanField(required=False)


class PostModerationSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    challenge = serializers.SerializerMethodField()
    like_count = serializers.IntegerField(read_only=True)
    comment_count = serializers.IntegerField(read_only=True)
    image_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Post
        fields = [
            "id",
            "author",
            "content",
            "challenge",
            "like_count",
            "comment_count",
            "image_count",
            "created_at",
        ]

    def get_author(self, post):
        return user_brief(post.author)

    def get_challenge(self, post):
        challenge = post.challenge
        return {"id": challenge.pk, "title": challenge.title} if challenge else None


class CommentModerationSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    post = serializers.SerializerMethodField()
    parent = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ["id", "author", "content", "post", "parent", "created_at"]

    def get_author(self, comment):
        return user_brief(comment.author)

    def get_post(self, comment) -> dict:
        return {
            "id": str(comment.post_id),
            "excerpt": comment.post.content[:CONTENT_PREVIEW_LENGTH],
            "author_name": comment.post.author.display_name,
        }

    def get_parent(self, comment):
        parent = comment.parent
        if parent is None:
            return None
        return {"id": str(parent.pk), "author_name": parent.author.display_name}


# ---------------------------------------------------------------- articles


class AdminArticleSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    author = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    read_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Article
        fields = [
            "id",
            "title",
            "slug",
            "summary",
            "status",
            "status_display",
            "author",
            "category",
            "read_count",
            "review_note",
            "submitted_at",
            "published_at",
            "updated_at",
        ]

    def get_author(self, article):
        return user_brief(article.author)

    def get_category(self, article) -> dict:
        return {"id": article.category_id, "name": article.category.name}


# --------------------------------------------------------------- donations


class AdminCampaignSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    approved_total = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    progress_percent = serializers.SerializerMethodField()
    accepting_donations = serializers.SerializerMethodField()
    pending_count = serializers.IntegerField(read_only=True)
    donor_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Campaign
        fields = [
            "id",
            "title",
            "slug",
            "status",
            "status_display",
            "target_amount",
            "approved_total",
            "progress_percent",
            "accepting_donations",
            "pending_count",
            "donor_count",
            "starts_at",
            "ends_at",
            "created_at",
        ]

    def get_progress_percent(self, campaign) -> float:
        return round(float(campaign_progress_percent(campaign)), 1)

    def get_accepting_donations(self, campaign) -> bool:
        return campaign_accepts_donations(campaign)


class DonationBriefSerializer(serializers.ModelSerializer):
    campaign = serializers.CharField(source="campaign.title", read_only=True)

    class Meta:
        model = Donation
        fields = ["id", "campaign", "amount", "status", "created_at"]


def user_activity(member) -> dict:
    """What the user detail screen shows below the profile."""
    donations = Donation.objects.filter(donor=member)
    donated = donations.aggregate(
        approved=Sum("amount", filter=Q(status=Donation.Status.APPROVED)),
        pending=Count("id", filter=Q(status=Donation.Status.PENDING)),
    )
    return {
        "impact": impact_summary(member),
        "donations_approved_amount": donated["approved"] or 0,
        "donations_pending": donated["pending"],
        "tickets": Ticket.objects.filter(requester=member).count(),
    }
