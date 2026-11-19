from rest_framework import generics
from rest_framework.permissions import AllowAny

from .models import Post
from .serializers import PostListSerializer


class PostListAPIView(generics.ListAPIView):
    """
    Endpoint GET publik untuk linimasa feed postingan.
    Hanya mendukung HTTP GET (Read-Only).
    """

    queryset = (
        Post.objects.select_related("author", "challenge")
        .prefetch_related("images", "likes", "comments")
        .order_by("-created_at")
    )
    serializer_class = PostListSerializer
    permission_classes = [AllowAny]
    http_method_names = ["get", "head", "options"]
