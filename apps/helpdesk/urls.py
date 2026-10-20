from django.urls import path

from . import views

app_name = "helpdesk"

urlpatterns = [
    path("", views.ticket_list, name="list"),
    path("create/", views.ticket_create, name="create"),
    path("<int:ticket_id>/", views.ticket_detail, name="detail"),
    path("<int:ticket_id>/messages/create/", views.ticket_message_create, name="message_create"),
    path("<int:ticket_id>/update/", views.ticket_update, name="update"),
]