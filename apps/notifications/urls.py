from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.notification_list, name="list"),
    path("feed/", views.notification_feed, name="feed"),
    path("read-all/", views.notification_read_all, name="read_all"),
    path("<uuid:notification_id>/", views.notification_open, name="open"),
]
