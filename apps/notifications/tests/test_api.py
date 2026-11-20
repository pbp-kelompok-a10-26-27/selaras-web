from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.accounts.models import User

from ..models import Notification
from ..services import Kind, notify

BASE = "/api/v1/notifications"


class NotificationApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("sari", "sari@example.com", "pw-12345-x")
        self.actor = User.objects.create_user(
            "budi", "budi@example.com", "pw-12345-x", first_name="Budi"
        )
        self.other = User.objects.create_user("dewi", "dewi@example.com", "pw-12345-x")
        self.login(self.user)

    def login(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_every_endpoint_requires_a_token(self):
        note = notify(self.user, Kind.POST_LIKED, "x", actor=self.actor)
        self.client.credentials()
        for method, path in [
            ("get", f"{BASE}/"),
            ("get", f"{BASE}/unread-count/"),
            ("post", f"{BASE}/read-all/"),
            ("get", f"{BASE}/{note.pk}/"),
            ("post", f"{BASE}/{note.pk}/read/"),
        ]:
            with self.subTest(path=path):
                self.assertEqual(getattr(self.client, method)(path).status_code, 401)

    def test_list_is_newest_first_with_unread_total(self):
        notify(self.user, Kind.POST_COMMENTED, "Lama", actor=self.actor)
        newest = notify(
            self.user, Kind.BADGE_EARNED, "Baru", url="/accounts/profile/#badges"
        )
        response = self.client.get(f"{BASE}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["unread"], 2)
        self.assertEqual(response.data["count"], 2)
        first = response.data["results"][0]
        self.assertEqual(first["id"], str(newest.pk))
        self.assertEqual(first["icon"], "award")
        self.assertEqual(first["tone"], "gold")
        self.assertFalse(first["is_read"])
        self.assertEqual(response.data["results"][1]["actor_name"], "Budi")

    def test_only_own_notifications_are_visible(self):
        theirs = notify(self.other, Kind.POST_LIKED, "private", actor=self.actor)
        notify(self.user, Kind.POST_LIKED, "mine", actor=self.actor)

        titles = [n["title"] for n in self.client.get(f"{BASE}/").data["results"]]
        self.assertEqual(titles, ["mine"])
        self.assertEqual(self.client.get(f"{BASE}/{theirs.pk}/").status_code, 404)
        self.assertEqual(self.client.post(f"{BASE}/{theirs.pk}/read/").status_code, 404)
        theirs.refresh_from_db()
        self.assertFalse(theirs.is_read)

    def test_show_unread_filter(self):
        read = notify(self.user, Kind.POST_LIKED, "read", actor=self.actor)
        notify(self.user, Kind.POST_COMMENTED, "unread", actor=self.actor)
        self.client.post(f"{BASE}/{read.pk}/read/")

        unread = self.client.get(f"{BASE}/", {"show": "unread"})
        self.assertEqual([n["title"] for n in unread.data["results"]], ["unread"])
        everything = self.client.get(f"{BASE}/", {"show": "bogus"})
        self.assertEqual(everything.data["count"], 2)

    def test_pagination(self):
        for i in range(5):
            notify(self.user, Kind.POST_LIKED, f"n{i}", actor=self.actor)
        response = self.client.get(f"{BASE}/", {"page_size": 2})
        self.assertEqual(len(response.data["results"]), 2)
        self.assertIsNotNone(response.data["next"])
        self.assertEqual(response.data["unread"], 5)

    def test_reading_detail_does_not_mark_read_but_post_does(self):
        note = notify(self.user, Kind.POST_LIKED, "x", actor=self.actor)
        notify(self.user, Kind.POST_COMMENTED, "y", actor=self.actor)

        self.assertEqual(self.client.get(f"{BASE}/{note.pk}/").data["is_read"], False)
        self.assertEqual(self.client.get(f"{BASE}/unread-count/").data["unread"], 2)

        marked = self.client.post(f"{BASE}/{note.pk}/read/")
        self.assertEqual(marked.status_code, 200)
        self.assertTrue(marked.data["is_read"])
        self.assertEqual(marked.data["unread"], 1)
        self.assertEqual(self.client.get(f"{BASE}/unread-count/").data["unread"], 1)

    def test_marking_twice_keeps_first_read_time(self):
        note = notify(self.user, Kind.POST_LIKED, "x", actor=self.actor)
        first = self.client.post(f"{BASE}/{note.pk}/read/").data["read_at"]
        second = self.client.post(f"{BASE}/{note.pk}/read/").data["read_at"]
        self.assertEqual(first, second)

    def test_read_all_only_touches_own_notifications(self):
        notify(self.user, Kind.POST_LIKED, "a", actor=self.actor)
        notify(self.user, Kind.POST_COMMENTED, "b", actor=self.actor)
        theirs = notify(self.other, Kind.POST_LIKED, "c", actor=self.actor)

        response = self.client.post(f"{BASE}/read-all/")

        self.assertEqual(response.data, {"marked": 2, "unread": 0})
        theirs.refresh_from_db()
        self.assertFalse(theirs.is_read)

    def test_links_are_limited_to_site_paths(self):
        cases = {
            "/feed/": "/feed/",
            "https://evil.example/": "",
            "//evil.example/": "",
            "/\\evil.example": "",
            "javascript:alert(1)": "",
            "": "",
        }
        for stored, expected in cases.items():
            with self.subTest(stored=stored):
                Notification.objects.all().delete()
                note = notify(self.user, Kind.POST_LIKED, "x", url=stored)
                shown = self.client.get(f"{BASE}/{note.pk}/").data["url"]
                self.assertEqual(shown, expected)

    def test_api_is_read_only_for_content(self):
        note = notify(self.user, Kind.POST_LIKED, "x", actor=self.actor)
        for method in ("put", "patch", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(f"{BASE}/{note.pk}/")
                self.assertEqual(response.status_code, 405)
        self.assertTrue(Notification.objects.filter(pk=note.pk).exists())
