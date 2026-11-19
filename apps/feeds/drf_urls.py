from django.urls import path

from .drf_views import PostListAPIView

app_name = "feeds_drf"

urlpatterns = [
    path("posts/", PostListAPIView.as_view(), name="post-list"),
    path("", PostListAPIView.as_view(), name="post-list-root"),
]
