from rest_framework import generics
from rest_framework.permissions import AllowAny

from .models import Article
from .serializers import ArticleListSerializer


class ArticleListAPIView(generics.ListAPIView):
    """
    Endpoint GET publik untuk daftar artikel yang sudah terbit.
    Hanya mendukung HTTP GET (Read-Only).
    """

    queryset = (
        Article.objects.filter(status=Article.Status.PUBLISHED)
        .select_related("category", "author")
        .prefetch_related("tags")
        .order_by("-published_at", "-created_at")
    )
    serializer_class = ArticleListSerializer
    permission_classes = [AllowAny]
    http_method_names = ["get", "head", "options"]
