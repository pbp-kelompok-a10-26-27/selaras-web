from datetime import timedelta

from django.db import transaction
from django.db.models import Case, Count, Q, Sum, Value, When
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.text import Truncator
from rest_framework import generics, status
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from apps.accounts.api_views import AuthenticatedAPIView
from apps.accounts.models import User
from apps.articles.models import Article, ArticleCategory
from apps.challenges.models import (
    Badge,
    Challenge,
    ChallengeParticipation,
    CommunityGoal,
)
from apps.core.permissions import is_admin
from apps.donations.models import Campaign, Donation
from apps.donations.services import campaign_queryset
from apps.feeds.models import Comment, Like, Post
from apps.feeds.views import delete_post
from apps.helpdesk.models import Ticket, TicketAttachment
from apps.helpdesk.views import can_post_message, can_reply_to_ticket
from apps.notifications.models import Notification
from apps.notifications.services import notify

from .serializers import (
    AdminArticleSerializer,
    AdminCampaignSerializer,
    AdminTicketDetailSerializer,
    AdminTicketMessageCreateSerializer,
    AdminTicketMessageSerializer,
    AdminTicketSerializer,
    AdminTicketStatusSerializer,
    AdminUserSerializer,
    AdminUserUpdateSerializer,
    BadgeAdminSerializer,
    ChallengeAdminSerializer,
    CommentModerationSerializer,
    CommunityGoalAdminSerializer,
    DonationBriefSerializer,
    PostModerationSerializer,
    user_activity,
)
from .views import (
    ARTICLE_STATUS_FILTERS,
    CAMPAIGN_STATUS_FILTERS,
    FEED_PERIODS,
    LIST_PER_PAGE,
    POST_SORTS,
    USER_ROLE_FILTERS,
    USER_SORTS,
    USER_STATE_FILTERS,
    _choice,
    _user_guard,
    apply_admin_ticket_query,
    build_admin_ticket_stats,
    build_overview,
    can_manage_ticket,
    parse_admin_ticket_query,
)

# ============================================================================ base


class IsAdminRole(BasePermission):
    message = "Hanya admin yang bisa mengakses ini."

    def has_permission(self, request, view):
        return is_admin(request.user)


class AdminAPIView(AuthenticatedAPIView):
    """Everything in the dashboard API: a valid token (401 otherwise) that belongs
    to an admin (403 otherwise)."""

    permission_classes = [IsAuthenticated, IsAdminRole]


class AdminPagination(PageNumberPagination):
    page_size = LIST_PER_PAGE
    page_size_query_param = "page_size"
    max_page_size = 100


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Permintaan bertentangan dengan keadaan saat ini."
    default_code = "conflict"


class MetricsListMixin:
    """Adds the screen's headline numbers (``get_metrics``) to a paginated list as
    ``metrics``, next to ``count`` / ``results``."""

    def get_metrics(self) -> dict | None:
        return None

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        metrics = self.get_metrics()
        if metrics is not None and isinstance(response.data, dict):
            response.data = {**response.data, "metrics": metrics}
        return response


def _search(request) -> str:
    return request.query_params.get("search", "").strip()[:100]


# ====================================================================== overview


class OverviewAPIView(AdminAPIView):
    """GET: what needs doing now, plus the last 7 days of activity."""

    def get(self, request):
        overview = build_overview(request.user)
        todo = [
            {key: value for key, value in item.items() if key not in ("href", "cta")}
            for item in overview["todo"]
        ]
        return Response(
            {"helpdesk": overview["helpdesk"], "todo": todo, "week": overview["week"]}
        )


# ===================================================================== helpdesk


class AdminTicketListAPIView(AdminAPIView, generics.ListAPIView):
    """GET: every ticket. Query: ``status``, ``priority``, ``assignment``
    (me / unassigned / others), ``search`` (also matches people and ticket id),
    ``sort`` (-created_at, created_at, -priority, priority), ``page``, ``page_size``."""

    serializer_class = AdminTicketSerializer
    pagination_class = AdminPagination

    def get_queryset(self):
        query = parse_admin_ticket_query(self.request)
        return (
            apply_admin_ticket_query(Ticket.objects.all(), query, self.request.user)
            .select_related("requester", "assigned_to")
            .annotate(messages_count=Count("messages"))
        )


class AdminTicketStatsAPIView(AdminAPIView):
    """GET: helpdesk KPIs, status counts and open workload by priority."""

    def get(self, request):
        return Response(build_admin_ticket_stats(request.user))


def _ticket_queryset():
    return Ticket.objects.select_related("requester", "assigned_to").annotate(
        messages_count=Count("messages")
    )


class AdminTicketDetailAPIView(AdminAPIView, generics.RetrieveUpdateDestroyAPIView):
    """GET: a ticket with its screenshots.

    PATCH ``{"status": "in_progress" | "resolved" | "closed"}``: only the assigned
    coordinator may change status. DELETE: any admin can delete any ticket."""

    http_method_names = ["get", "patch", "delete", "head", "options"]
    lookup_url_kwarg = "ticket_id"

    def get_queryset(self):
        return _ticket_queryset().prefetch_related("attachments")

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return AdminTicketStatusSerializer
        return AdminTicketDetailSerializer

    def partial_update(self, request, *args, **kwargs):
        serializer = AdminTicketStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data["status"]

        # Row lock, so two admins can't race on the same ticket
        with transaction.atomic():
            ticket = get_object_or_404(
                Ticket.objects.select_for_update(), id=kwargs["ticket_id"]
            )
            if not can_manage_ticket(request.user, ticket):
                raise PermissionDenied(
                    "Hanya koordinator tiket yang bisa mengubah statusnya."
                )
            if ticket.status != new_status:
                ticket.status = new_status
                # closed_at records when it was closed; reopening clears it
                ticket.closed_at = (
                    timezone.now() if new_status == Ticket.Status.CLOSED else None
                )
                ticket.save(update_fields=["status", "closed_at", "updated_at"])

        ticket = self.get_queryset().get(id=ticket.id)
        data = AdminTicketDetailSerializer(ticket, context={"request": request}).data
        return Response(data)


class AdminTicketAssignAPIView(AdminAPIView):
    """POST: take an unassigned ticket (admins only reply to their own tickets).
    409 if another admin already has it."""

    def post(self, request, ticket_id):
        with transaction.atomic():
            ticket = get_object_or_404(
                Ticket.objects.select_for_update().select_related("assigned_to"),
                id=ticket_id,
            )
            if ticket.assigned_to_id and ticket.assigned_to_id != request.user.id:
                raise Conflict(
                    f"Tiket ini sudah diambil {ticket.assigned_to.display_name}."
                )
            ticket.assigned_to = request.user
            ticket.save(update_fields=["assigned_to", "updated_at"])

        ticket = _ticket_queryset().get(id=ticket.id)
        return Response(
            AdminTicketSerializer(ticket, context={"request": request}).data
        )


class AdminTicketMessageListCreateAPIView(AdminAPIView, generics.ListCreateAPIView):
    """GET: the conversation, oldest first. POST: reply, optionally quoting a message
    with ``reply_to``. Only the assigned coordinator can reply; closed tickets take
    no replies."""

    pagination_class = None

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AdminTicketMessageCreateSerializer
        return AdminTicketMessageSerializer

    def get_queryset(self):
        ticket = get_object_or_404(Ticket, id=self.kwargs["ticket_id"])
        return ticket.messages.select_related("author", "reply_to__author")

    def create(self, request, *args, **kwargs):
        ticket = get_object_or_404(Ticket, id=kwargs["ticket_id"])
        if not can_post_message(request.user, ticket):
            raise PermissionDenied(
                "Hanya pengirim dan koordinator tiket yang bisa membalas tiket ini."
            )
        if not can_reply_to_ticket(ticket):
            raise Conflict("Tiket ini sudah ditutup dan tidak menerima balasan.")

        serializer = AdminTicketMessageCreateSerializer(
            data=request.data, context={"request": request, "ticket": ticket}
        )
        serializer.is_valid(raise_exception=True)
        message = serializer.save()
        data = AdminTicketMessageSerializer(message, context={"request": request}).data
        return Response(data, status=status.HTTP_201_CREATED)


class AdminAttachmentDownloadAPIView(AdminAPIView):
    """GET: an uploaded screenshot (send the token header)."""

    def get(self, request, attachment_id):
        attachment = get_object_or_404(TicketAttachment, id=attachment_id)
        if not attachment.file:
            raise Http404
        response = FileResponse(attachment.file.open("rb"))
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, max-age=3600"
        return response


# ================================================================== challenges

CHALLENGE_STATUS_FILTERS = ("all", "active", "upcoming", "ended", "draft")


class AdminChallengeListCreateAPIView(
    AdminAPIView, MetricsListMixin, generics.ListCreateAPIView
):
    """GET: challenges (``search``, ``status``: active / upcoming / ended / draft).
    POST: create one."""

    serializer_class = ChallengeAdminSerializer
    pagination_class = AdminPagination

    def get_queryset(self):
        params = self.request.query_params
        today = timezone.localdate()
        challenges = Challenge.objects.annotate(
            participants_count=Count("participations")
        ).order_by("-created_at")

        if search := _search(self.request):
            challenges = challenges.filter(
                Q(title__icontains=search) | Q(description__icontains=search)
            )

        match params.get("status", "all"):
            case "active":
                challenges = challenges.filter(
                    is_published=True, start_date__lte=today, end_date__gte=today
                )
            case "upcoming":
                challenges = challenges.filter(is_published=True, start_date__gt=today)
            case "ended":
                challenges = challenges.filter(is_published=True, end_date__lt=today)
            case "draft":
                challenges = challenges.filter(is_published=False)
        return challenges

    def get_metrics(self):
        today = timezone.localdate()
        return {
            "total": Challenge.objects.count(),
            "active": Challenge.objects.filter(
                is_published=True, start_date__lte=today, end_date__gte=today
            ).count(),
            "participants": ChallengeParticipation.objects.count(),
            "draft": Challenge.objects.filter(is_published=False).count(),
        }


class AdminChallengeDetailAPIView(AdminAPIView, generics.RetrieveUpdateDestroyAPIView):
    """GET / PATCH / DELETE a challenge by slug. One that already has participants
    can't be deleted (409): unpublish it instead."""

    serializer_class = ChallengeAdminSerializer
    lookup_field = "slug"
    queryset = Challenge.objects.annotate(participants_count=Count("participations"))

    def perform_destroy(self, challenge):
        if challenge.participants_count:
            raise Conflict(
                f"“{challenge.title}” tidak bisa dihapus karena sudah punya "
                f"{challenge.participants_count} peserta. Ubah jadi draf saja."
            )
        challenge.delete()


# ===================================================================== badges


class AdminBadgeListCreateAPIView(AdminAPIView, generics.ListCreateAPIView):
    """GET: every badge with how many challenges offer it and how many people own
    it. POST: create one."""

    serializer_class = BadgeAdminSerializer
    pagination_class = AdminPagination
    queryset = Badge.objects.annotate(
        challenge_count=Count("challenges", distinct=True),
        holder_count=Count("awarded_to", distinct=True),
    ).order_by("name")


class AdminBadgeDetailAPIView(AdminAPIView, generics.RetrieveUpdateDestroyAPIView):
    """GET / PATCH / DELETE a badge by slug. Owned badges can't be deleted (409):
    they are part of people's history."""

    serializer_class = BadgeAdminSerializer
    lookup_field = "slug"
    queryset = Badge.objects.annotate(
        challenge_count=Count("challenges", distinct=True),
        holder_count=Count("awarded_to", distinct=True),
    )

    def perform_destroy(self, badge):
        if badge.holder_count:
            raise Conflict(
                f"“{badge.name}” tidak bisa dihapus karena sudah dimiliki "
                f"{badge.holder_count} orang."
            )
        badge.delete()


# ===================================================================== goals


class AdminGoalListCreateAPIView(AdminAPIView, generics.ListCreateAPIView):
    """GET: community goals with live progress. POST: create one."""

    serializer_class = CommunityGoalAdminSerializer
    pagination_class = AdminPagination
    queryset = CommunityGoal.objects.order_by("-end_date")


class AdminGoalDetailAPIView(AdminAPIView, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CommunityGoalAdminSerializer
    queryset = CommunityGoal.objects.all()


# ===================================================================== users


class AdminUserListAPIView(AdminAPIView, MetricsListMixin, generics.ListAPIView):
    """GET: accounts. Query: ``search``, ``role`` (admin / user), ``state``
    (active / inactive), ``sort`` (newest, last_login, name)."""

    serializer_class = AdminUserSerializer
    pagination_class = AdminPagination

    def get_queryset(self):
        request = self.request
        role = _choice(request, "role", USER_ROLE_FILTERS)
        state = _choice(request, "state", USER_STATE_FILTERS)
        sort = _choice(request, "sort", USER_SORTS, default="newest")

        users = User.objects.annotate(
            post_count=Count("posts", distinct=True),
            article_count=Count("articles", distinct=True),
        )
        if term := _search(request):
            users = users.filter(
                Q(username__icontains=term)
                | Q(first_name__icontains=term)
                | Q(last_name__icontains=term)
                | Q(email__icontains=term)
            )
        if role != "all":
            users = users.filter(role=role)
        if state != "all":
            users = users.filter(is_active=state == "active")
        return users.order_by(*USER_SORTS[sort][2], "username")

    def get_metrics(self):
        week_ago = timezone.now() - timedelta(days=7)
        return User.objects.aggregate(
            total=Count("id"),
            admins=Count("id", filter=Q(role=User.Role.ADMIN)),
            new_week=Count("id", filter=Q(date_joined__gte=week_ago)),
            inactive=Count("id", filter=Q(is_active=False)),
        )


class AdminUserDetailAPIView(AdminAPIView, generics.RetrieveUpdateAPIView):
    """GET: an account with its activity. PATCH ``{"role": ..., "is_active": ...}``:
    change role or deactivate / reactivate (deactivated accounts can't sign in; their
    data is kept). You can't change your own account, and only a superuser can change
    a superuser."""

    http_method_names = ["get", "patch", "head", "options"]
    queryset = User.objects.all()
    lookup_url_kwarg = "user_id"
    serializer_class = AdminUserSerializer

    def retrieve(self, request, *args, **kwargs):
        member = self.get_object()
        data = dict(self.get_serializer(member).data)
        data["activity"] = user_activity(member)
        data["recent_posts"] = PostModerationSerializer(
            member.posts.select_related("author", "challenge")
            .annotate(
                like_count=Count("likes", distinct=True),
                comment_count=Count("comments", distinct=True),
                image_count=Count("images", distinct=True),
            )
            .order_by("-created_at")[:5],
            many=True,
        ).data
        data["recent_articles"] = AdminArticleSerializer(
            member.articles.select_related("author", "category").order_by(
                "-updated_at"
            )[:5],
            many=True,
        ).data
        data["recent_donations"] = DonationBriefSerializer(
            Donation.objects.filter(donor=member)
            .select_related("campaign")
            .order_by("-created_at")[:5],
            many=True,
        ).data
        return Response(data)

    def partial_update(self, request, *args, **kwargs):
        member = self.get_object()
        if problem := _user_guard(request.user, member):
            raise PermissionDenied(problem)

        serializer = AdminUserUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        changes = serializer.validated_data

        fields = [
            field for field in changes if getattr(member, field) != changes[field]
        ]
        for field in fields:
            setattr(member, field, changes[field])
        if fields:
            member.save(update_fields=[*fields, "updated_at"])
        return Response(self.get_serializer(member).data)


# ================================================================== articles


class AdminArticleListAPIView(AdminAPIView, MetricsListMixin, generics.ListAPIView):
    """GET: articles, pending review first. Query: ``search``,
    ``status`` (PENDING / PUBLISHED / REJECTED / DRAFT), ``category`` (slug)."""

    serializer_class = AdminArticleSerializer
    pagination_class = AdminPagination

    def get_queryset(self):
        request = self.request
        status_filter = _choice(request, "status", ARTICLE_STATUS_FILTERS)
        category = request.query_params.get("category", "all")

        articles = Article.objects.select_related("author", "category").annotate(
            read_count=Count("reads", distinct=True),
            # Waiting for review always comes first
            needs_review=Case(
                When(status=Article.Status.PENDING, then=Value(0)), default=Value(1)
            ),
        )
        if term := _search(request):
            articles = articles.filter(
                Q(title__icontains=term)
                | Q(summary__icontains=term)
                | Q(author__username__icontains=term)
                | Q(author__first_name__icontains=term)
                | Q(author__last_name__icontains=term)
            )
        if status_filter != "all":
            articles = articles.filter(status=status_filter)
        if category != "all" and ArticleCategory.objects.filter(slug=category).exists():
            articles = articles.filter(category__slug=category)

        return articles.order_by("needs_review", "-updated_at")

    def get_metrics(self):
        return Article.objects.aggregate(
            total=Count("id"),
            published=Count("id", filter=Q(status=Article.Status.PUBLISHED)),
            pending=Count("id", filter=Q(status=Article.Status.PENDING)),
            drafts=Count(
                "id",
                filter=Q(status__in=[Article.Status.DRAFT, Article.Status.REJECTED]),
            ),
        )


# ================================================================== donations


class AdminCampaignListAPIView(AdminAPIView, MetricsListMixin, generics.ListAPIView):
    """GET: donation campaigns with progress. Query: ``search``,
    ``status`` (PUBLISHED / DRAFT / CLOSED)."""

    serializer_class = AdminCampaignSerializer
    pagination_class = AdminPagination

    def get_queryset(self):
        request = self.request
        status_filter = _choice(request, "status", CAMPAIGN_STATUS_FILTERS)
        campaigns = campaign_queryset().annotate(
            pending_count=Count(
                "donations", filter=Q(donations__status=Donation.Status.PENDING)
            ),
            donor_count=Count(
                "donations__donor",
                filter=Q(donations__status=Donation.Status.APPROVED),
                distinct=True,
            ),
        )
        if term := _search(request):
            campaigns = campaigns.filter(
                Q(title__icontains=term) | Q(description__icontains=term)
            )
        if status_filter != "all":
            campaigns = campaigns.filter(status=status_filter)
        return campaigns.order_by("-created_at", "title")

    def get_metrics(self):
        totals = Donation.objects.aggregate(
            collected=Sum("amount", filter=Q(status=Donation.Status.APPROVED)),
            pending=Count("id", filter=Q(status=Donation.Status.PENDING)),
            pending_amount=Sum("amount", filter=Q(status=Donation.Status.PENDING)),
            donors=Count(
                "donor", filter=Q(status=Donation.Status.APPROVED), distinct=True
            ),
        )
        now = timezone.now()
        totals["open_campaigns"] = (
            Campaign.objects.filter(status=Campaign.Status.PUBLISHED)
            .filter(Q(starts_at__isnull=True) | Q(starts_at__lte=now))
            .filter(Q(ends_at__isnull=True) | Q(ends_at__gte=now))
            .count()
        )
        return totals


# ===================================================================== feeds


def _feed_metrics() -> dict:
    week_ago = timezone.now() - timedelta(days=7)
    return {
        **Post.objects.aggregate(
            posts=Count("id"),
            posts_week=Count("id", filter=Q(created_at__gte=week_ago)),
        ),
        "comments": Comment.objects.count(),
        "likes": Like.objects.count(),
    }


def _since_period(request, items):
    days = FEED_PERIODS[_choice(request, "period", FEED_PERIODS)][2]
    if days is None:
        return items
    start = timezone.localdate() - timedelta(days=days)
    return items.filter(created_at__date__gte=start)


def _author_match(term):
    return (
        Q(author__username__icontains=term)
        | Q(author__first_name__icontains=term)
        | Q(author__last_name__icontains=term)
    )


class AdminPostListAPIView(AdminAPIView, MetricsListMixin, generics.ListAPIView):
    """GET: posts for moderation. Query: ``search``, ``period`` (today / week /
    month), ``sort`` (newest, likes, comments)."""

    serializer_class = PostModerationSerializer
    pagination_class = AdminPagination

    def get_queryset(self):
        request = self.request
        sort = _choice(request, "sort", POST_SORTS, default="newest")
        posts = Post.objects.select_related("author", "challenge").annotate(
            like_count=Count("likes", distinct=True),
            comment_count=Count("comments", distinct=True),
            image_count=Count("images", distinct=True),
        )
        if term := _search(request):
            posts = posts.filter(Q(content__icontains=term) | _author_match(term))
        return _since_period(request, posts).order_by(*POST_SORTS[sort][2])

    def get_metrics(self):
        return _feed_metrics()


class AdminCommentListAPIView(AdminAPIView, MetricsListMixin, generics.ListAPIView):
    """GET: comments for moderation. Query: ``search``, ``period``."""

    serializer_class = CommentModerationSerializer
    pagination_class = AdminPagination

    def get_queryset(self):
        comments = Comment.objects.select_related(
            "author", "post__author", "parent__author"
        )
        if term := _search(self.request):
            comments = comments.filter(Q(content__icontains=term) | _author_match(term))
        return _since_period(self.request, comments).order_by("-created_at")

    def get_metrics(self):
        return _feed_metrics()


def _notify_removed(request, author, what, content):
    """Tell the author their content was removed, with the admin's reason if given
    (``reason`` in the body or query string)."""
    reason = str(
        request.data.get("reason") or request.query_params.get("reason", "")
    ).strip()[:200]
    message = f"“{Truncator(content).chars(80)}”"
    if reason:
        message += f" Alasan: {reason}"
    notify(
        author,
        Notification.Kind.CONTENT_REMOVED,
        f"{what} kamu dihapus admin",
        message,
        actor=request.user,
    )


class AdminPostDeleteAPIView(AdminAPIView):
    """DELETE: remove a post and notify its author (optional ``reason``)."""

    def delete(self, request, post_id):
        post = get_object_or_404(Post.objects.select_related("author"), pk=post_id)
        _notify_removed(request, post.author, "Postingan", post.content)
        delete_post(post)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminCommentDeleteAPIView(AdminAPIView):
    """DELETE: remove a comment and its replies, and notify its author (optional
    ``reason``)."""

    def delete(self, request, comment_id):
        comment = get_object_or_404(
            Comment.objects.select_related("author"), pk=comment_id
        )
        _notify_removed(request, comment.author, "Komentar", comment.content)
        comment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
