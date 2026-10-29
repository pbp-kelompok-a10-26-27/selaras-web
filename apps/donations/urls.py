from django.urls import path

from . import views

app_name = "donations"

urlpatterns = [
    path("", views.campaign_list, name="campaign_list"),
    path("campaigns/", views.campaign_list, name="campaigns"),
    path("campaigns/create/", views.campaign_create, name="campaign_create"),
    path("campaigns/<slug:slug>/", views.campaign_detail, name="campaign_detail"),
    path("campaigns/<slug:slug>/edit/", views.campaign_update, name="campaign_update"),
    path("campaigns/<slug:slug>/donate/", views.donation_create, name="donate"),
    path("history/", views.donation_history, name="history"),
    path("<int:donation_id>/edit/", views.donation_update, name="edit"),
    path("verification/", views.donation_verification_queue, name="verification_queue"),
    path(
        "verification/<int:donation_id>/proof/",
        views.admin_donation_proof,
        name="admin_proof",
    ),
    path("<int:donation_id>/proof/", views.donation_proof, name="proof"),
    path("<int:donation_id>/", views.donation_detail, name="detail"),
    path("<int:donation_id>/verify/", views.donation_verify, name="verify"),
]
