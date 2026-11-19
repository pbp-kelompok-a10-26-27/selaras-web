from django.urls import path

from .api_views import ArticleListAPIView

app_name = "articles_drf"

urlpatterns = [
    path("", ArticleListAPIView.as_view(), name="article-list"),
]
