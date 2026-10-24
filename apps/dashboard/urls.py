from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.admin_dashboard, name="home"),
    # path("helpdesk/tickets/", views.admin_ticket_list, name="admin_ticket_list"),

    # TODO 2 & 3: enable these once their views exist (a missing view breaks every URL in the project)
    # path("helpdesk/tickets/<uuid:ticket_id>/", views.admin_ticket_detail, name="admin_ticket_detail"),
    # path("helpdesk/tickets/<uuid:ticket_id>/update/", views.admin_ticket_update, name="admin_ticket_update"),
    # path("helpdesk/tickets/<uuid:ticket_id>/delete/", views.admin_ticket_delete, name="admin_ticket_delete"),
    # path("helpdesk/tickets/<uuid:ticket_id>/messages/create/", views.admin_ticket_message_create, name="admin_ticket_message_create"),
    # path("helpdesk/api/tickets/stats/", views.admin_ticket_stats_api, name="admin_ticket_stats_api"),
    # path("helpdesk/api/tickets/", views.admin_ticket_list_api, name="admin_ticket_list_api"),
]
