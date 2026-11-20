from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated

from .models import Campaign, Donation
from .serializers import (
    CampaignListSerializer,
    DonationCreateSerializer,
    DonationHistorySerializer,
)


class CampaignListAPIView(generics.ListAPIView):
    queryset = Campaign.objects.filter(status=Campaign.Status.PUBLISHED).order_by(
        "-created_at"
    )
    serializer_class = CampaignListSerializer
    permission_classes = [AllowAny]


class CampaignDetailAPIView(generics.RetrieveAPIView):
    queryset = Campaign.objects.filter(status=Campaign.Status.PUBLISHED)
    serializer_class = CampaignListSerializer
    permission_classes = [AllowAny]
    lookup_field = "slug"


class DonationCreateAPIView(generics.CreateAPIView):
    serializer_class = DonationCreateSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(donor=self.request.user)


class DonationHistoryAPIView(generics.ListAPIView):
    serializer_class = DonationHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Donation.objects.filter(donor=self.request.user)
            .select_related("campaign")
            .order_by("-created_at")
        )
