from django.urls import path

from .api_views import (
    MarkAllReadAPIView,
    NotificationDetailAPIView,
    NotificationListAPIView,
    NotificationMarkReadAPIView,
    UnreadCountAPIView,
)

app_name = "notifications_drf"

urlpatterns = [
    path("", NotificationListAPIView.as_view(), name="list"),
    path("unread-count/", UnreadCountAPIView.as_view(), name="unread-count"),
    path("read-all/", MarkAllReadAPIView.as_view(), name="read-all"),
    path(
        "<uuid:notification_id>/",
        NotificationDetailAPIView.as_view(),
        name="detail",
    ),
    path(
        "<uuid:notification_id>/read/",
        NotificationMarkReadAPIView.as_view(),
        name="mark-read",
    ),
]
