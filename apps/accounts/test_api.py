import io

from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.challenges.models import Badge, UserBadge

from .models import User
from .views import LOGIN_MAX_FAILURES

PASSWORD = "Strong-password-123"
BASE = "/api/v1/accounts"

# 1x1 transparent PNG
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe"
    b"\x02\xfe\xa7\x9a\xa0\xa0\x00\x00\x00\x00IEND\xaeB`\x82"
)


class ApiTestBase(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="existing", email="existing@example.com", password=PASSWORD
        )

    def authenticate(self, user=None):
        token, _ = Token.objects.get_or_create(user=user or self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        return token


class RegisterTests(ApiTestBase):
    url = f"{BASE}/register/"

    def payload(self, **overrides):
        data = {
            "username": "new-user",
            "email": "New@Example.com",
            "password": PASSWORD,
            "password_confirm": PASSWORD,
        }
        data.update(overrides)
        return data

    def test_creates_regular_user_and_returns_token(self):
        response = self.client.post(self.url, self.payload())

        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username="new-user")
        self.assertEqual(user.role, User.Role.USER)
        self.assertEqual(user.email, "new@example.com")
        self.assertEqual(response.data["token"], Token.objects.get(user=user).key)
        self.assertNotIn("password", response.data["user"])

    def test_cannot_choose_role(self):
        self.client.post(self.url, self.payload(role="admin", is_staff=True))
        user = User.objects.get(username="new-user")
        self.assertEqual(user.role, User.Role.USER)
        self.assertFalse(user.is_staff)

    def test_rejects_duplicate_email_case_insensitively(self):
        response = self.client.post(
            self.url, self.payload(email="EXISTING@example.com")
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)

    def test_rejects_mismatched_and_weak_passwords(self):
        mismatch = self.client.post(self.url, self.payload(password_confirm="nope"))
        self.assertIn("password_confirm", mismatch.data)

        weak = self.client.post(
            self.url, self.payload(password="12345678", password_confirm="12345678")
        )
        self.assertEqual(weak.status_code, 400)
        self.assertIn("password", weak.data)


class LoginLogoutTests(ApiTestBase):
    url = f"{BASE}/login/"

    def test_login_returns_token(self):
        response = self.client.post(
            self.url, {"username": "existing", "password": PASSWORD}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["token"], Token.objects.get(user=self.user).key)

    def test_wrong_password_is_rejected(self):
        response = self.client.post(
            self.url, {"username": "existing", "password": "wrong"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Token.objects.exists())

    def test_locks_out_after_repeated_failures(self):
        for _ in range(LOGIN_MAX_FAILURES):
            self.client.post(self.url, {"username": "existing", "password": "wrong"})

        # even the right password is refused while locked
        response = self.client.post(
            self.url, {"username": "existing", "password": PASSWORD}
        )
        self.assertEqual(response.status_code, 429)

    def test_logout_revokes_token(self):
        token = self.authenticate()
        response = self.client.post(f"{BASE}/logout/")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Token.objects.filter(key=token.key).exists())
        self.assertEqual(self.client.get(f"{BASE}/me/").status_code, 401)


class ProfileTests(ApiTestBase):
    url = f"{BASE}/me/"

    def test_requires_authentication(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_get_profile(self):
        self.authenticate()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["username"], "existing")
        self.assertEqual(response.data["avatar_url"], "")

    def test_patch_updates_allowed_fields_only(self):
        self.authenticate()
        response = self.client.patch(
            self.url,
            {
                "first_name": "Sari",
                "bio": "Suka menanam",
                "role": "admin",
                "username": "hacked",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Sari")
        self.assertEqual(self.user.bio, "Suka menanam")
        self.assertEqual(self.user.role, User.Role.USER)
        self.assertEqual(self.user.username, "existing")

    def test_patch_rejects_email_taken_by_someone_else(self):
        User.objects.create_user("other", "other@example.com", PASSWORD)
        self.authenticate()
        response = self.client.patch(self.url, {"email": "OTHER@example.com"})
        self.assertEqual(response.status_code, 400)

    def test_patch_keeps_own_email(self):
        self.authenticate()
        response = self.client.patch(self.url, {"email": "Existing@Example.com"})
        self.assertEqual(response.status_code, 200)

    def test_delete_not_allowed(self):
        self.authenticate()
        self.assertEqual(self.client.delete(self.url).status_code, 405)

    def test_summary(self):
        self.authenticate()
        response = self.client.get(f"{BASE}/me/summary/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["stats"]), 3)
        self.assertNotIn("href", response.data["stats"][0])
        self.assertIn("percent", response.data["completion"])
        self.assertIn("badges", response.data["impact"])


class PasswordTests(ApiTestBase):
    def test_change_password_rotates_token(self):
        old = self.authenticate()
        response = self.client.post(
            f"{BASE}/password/change/",
            {
                "old_password": PASSWORD,
                "new_password": "Another-strong-456",
                "new_password_confirm": "Another-strong-456",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.data["token"], old.key)
        self.assertFalse(Token.objects.filter(key=old.key).exists())
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Another-strong-456"))

    def test_change_password_needs_correct_old_password(self):
        self.authenticate()
        response = self.client.post(
            f"{BASE}/password/change/",
            {
                "old_password": "wrong",
                "new_password": "Another-strong-456",
                "new_password_confirm": "Another-strong-456",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("old_password", response.data)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_reset_sends_email_without_revealing_whether_it_exists(self):
        known = self.client.post(
            f"{BASE}/password/reset/", {"email": "existing@example.com"}
        )
        unknown = self.client.post(
            f"{BASE}/password/reset/", {"email": "nobody@example.com"}
        )

        self.assertEqual(known.status_code, 200)
        self.assertEqual(known.data, unknown.data)
        self.assertEqual(len(mail.outbox), 1)


class AvatarTests(ApiTestBase):
    url = f"{BASE}/me/avatar/"

    def upload(self, content, name="a.png"):
        file = io.BytesIO(content)
        file.name = name
        return self.client.post(self.url, {"avatar": file}, format="multipart")

    def test_upload_and_remove(self):
        self.authenticate()
        response = self.upload(PNG)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["avatar_url"].startswith("http"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.avatar.name.endswith(".png"))

        removed = self.client.delete(self.url)
        self.assertEqual(removed.status_code, 204)
        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)

    def test_rejects_non_image(self):
        self.authenticate()
        response = self.upload(b"<script>alert(1)</script>", name="x.png")
        self.assertEqual(response.status_code, 400)
        self.assertIn("avatar", response.data)

    def test_requires_file(self):
        self.authenticate()
        response = self.client.post(self.url, {}, format="multipart")
        self.assertEqual(response.status_code, 400)


class BadgeTests(ApiTestBase):
    def setUp(self):
        super().setUp()
        self.badge = Badge.objects.create(name="Pemula", slug="pemula")
        self.owned = UserBadge.objects.create(user=self.user, badge=self.badge)
        self.other = User.objects.create_user("other", "other@example.com", PASSWORD)
        self.others_badge = UserBadge.objects.create(user=self.other, badge=self.badge)

    def test_collection(self):
        self.authenticate()
        response = self.client.get(f"{BASE}/me/badges/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([b["id"] for b in response.data["earned"]], [self.owned.pk])
        self.assertIsNone(response.data["featured"])

    def test_feature_and_unfeature(self):
        self.authenticate()
        url = f"{BASE}/me/badges/featured/"

        self.assertEqual(
            self.client.post(
                url, {"user_badge": self.owned.pk}, format="json"
            ).status_code,
            200,
        )
        self.owned.refresh_from_db()
        self.assertTrue(self.owned.is_featured)

        self.client.post(url, {"user_badge": None}, format="json")
        self.owned.refresh_from_db()
        self.assertFalse(self.owned.is_featured)

    def test_cannot_feature_someone_elses_badge(self):
        self.authenticate()
        response = self.client.post(
            f"{BASE}/me/badges/featured/",
            {"user_badge": self.others_badge.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.others_badge.refresh_from_db()
        self.assertFalse(self.others_badge.is_featured)
