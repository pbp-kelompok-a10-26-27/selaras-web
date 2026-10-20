from django.urls import path

from . import views

app_name = "articles"

urlpatterns = [
    path("", views.article_list, name="list"),
    path("<slug:slug>/", views.article_detail, name="detail"),
    path("create/", views.article_create, name="create"),
    path("<slug:slug>/edit/", views.article_update, name="update"),
    path("<slug:slug>/delete/", views.article_delete, name="delete"),
]