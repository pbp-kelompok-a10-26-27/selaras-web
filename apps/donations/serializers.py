from rest_framework import serializers

from .models import Campaign, Donation
from .services import campaign_accepts_donations


class CampaignListSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Campaign
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "image_url",
            "target_amount",
            "status",
            "starts_at",
            "ends_at",
        ]

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class DonationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Donation
        fields = ["id", "campaign", "amount", "proof", "status", "created_at"]
        read_only_fields = ["id", "status", "created_at"]

    def validate_campaign(self, campaign):
        if not campaign_accepts_donations(campaign):
            raise serializers.ValidationError(
                "Kampanye ini sedang tidak menerima donasi."
            )
        return campaign


class DonationHistorySerializer(serializers.ModelSerializer):
    campaign_title = serializers.CharField(
        source="campaign.title",
        read_only=True,
    )
    campaign_slug = serializers.CharField(
        source="campaign.slug",
        read_only=True,
    )

    class Meta:
        model = Donation
        fields = [
            "id",
            "campaign",
            "campaign_title",
            "campaign_slug",
            "amount",
            "proof",
            "status",
            "created_at",
            "verified_at",
        ]
        read_only_fields = fields
