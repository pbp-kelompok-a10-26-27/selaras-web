from django.urls import path

from . import views

app_name = "helpdesk"

urlpatterns = [
    path("tickets/", views.ticket_list, name="ticket_list"),
    path("tickets/create/", views.ticket_create, name="ticket_create"),
    path("api/tickets/stats/", views.ticket_stats_api, name="ticket_stats_api"),
    path("api/tickets/", views.ticket_list_api, name="ticket_list_api"),
    path("api/tickets/create/", views.ticket_create_api, name="ticket_create_api"),
    path(
        "api/tickets/<uuid:ticket_id>/",
        views.ticket_detail_api,
        name="ticket_detail_api",
    ),
    path(
        "api/tickets/<uuid:ticket_id>/messages/",
        views.ticket_message_api,
        name="ticket_message_api",
    ),
    path("tickets/<uuid:ticket_id>/", views.ticket_detail, name="ticket_detail"),
    path(
        "tickets/<uuid:ticket_id>/messages/create/",
        views.ticket_message_create,
        name="ticket_message_create",
    ),
    path("tickets/<uuid:ticket_id>/update/", views.ticket_update, name="ticket_update"),
    path("tickets/<uuid:ticket_id>/delete/", views.ticket_delete, name="ticket_delete"),
]
