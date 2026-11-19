from django.urls import path

from .api_views import ChallengeListAPIView

app_name = "challenges_drf"

urlpatterns = [
    path("", ChallengeListAPIView.as_view(), name="challenge-list"),
]
