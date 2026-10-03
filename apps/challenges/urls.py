from django.urls import path

from . import views

app_name = "challenges"

urlpatterns = [
    path("", views.challenge_list, name="list"),
    path("history/", views.challenge_history, name="history"),
    path("create/", views.challenge_create, name="create"),
    path("<slug:slug>/", views.challenge_detail, name="detail"),
    path("<slug:slug>/join/", views.join_challenge, name="join"),
    path("<slug:slug>/progress/", views.record_progress, name="progress"),
    path("<slug:slug>/edit/", views.challenge_update, name="update"),
    path("<slug:slug>/delete/", views.challenge_delete, name="delete"),
]