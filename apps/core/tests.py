from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.views import permission_denied


# Tests run with DEBUG=False, so Django uses handler404 / handler403 from config/urls.py
class ErrorPageTests(TestCase):
    def test_missing_page_renders_custom_404(self):
        response = self.client.get("/jalur-yang-tidak-ada/")

        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "errors/404.html")
        self.assertContains(response, "/jalur-yang-tidak-ada/", status_code=404)

    def test_forbidden_page_renders_custom_403_for_signed_in_user(self):
        user = User.objects.create_user(
            username="regular", email="regular@example.com", password="pass-12345"
        )
        self.client.force_login(user)

        response = self.client.get(reverse("dashboard:home"))

        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "errors/403.html")
        self.assertContains(response, "@regular", status_code=403)

    def test_403_login_link_returns_to_the_requested_page(self):
        request = RequestFactory().get("/dashboard/")
        request.user = AnonymousUser()

        response = permission_denied(request, None)

        self.assertEqual(response.status_code, 403)
        self.assertIn(b"/accounts/login/?next=%2Fdashboard%2F", response.content)
