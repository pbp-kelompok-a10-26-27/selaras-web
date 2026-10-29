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
]
