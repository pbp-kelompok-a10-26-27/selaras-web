from django.urls import path

from .api_views import (
    AttachmentDownloadAPIView,
    TicketDetailAPIView,
    TicketListCreateAPIView,
    TicketMessageListCreateAPIView,
    TicketStatsAPIView,
)

app_name = "helpdesk_drf"

urlpatterns = [
    path("tickets/", TicketListCreateAPIView.as_view(), name="ticket-list"),
    path("", TicketListCreateAPIView.as_view(), name="ticket-list-root"),
    path("tickets/stats/", TicketStatsAPIView.as_view(), name="ticket-stats"),
    path(
        "tickets/<uuid:ticket_id>/",
        TicketDetailAPIView.as_view(),
        name="ticket-detail",
    ),
    path(
        "tickets/<uuid:ticket_id>/messages/",
        TicketMessageListCreateAPIView.as_view(),
        name="ticket-messages",
    ),
    path(
        "attachments/<int:attachment_id>/",
        AttachmentDownloadAPIView.as_view(),
        name="attachment-download",
    ),
]
