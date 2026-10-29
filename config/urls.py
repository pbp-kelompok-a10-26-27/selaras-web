"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.articles.urls import api_urlpatterns
from apps.core.views import design_system, home

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "api/",
        include((api_urlpatterns, "articles_api"), namespace="articles_api"),
    ),
    path("accounts/", include("apps.accounts.urls")),
    path("articles/", include("apps.articles.urls")),
    path("challenges/", include("apps.challenges.urls")),
    path("feed/", include("apps.feeds.urls")),
    path("api/v1/", include("apps.feeds.api_urls")),
    path("donations/", include("apps.donations.urls")),
    path("helpdesk/", include("apps.helpdesk.urls")),
    path("design-system/", design_system, name="design_system"),
    # Not "admin/": Django's admin above already owns that prefix and 404s any path
    # it doesn't know
    path("dashboard/", include("apps.dashboard.urls")),
    # Landing page (templates/landing/home.html) with live numbers from each app
    path("", home, name="home"),
]

# Uploaded avatars. Outside DEBUG the web server is expected to serve MEDIA_ROOT.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Custom error pages (templates/errors/), used when DEBUG is False
handler404 = "apps.core.views.page_not_found"
handler403 = "apps.core.views.permission_denied"

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
