from django.urls import path

from . import views

app_name = "feeds_api"

urlpatterns = [
    path("posts", views.api_posts_collection, name="post-list"),
    path("posts/<int:post_id>", views.api_post_resource, name="api-post-detail"),
    path(
        "posts/<int:post_id>/comments",
        views.api_comment_collection,
        name="comment-list",
    ),
    path(
        "comments/<int:comment_id>/replies",
        views.api_reply_create,
        name="reply-create",
    ),
    path(
        "comments/<int:comment_id>",
        views.api_comment_resource,
        name="comment-update",
    ),
    path("posts/<int:post_id>/like", views.api_toggle_like, name="like"),
    path("admin/posts", views.api_admin_post_list, name="admin-post-list"),
    path(
        "admin/posts/<int:post_id>",
        views.api_admin_post_delete,
        name="admin-post-delete",
    ),
    path(
        "admin/comments/<int:comment_id>",
        views.api_admin_comment_delete,
        name="admin-comment-delete",
    ),
]
