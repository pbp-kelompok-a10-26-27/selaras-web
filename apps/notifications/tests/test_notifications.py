from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.notifications.models import Notification
from apps.notifications.services import Kind, notify, notify_admins, unread_count


class NotificationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("sari", "sari@example.com", "pw")
        self.actor = User.objects.create_user("budi", "budi@example.com", "pw")
        self.admin = User.objects.create_user(
            "admin", "admin@example.com", "pw", role="admin"
        )

    def test_never_notifies_yourself_and_dedupes_repeats(self):
        self.assertIsNone(notify(self.user, Kind.POST_LIKED, "x", actor=self.user))
        notify(self.user, Kind.POST_LIKED, "x", actor=self.actor, dedupe_key="post:1")
        notify(self.user, Kind.POST_LIKED, "x", actor=self.actor, dedupe_key="post:1")
        self.assertEqual(Notification.objects.count(), 1)

    def test_admins_are_notified_without_the_actor(self):
        notify_admins(Kind.ARTICLE_SUBMITTED, "Baru", actor=self.admin)
        self.assertFalse(Notification.objects.exists())
        notify_admins(Kind.ARTICLE_SUBMITTED, "Baru", actor=self.user)
        self.assertEqual(Notification.objects.get().recipient, self.admin)

    def test_bell_count_feed_open_and_read_all(self):
        first = notify(self.user, Kind.POST_COMMENTED, "Komentar", url="/feed/")
        notify(self.user, Kind.BADGE_EARNED, "Lencana baru: Hemat")
        self.client.force_login(self.user)

        page = self.client.get(reverse("feeds:list"))
        self.assertContains(page, "data-bell-count")
        self.assertContains(page, "2 belum dibaca")

        feed = self.client.get(reverse("notifications:feed")).json()
        self.assertEqual(feed["unread"], 2)
        self.assertIn('data-kind="badge_earned"', feed["html"])

        opened = self.client.get(reverse("notifications:open", args=[first.pk]))
        self.assertRedirects(opened, "/feed/", fetch_redirect_response=False)
        self.assertEqual(unread_count(self.user), 1)

        self.client.post(reverse("notifications:read_all"))
        self.assertEqual(unread_count(self.user), 0)

    def test_people_only_see_their_own_notifications(self):
        mine = notify(self.user, Kind.POST_LIKED, "Halo")
        self.client.force_login(self.actor)
        self.assertEqual(
            self.client.get(reverse("notifications:open", args=[mine.pk])).status_code,
            404,
        )
        self.assertNotContains(self.client.get(reverse("notifications:list")), "Halo")

    def test_offsite_links_are_not_followed(self):
        item = notify(self.user, Kind.POST_LIKED, "x", url="https://evil.example/")
        self.client.force_login(self.user)
        response = self.client.get(reverse("notifications:open", args=[item.pk]))
        self.assertRedirects(response, reverse("notifications:list"))

    def test_list_filters_unread(self):
        notify(self.user, Kind.POST_LIKED, "Belum")
        read = notify(self.user, Kind.POST_LIKED, "Sudah")
        self.client.force_login(self.user)
        self.client.get(reverse("notifications:open", args=[read.pk]))
        response = self.client.get(reverse("notifications:list") + "?show=unread")
        self.assertContains(response, "Belum")
        self.assertNotContains(response, "Sudah")
