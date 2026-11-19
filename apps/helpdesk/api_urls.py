from django.urls import path

from .api_views import TicketListAPIView

app_name = "helpdesk_drf"

urlpatterns = [
    path("tickets/", TicketListAPIView.as_view(), name="ticket-list"),
    path("", TicketListAPIView.as_view(), name="ticket-list-root"),
]
