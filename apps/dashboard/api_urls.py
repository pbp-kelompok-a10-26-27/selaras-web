from django.urls import path

from .api_views import (
    AdminArticleListAPIView,
    AdminAttachmentDownloadAPIView,
    AdminBadgeDetailAPIView,
    AdminBadgeListCreateAPIView,
    AdminCampaignListAPIView,
    AdminChallengeDetailAPIView,
    AdminChallengeListCreateAPIView,
    AdminCommentDeleteAPIView,
    AdminCommentListAPIView,
    AdminGoalDetailAPIView,
    AdminGoalListCreateAPIView,
    AdminPostDeleteAPIView,
    AdminPostListAPIView,
    AdminTicketAssignAPIView,
    AdminTicketDetailAPIView,
    AdminTicketListAPIView,
    AdminTicketMessageListCreateAPIView,
    AdminTicketStatsAPIView,
    AdminUserDetailAPIView,
    AdminUserListAPIView,
    OverviewAPIView,
)

app_name = "dashboard_drf"

urlpatterns = [
    path("overview/", OverviewAPIView.as_view(), name="overview"),
    # Helpdesk
    path("helpdesk/tickets/", AdminTicketListAPIView.as_view(), name="ticket-list"),
    path(
        "helpdesk/tickets/stats/",
        AdminTicketStatsAPIView.as_view(),
        name="ticket-stats",
    ),
    path(
        "helpdesk/tickets/<uuid:ticket_id>/",
        AdminTicketDetailAPIView.as_view(),
        name="ticket-detail",
    ),
    path(
        "helpdesk/tickets/<uuid:ticket_id>/assign/",
        AdminTicketAssignAPIView.as_view(),
        name="ticket-assign",
    ),
    path(
        "helpdesk/tickets/<uuid:ticket_id>/messages/",
        AdminTicketMessageListCreateAPIView.as_view(),
        name="ticket-messages",
    ),
    path(
        "helpdesk/attachments/<int:attachment_id>/",
        AdminAttachmentDownloadAPIView.as_view(),
        name="attachment-download",
    ),
    # Challenges, badges and community goals
    path(
        "challenges/",
        AdminChallengeListCreateAPIView.as_view(),
        name="challenge-list",
    ),
    path(
        "challenges/<slug:slug>/",
        AdminChallengeDetailAPIView.as_view(),
        name="challenge-detail",
    ),
    path("badges/", AdminBadgeListCreateAPIView.as_view(), name="badge-list"),
    path(
        "badges/<slug:slug>/",
        AdminBadgeDetailAPIView.as_view(),
        name="badge-detail",
    ),
    path("goals/", AdminGoalListCreateAPIView.as_view(), name="goal-list"),
    path("goals/<int:pk>/", AdminGoalDetailAPIView.as_view(), name="goal-detail"),
    # Users
    path("users/", AdminUserListAPIView.as_view(), name="user-list"),
    path(
        "users/<uuid:user_id>/",
        AdminUserDetailAPIView.as_view(),
        name="user-detail",
    ),
    # Read-only overviews
    path("articles/", AdminArticleListAPIView.as_view(), name="article-list"),
    path(
        "donations/campaigns/",
        AdminCampaignListAPIView.as_view(),
        name="campaign-list",
    ),
    # Feed moderation
    path("feeds/posts/", AdminPostListAPIView.as_view(), name="post-list"),
    path(
        "feeds/posts/<uuid:post_id>/",
        AdminPostDeleteAPIView.as_view(),
        name="post-delete",
    ),
    path("feeds/comments/", AdminCommentListAPIView.as_view(), name="comment-list"),
    path(
        "feeds/comments/<uuid:comment_id>/",
        AdminCommentDeleteAPIView.as_view(),
        name="comment-delete",
    ),
]
