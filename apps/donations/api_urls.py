from django.urls import path

from .api_views import CampaignListAPIView

app_name = "donations_drf"

urlpatterns = [
    path("campaigns/", CampaignListAPIView.as_view(), name="campaign-list"),
    path("", CampaignListAPIView.as_view(), name="campaign-list-root"),
]
