from django.urls import path

from . import views

app_name = "feeds"

urlpatterns = [
    path("", views.post_list, name="list"),
    path("create/", views.post_create, name="create"),
    path("<int:post_id>/", views.post_detail, name="detail"),
    path("<int:post_id>/edit/", views.post_update, name="update"),
    path("<int:post_id>/delete/", views.post_delete, name="delete"),
    path("<int:post_id>/like/", views.toggle_like, name="like"),
    path("<int:post_id>/comments/create/", views.comment_create, name="comment_create"),
    path("<int:post_id>/moderate/", views.moderate_post, name="moderate"),
]