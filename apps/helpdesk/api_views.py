from rest_framework import generics
from rest_framework.permissions import AllowAny

from .models import Ticket
from .serializers import TicketListSerializer


class TicketListAPIView(generics.ListAPIView):
    """
    Endpoint GET publik untuk daftar tiket bantuan.
    Hanya mendukung HTTP GET (Read-Only).
    """

    queryset = Ticket.objects.select_related("requester").order_by("-created_at")[:50]
    serializer_class = TicketListSerializer
    permission_classes = [AllowAny]
    http_method_names = ["get", "head", "options"]
