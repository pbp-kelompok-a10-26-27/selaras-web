from django.urls import path

from . import views

app_name = "feeds"

urlpatterns = [
    path("", views.post_list, name="list"),
    path("create/", views.post_create, name="create"),
    path("<uuid:post_id>/", views.post_detail, name="detail"),
    path("<uuid:post_id>/edit/", views.post_update, name="update"),
    path("<uuid:post_id>/delete/", views.post_delete, name="delete"),
    path("<uuid:post_id>/like/", views.toggle_like, name="like"),
    path("<uuid:post_id>/likes/", views.post_likers, name="likers"),
    path(
        "<uuid:post_id>/comments/create/", views.comment_create, name="comment_create"
    ),
    path(
        "comments/<uuid:comment_id>/delete/",
        views.comment_delete,
        name="comment_delete",
    ),
    path("comments/<uuid:comment_id>/reply/", views.reply_create, name="reply_create"),
    path("comments/<uuid:comment_id>/like/", views.comment_like, name="comment_like"),
    path(
        "comments/<uuid:comment_id>/likes/",
        views.comment_likers,
        name="comment_likers",
    ),
    path("<uuid:post_id>/moderate/", views.moderate_post, name="moderate"),
]
