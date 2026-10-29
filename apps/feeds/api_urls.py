from django.urls import path

from . import views

app_name = "feeds_api"

urlpatterns = [
    path("posts", views.api_posts_collection, name="post-list"),
    path("posts/<uuid:post_id>", views.api_post_resource, name="api-post-detail"),
    path(
        "posts/<uuid:post_id>/comments",
        views.api_comment_collection,
        name="comment-list",
    ),
    path(
        "comments/<uuid:comment_id>/replies",
        views.api_reply_create,
        name="reply-create",
    ),
    path(
        "comments/<uuid:comment_id>",
        views.api_comment_resource,
        name="comment-update",
    ),
    path("posts/<uuid:post_id>/like", views.api_toggle_like, name="like"),
    path("posts/<uuid:post_id>/likes", views.api_post_likers, name="post-likers"),
    path(
        "comments/<uuid:comment_id>/like",
        views.api_toggle_comment_like,
        name="comment-like",
    ),
    path(
        "comments/<uuid:comment_id>/likes",
        views.api_comment_likers,
        name="comment-likers",
    ),
    path("admin/posts", views.api_admin_post_list, name="admin-post-list"),
    path(
        "admin/posts/<uuid:post_id>",
        views.api_admin_post_delete,
        name="admin-post-delete",
    ),
    path(
        "admin/comments/<uuid:comment_id>",
        views.api_admin_comment_delete,
        name="admin-comment-delete",
    ),
]
