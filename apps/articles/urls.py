from django.urls import path

from . import html_views, views

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
    path("browse/", html_views.article_html_list, name="html-list"),
    path("read/<slug:slug>/", html_views.article_html_detail, name="html-detail"),
    path("manage/new/", html_views.article_html_create, name="html-create"),
    path(
        "manage/<slug:slug>/edit/",
        html_views.article_html_update,
        name="html-update",
    ),
    path(
        "manage/<slug:slug>/delete/",
        html_views.article_html_delete,
        name="html-delete",
    ),
    path("api/articles/", views.api_article_list, name="api-article-list"),
    path("", views.article_list, name="list"),
    path("create/", views.article_create, name="create"),
    path("<slug:slug>/edit/", views.article_update, name="update"),
    path("<slug:slug>/delete/", views.article_delete, name="delete"),
    path("<slug:slug>/", views.article_detail, name="detail"),
]
