from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.admin_dashboard, name="home"),
    # Helpdesk ticket management
    path("helpdesk/tickets/", views.admin_ticket_list, name="admin_ticket_list"),
    path(
        "helpdesk/api/tickets/",
        views.admin_ticket_list_api,
        name="admin_ticket_list_api",
    ),
    path(
        "helpdesk/api/tickets/stats/",
        views.admin_ticket_stats_api,
        name="admin_ticket_stats_api",
    ),
    path(
        "helpdesk/tickets/<uuid:ticket_id>/assign/",
        views.admin_ticket_assign,
        name="admin_ticket_assign",
    ),
    path(
        "helpdesk/tickets/<uuid:ticket_id>/delete/",
        views.admin_ticket_delete,
        name="admin_ticket_delete",
    ),
    path(
        "helpdesk/tickets/<uuid:ticket_id>/",
        views.admin_ticket_detail,
        name="admin_ticket_detail",
    ),
    path(
        "helpdesk/tickets/<uuid:ticket_id>/update/",
        views.admin_ticket_update,
        name="admin_ticket_update",
    ),
    path(
        "helpdesk/tickets/<uuid:ticket_id>/messages/create/",
        views.admin_ticket_message_create,
        name="admin_ticket_message_create",
    ),
    path(
        "helpdesk/api/tickets/<uuid:ticket_id>/",
        views.admin_ticket_detail_api,
        name="admin_ticket_detail_api",
    ),
    # Challenges management
    path("challenges/", views.admin_challenge_list, name="admin_challenge_list"),
    # Community goals; before <slug> so "goals" isn't a slug
    path("challenges/goals/", views.admin_goal_list, name="admin_goal_list"),
    path("challenges/goals/create/", views.admin_goal_create, name="admin_goal_create"),
    path(
        "challenges/goals/<int:pk>/edit/",
        views.admin_goal_update,
        name="admin_goal_update",
    ),
    path(
        "challenges/goals/<int:pk>/delete/",
        views.admin_goal_delete,
        name="admin_goal_delete",
    ),
    # Badges (rewards for challenges); before <slug> so "badges" isn't a slug
    path("challenges/badges/", views.admin_badge_list, name="admin_badge_list"),
    path(
        "challenges/badges/create/",
        views.admin_badge_create,
        name="admin_badge_create",
    ),
    path(
        "challenges/badges/<slug:slug>/edit/",
        views.admin_badge_update,
        name="admin_badge_update",
    ),
    path(
        "challenges/badges/<slug:slug>/delete/",
        views.admin_badge_delete,
        name="admin_badge_delete",
    ),
    path(
        "challenges/create/",
        views.admin_challenge_create,
        name="admin_challenge_create",
    ),
    path(
        "challenges/<slug:slug>/edit/",
        views.admin_challenge_update,
        name="admin_challenge_update",
    ),
    path(
        "challenges/<slug:slug>/delete/",
        views.admin_challenge_delete,
        name="admin_challenge_delete",
    ),
    # Users
    path("users/", views.admin_user_list, name="admin_user_list"),
    path("users/<uuid:user_id>/", views.admin_user_detail, name="admin_user_detail"),
    path("users/<uuid:user_id>/role/", views.admin_user_role, name="admin_user_role"),
    path(
        "users/<uuid:user_id>/active/",
        views.admin_user_active,
        name="admin_user_active",
    ),
    # Articles
    path("articles/", views.admin_article_list, name="admin_article_list"),
    # Donations
    path("donations/", views.admin_donation_list, name="admin_donation_list"),
    # Feeds moderation
    path("feeds/", views.admin_feed_list, name="admin_feed_list"),
    path(
        "feeds/posts/<uuid:post_id>/delete/",
        views.admin_feed_post_delete,
        name="admin_feed_post_delete",
    ),
    path(
        "feeds/comments/<uuid:comment_id>/delete/",
        views.admin_feed_comment_delete,
        name="admin_feed_comment_delete",
    ),
]
