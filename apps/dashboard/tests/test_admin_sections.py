from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.articles.models import Article, ArticleCategory
from apps.donations.models import Campaign, Donation
from apps.feeds.models import Comment, Post
from apps.notifications.models import Notification


class AdminSectionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            "boss", "boss@example.com", "x", role="admin", first_name="Bos"
        )
        cls.member = User.objects.create_user(
            "alya", "alya@example.com", "x", first_name="Alya"
        )
        cls.category = ArticleCategory.objects.create(name="Gaya hidup")

    def setUp(self):
        self.client.force_login(self.admin)


class AccessTests(AdminSectionTestCase):
    def test_new_sections_are_admin_only(self):
        urls = [
            reverse("dashboard:admin_user_list"),
            reverse("dashboard:admin_user_detail", args=[self.member.pk]),
            reverse("dashboard:admin_article_list"),
            reverse("dashboard:admin_donation_list"),
            reverse("dashboard:admin_feed_list"),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.member)
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_sidebar_has_no_coming_soon_sections(self):
        response = self.client.get(reverse("dashboard:home"))
        self.assertNotContains(response, "Segera</span>")
        # Overview reuses the sidebar's "Kelola" items
        self.assertContains(response, reverse("dashboard:admin_feed_list"))

    def test_overview_lists_what_needs_attention(self):
        Article.objects.create(
            title="Kompos",
            content="x",
            author=self.member,
            status="PENDING",
            category=self.category,
        )
        response = self.client.get(reverse("dashboard:home"))
        self.assertContains(response, "Perlu tindakan")
        self.assertContains(response, "Artikel menunggu review")
        todo = {item["key"]: item["value"] for item in response.context["todo"]}
        self.assertEqual(todo["articles"], 1)


class UserManagementTests(AdminSectionTestCase):
    def test_search_and_role_filter(self):
        url = reverse("dashboard:admin_user_list")
        response = self.client.get(url, {"search": "alya"})
        self.assertContains(response, "@alya")
        self.assertNotContains(response, "@boss")
        response = self.client.get(url, {"role": "admin"})
        self.assertContains(response, "@boss")
        self.assertNotContains(response, "@alya")
        # Unknown filter values fall back to "all"
        self.assertEqual(self.client.get(url, {"role": "x"}).status_code, 200)

    def test_promote_and_demote(self):
        url = reverse("dashboard:admin_user_role", args=[self.member.pk])
        self.client.post(url, {"role": "admin"})
        self.member.refresh_from_db()
        self.assertTrue(self.member.is_admin)
        self.client.post(url, {"role": "user"})
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_admin)

    def test_cannot_change_own_account_or_superuser(self):
        self.client.post(
            reverse("dashboard:admin_user_role", args=[self.admin.pk]),
            {"role": "user"},
        )
        self.client.post(
            reverse("dashboard:admin_user_active", args=[self.admin.pk]),
            {"active": "0"},
        )
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_admin)
        self.assertTrue(self.admin.is_active)

        root = User.objects.create_superuser("root", "root@example.com", "x")
        self.client.post(
            reverse("dashboard:admin_user_active", args=[root.pk]), {"active": "0"}
        )
        root.refresh_from_db()
        self.assertTrue(root.is_active)

    def test_deactivate_blocks_login_and_reactivate(self):
        url = reverse("dashboard:admin_user_active", args=[self.member.pk])
        response = self.client.post(
            url, {"active": "0", "next": "/dashboard/users/?state=inactive"}
        )
        self.assertRedirects(response, "/dashboard/users/?state=inactive")
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_active)

        self.client.post(url, {"active": "1"})
        self.member.refresh_from_db()
        self.assertTrue(self.member.is_active)

    def test_external_next_is_ignored(self):
        response = self.client.post(
            reverse("dashboard:admin_user_active", args=[self.member.pk]),
            {"active": "0", "next": "https://evil.example/"},
        )
        self.assertRedirects(response, reverse("dashboard:admin_user_list"))

    def test_actions_are_post_only(self):
        url = reverse("dashboard:admin_user_role", args=[self.member.pk])
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_detail_shows_activity(self):
        Post.objects.create(author=self.member, content="Bawa tumbler hari ini")
        response = self.client.get(
            reverse("dashboard:admin_user_detail", args=[self.member.pk])
        )
        self.assertContains(response, "Bawa tumbler hari ini")
        self.assertContains(response, "Jadikan admin")


class ArticleManagementTests(AdminSectionTestCase):
    def setUp(self):
        super().setUp()
        self.pending = Article.objects.create(
            title="Menunggu",
            content="x",
            author=self.member,
            status="PENDING",
            category=self.category,
        )
        self.published = Article.objects.create(
            title="Sudah terbit",
            content="x",
            author=self.admin,
            status="PUBLISHED",
            category=self.category,
        )

    def test_pending_articles_come_first_and_filter_works(self):
        url = reverse("dashboard:admin_article_list")
        articles = list(self.client.get(url).context["page_obj"])
        self.assertEqual(articles[0], self.pending)
        response = self.client.get(url, {"status": "PUBLISHED"})
        self.assertContains(response, "Sudah terbit")
        self.assertNotContains(response, "Menunggu</a>")

    def test_approve_from_dashboard_returns_to_list(self):
        back = reverse("dashboard:admin_article_list") + "?status=PENDING"
        response = self.client.post(
            reverse("articles:review", args=[self.pending.slug]),
            {"decision": "approve", "next": back},
        )
        self.assertRedirects(response, back)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, "PUBLISHED")

    def test_delete_from_dashboard_returns_to_list(self):
        back = reverse("dashboard:admin_article_list")
        response = self.client.post(
            reverse("articles:html-delete", args=[self.published.slug]),
            {"next": back},
        )
        self.assertRedirects(response, back)
        self.assertFalse(Article.objects.filter(pk=self.published.pk).exists())


class DonationManagementTests(AdminSectionTestCase):
    def test_overview_totals_and_queue(self):
        campaign = Campaign.objects.create(
            title="Pohon",
            description="d",
            target_amount=Decimal("1000000"),
            status=Campaign.Status.PUBLISHED,
        )
        Donation.objects.create(
            campaign=campaign,
            donor=self.member,
            amount=Decimal("250000"),
            status=Donation.Status.APPROVED,
        )
        Donation.objects.create(
            campaign=campaign, donor=self.member, amount=Decimal("50000")
        )
        response = self.client.get(reverse("dashboard:admin_donation_list"))
        self.assertEqual(response.context["totals"]["collected"], Decimal("250000"))
        self.assertEqual(response.context["totals"]["pending"], 1)
        self.assertEqual(response.context["totals"]["open_campaigns"], 1)
        campaign_row = response.context["page_obj"][0]
        self.assertEqual(campaign_row.progress, 25)
        self.assertContains(response, "Perlu diverifikasi")

        queue = self.client.get(
            reverse("donations:verification_queue"), {"search": "alya"}
        )
        self.assertEqual(queue.context["page_obj"].paginator.count, 2)
        # The sidebar marks Donasi active outside /dashboard/
        self.assertContains(
            queue, 'data-sidebar-key="donations"\n            aria-current="page"'
        )


class FeedModerationTests(AdminSectionTestCase):
    def setUp(self):
        super().setUp()
        self.post = Post.objects.create(author=self.member, content="Isi melanggar")
        self.comment = Comment.objects.create(
            post=self.post, author=self.member, content="Komentar kasar"
        )

    def test_posts_and_comments_tabs(self):
        url = reverse("dashboard:admin_feed_list")
        self.assertContains(self.client.get(url), "Isi melanggar")
        response = self.client.get(url, {"tab": "comments", "search": "kasar"})
        self.assertContains(response, "Komentar kasar")

    def test_delete_post_notifies_author_with_reason(self):
        self.client.post(
            reverse("dashboard:admin_feed_post_delete", args=[self.post.pk]),
            {"reason": "Spam"},
        )
        self.assertFalse(Post.objects.exists())
        notice = Notification.objects.get(recipient=self.member)
        self.assertEqual(notice.kind, Notification.Kind.CONTENT_REMOVED)
        self.assertIn("Alasan: Spam", notice.message)

    def test_delete_comment(self):
        response = self.client.post(
            reverse("dashboard:admin_feed_comment_delete", args=[self.comment.pk])
        )
        self.assertRedirects(
            response, reverse("dashboard:admin_feed_list") + "?tab=comments"
        )
        self.assertFalse(Comment.objects.exists())

    def test_members_cannot_moderate(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("dashboard:admin_feed_post_delete", args=[self.post.pk])
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Post.objects.exists())
