from rest_framework import serializers

from .models import Campaign


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
