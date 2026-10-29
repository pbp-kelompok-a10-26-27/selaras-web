from django.contrib.auth.models import Group
from django.core import mail
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from apps.core.decorators import admin_required
from apps.core.permissions import is_admin, is_authenticated_user, is_user

from .models import User


class AuthenticationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="existing",
            email="existing@example.com",
            password="Strong-password-123",
        )

    def test_registration_creates_user_and_assigns_user_group(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "username": "new-user",
                "email": "new@example.com",
                "password1": "Strong-password-123",
                "password2": "Strong-password-123",
            },
        )

        self.assertRedirects(response, reverse("home"))
        new_user = User.objects.get(username="new-user")
        self.assertEqual(new_user.role, User.Role.USER)

    def test_registration_rejects_duplicate_email_case_insensitively(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "username": "another-user",
                "email": "EXISTING@example.com",
                "password1": "Strong-password-123",
                "password2": "Strong-password-123",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Email ini sudah terdaftar.")

    def test_login_and_logout(self):
        login_response = self.client.post(
            reverse("accounts:login"),
            {"username": "existing", "password": "Strong-password-123"},
        )
        self.assertRedirects(login_response, reverse("home"))
        self.assertTrue(self.client.session.get("_auth_user_id"))

        logout_response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(logout_response, reverse("home"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_invalid_login_does_not_authenticate(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "existing", "password": "wrong-password"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_profile_requires_authentication_and_updates_current_user_only(self):
        response = self.client.get(reverse("accounts:profile"))
        self.assertRedirects(
            response, f"{reverse('accounts:login')}?next={reverse('accounts:profile')}"
        )

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("accounts:profile"),
            {
                "username": "existing",
                "email": "updated@example.com",
                "first_name": "Updated",
                "last_name": "User",
            },
        )
        self.assertRedirects(response, reverse("accounts:profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "updated@example.com")
        self.assertEqual(self.user.first_name, "Updated")

    def test_password_change_requires_authentication_and_keeps_session(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("accounts:password_change"),
            {
                "old_password": "Strong-password-123",
                "new_password1": "New-strong-password-456",
                "new_password2": "New-strong-password-456",
            },
        )
        self.assertRedirects(response, reverse("accounts:password_change_done"))
        self.assertTrue(
            self.client.login(username="existing", password="New-strong-password-456")
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_password_reset_does_not_reveal_unknown_accounts(self):
        response = self.client.post(
            reverse("accounts:password_reset"),
            {"email": "unknown@example.com"},
        )
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

        self.client.post(reverse("accounts:password_reset"), {"email": self.user.email})
        self.assertEqual(len(mail.outbox), 1)


class AuthorizationTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="regular",
            email="regular@example.com",
            password="Strong-password-123",
        )
        self.admin = User.objects.create_user(
            username="administrator",
            email="administrator@example.com",
            password="Strong-password-123",
            role=User.Role.ADMIN,
        )
        self.user.groups.add(Group.objects.get(name="User"))
        self.admin.groups.add(Group.objects.get(name="Admin"))

    def test_group_helpers_are_safe_for_anonymous_users(self):
        self.assertFalse(is_authenticated_user(None))
        self.assertFalse(is_admin(None))
        self.assertFalse(is_user(None))

    def test_group_helpers_distinguish_admin_and_user_roles(self):
        self.assertTrue(is_user(self.user))
        self.assertFalse(is_admin(self.user))
        self.assertTrue(is_admin(self.admin))
        self.assertFalse(is_user(self.admin))

    def test_admin_required_enforces_group_membership(self):
        @admin_required
        def protected_view(request):
            return HttpResponse("ok")

        anonymous_request = self.factory.get("/admin-only/")
        anonymous_request.user = type("Anonymous", (), {"is_authenticated": False})()
        self.assertEqual(protected_view(anonymous_request).status_code, 302)

        user_request = self.factory.get("/admin-only/")
        user_request.user = self.user
        with self.assertRaises(PermissionDenied):
            protected_view(user_request)

        admin_request = self.factory.get("/admin-only/")
        admin_request.user = self.admin
        self.assertEqual(protected_view(admin_request).status_code, 200)


class ProfileLayoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="regular",
            email="regular@example.com",
            password="Strong-password-123",
        )
        self.admin = User.objects.create_user(
            username="administrator",
            email="administrator@example.com",
            password="Strong-password-123",
            role=User.Role.ADMIN,
        )

    def test_user_account_pages_use_the_site_layout(self):
        self.client.force_login(self.user)
        for name in ("accounts:profile", "accounts:password_change"):
            response = self.client.get(reverse(name))
            self.assertTemplateUsed(response, "base.html")
            self.assertTemplateNotUsed(response, "dashboard/base.html")

        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(
            [stat["label"] for stat in response.context["stats"]],
            ["Tiket dibuat", "Sedang diproses", "Terjawab"],
        )

    def test_profile_no_longer_offers_a_reset_email(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("accounts:profile"))

        self.assertNotContains(response, "Send link")
        self.assertNotContains(
            response, f'action="{reverse("accounts:password_reset")}"'
        )

    def test_admin_account_pages_use_the_dashboard_layout(self):
        self.client.force_login(self.admin)
        for name in ("accounts:profile", "accounts:password_change"):
            response = self.client.get(reverse(name))
            self.assertTemplateUsed(response, "dashboard/base.html")
            self.assertIn("sidebar_sections", response.context)

        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.context["stats"][0]["label"], "Ditugaskan ke kamu")

    def test_profile_completion_counts_filled_fields(self):
        self.client.force_login(self.user)
        self.assertEqual(
            self.client.get(reverse("accounts:profile")).context["completion"][
                "percent"
            ],
            25,  # only the email
        )

        self.user.first_name, self.user.last_name, self.user.bio = (
            "Ayu",
            "Lestari",
            "Hi",
        )  # noqa: E501
        self.user.save()
        self.assertEqual(
            self.client.get(reverse("accounts:profile")).context["completion"][
                "percent"
            ],
            100,
        )

    def test_invalid_profile_post_keeps_saved_values_in_the_header(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("accounts:profile"),
            {"email": "not-an-email", "first_name": "Unsaved"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["profile_user"].first_name, "")
        self.assertContains(response, 'data-has-errors="true"')


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PasswordPagesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="regular",
            email="regular@example.com",
            password="Strong-password-123",
        )

    def test_password_change_done_uses_the_role_layout(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:password_change_done"))
        self.assertTemplateUsed(response, "base.html")
        self.assertContains(response, "Kata sandi berhasil diganti")

    def test_reset_flow_pages_render_with_their_step(self):
        response = self.client.get(reverse("accounts:password_reset_done"))
        self.assertTemplateUsed(response, "accounts/_recovery_base.html")
        self.assertContains(response, 'data-cooldown="30"')

        response = self.client.get(reverse("accounts:password_reset_complete"))
        self.assertContains(response, "Kata sandi berhasil diatur ulang")
        self.assertContains(response, reverse("accounts:login"))

    def test_reset_confirm_shows_form_for_valid_link_and_notice_for_bad_one(self):
        self.client.post(reverse("accounts:password_reset"), {"email": self.user.email})
        # The emailed link redirects once to a "set-password" URL that holds the token
        link = next(
            line
            for line in mail.outbox[0].body.splitlines()
            if "/password/reset/" in line
        ).strip()
        response = self.client.get(link, follow=True)
        self.assertTrue(response.context["validlink"])
        self.assertContains(response, "data-password-form")
        # username for password managers
        self.assertContains(response, 'value="regular"')

        response = self.client.post(
            response.redirect_chain[-1][0],
            {
                "new_password1": "New-strong-password-456",
                "new_password2": "New-strong-password-456",
            },
        )
        self.assertRedirects(response, reverse("accounts:password_reset_complete"))

        bad = reverse(
            "accounts:password_reset_confirm",
            kwargs={"uidb64": "bad", "token": "bad-token"},
        )
        response = self.client.get(bad)
        self.assertFalse(response.context["validlink"])
        self.assertContains(response, "Tautan ini sudah kedaluwarsa")
