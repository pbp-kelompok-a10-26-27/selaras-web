from rest_framework import generics
from rest_framework.permissions import AllowAny

from .models import Challenge
from .serializers import ChallengeListSerializer


class ChallengeListAPIView(generics.ListAPIView):
    """
    Endpoint GET publik untuk daftar tantangan hidup berkelanjutan.
    Hanya mendukung HTTP GET (Read-Only).
    """

    queryset = (
        Challenge.objects.filter(is_published=True)
        .select_related("badge")
        .order_by("-start_date", "-created_at")
    )
    serializer_class = ChallengeListSerializer
    permission_classes = [AllowAny]
    http_method_names = ["get", "head", "options"]
