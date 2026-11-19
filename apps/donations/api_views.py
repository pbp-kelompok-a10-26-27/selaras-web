from rest_framework import generics
from rest_framework.permissions import AllowAny

from .models import Campaign
from .serializers import CampaignListSerializer


class CampaignListAPIView(generics.ListAPIView):
    """
    Endpoint GET publik untuk daftar kampanye donasi yang terbit.
    Hanya mendukung HTTP GET (Read-Only).
    """

    queryset = Campaign.objects.filter(status=Campaign.Status.PUBLISHED).order_by(
        "-created_at"
    )
    serializer_class = CampaignListSerializer
    permission_classes = [AllowAny]
    http_method_names = ["get", "head", "options"]
