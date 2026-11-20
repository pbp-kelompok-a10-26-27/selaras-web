from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from apps.accounts.api_views import AuthenticatedAPIView

from . import services
from .models import Notification
from .serializers import NotificationSerializer

SHOW_FILTERS = ("all", "unread")


class NotificationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


def _inbox(user):
    """The signed-in user's own notifications, newest first. Everything in this API
    goes through it, so nobody can read or change someone else's."""
    return Notification.objects.filter(recipient=user).select_related("actor")


class NotificationListAPIView(AuthenticatedAPIView, generics.ListAPIView):
    """GET: your notifications, newest first. ``show=unread`` hides the read ones.
    The response also carries ``unread``, the total number still unread (for the
    bell badge)."""

    serializer_class = NotificationSerializer
    pagination_class = NotificationPagination

    def get_queryset(self):
        notifications = _inbox(self.request.user)
        if self.request.query_params.get("show") == "unread":
            notifications = notifications.filter(read_at__isnull=True)
        return notifications

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        response.data = {
            **response.data,
            "unread": services.unread_count(request.user),
        }
        return response


class UnreadCountAPIView(AuthenticatedAPIView):
    """GET: ``{"unread": n}``, cheap enough to poll for the bell badge."""

    def get(self, request):
        return Response({"unread": services.unread_count(request.user)})


class NotificationDetailAPIView(AuthenticatedAPIView, generics.RetrieveAPIView):
    """GET: one notification. Reading it does not mark it read; POST ``read/`` does."""

    serializer_class = NotificationSerializer
    lookup_url_kwarg = "notification_id"

    def get_queryset(self):
        return _inbox(self.request.user)


class NotificationMarkReadAPIView(AuthenticatedAPIView):
    """POST: mark one notification read (the app calls this when the user opens it)."""

    def post(self, request, notification_id):
        notification = get_object_or_404(_inbox(request.user), pk=notification_id)
        services.mark_read(notification)
        data = NotificationSerializer(notification, context={"request": request}).data
        return Response({**data, "unread": services.unread_count(request.user)})


class MarkAllReadAPIView(AuthenticatedAPIView):
    """POST: mark every notification read."""

    def post(self, request):
        marked = services.mark_all_read(request.user)
        return Response({"marked": marked, "unread": 0})
