from django.conf import settings
from django.urls import re_path
from django.views.static import serve

from config.urls import urlpatterns as project_urlpatterns

media_pattern_prefix = f"^{settings.MEDIA_URL.lstrip('/')}"


def serve_test_media(request, path):
    return serve(request, path, document_root=settings.MEDIA_ROOT)


urlpatterns = [
    pattern
    for pattern in project_urlpatterns
    if not str(pattern.pattern).startswith(media_pattern_prefix)
]
urlpatterns += [
    re_path(r"^media/(?P<path>.*)$", serve_test_media),
]
