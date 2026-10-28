from django.urls import path

from . import views

app_name = "articles"

api_urlpatterns = [
    path("categories/", views.category_api_collection, name="category-list-create"),
    path(
        "categories/<slug:slug>/",
        views.category_api_detail,
        name="category-detail-update-delete",
    ),
    path("articles/", views.article_api_collection, name="list-create"),
    path(
        "articles/<slug:slug>/",
        views.article_api_detail,
        name="detail-update-delete",
    ),
]

urlpatterns = [
    path("api/articles/", views.api_article_list, name="api-article-list"),
    path("", views.article_list, name="list"),
    path("create/", views.article_create, name="create"),
    path("<slug:slug>/edit/", views.article_update, name="update"),
    path("<slug:slug>/delete/", views.article_delete, name="delete"),
    path("<slug:slug>/", views.article_detail, name="detail"),
]
