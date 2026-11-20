from django.urls import path

from .api_views import (
    CampaignDetailAPIView,
    CampaignListAPIView,
    DonationCreateAPIView,
    DonationHistoryAPIView,
)

app_name = "donations_drf"

urlpatterns = [
    path("campaigns/", CampaignListAPIView.as_view(), name="campaign-list"),
    path(
        "campaigns/<slug:slug>/",
        CampaignDetailAPIView.as_view(),
        name="campaign-detail",
    ),
    path("create/", DonationCreateAPIView.as_view(), name="donation-create"),
    path("history/", DonationHistoryAPIView.as_view(), name="donation-history"),
]
