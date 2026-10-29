from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.articles.models import Article, ArticleCategory, ArticleRead
from apps.notifications.models import Notification


class ArticleReviewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.writer = User.objects.create_user("sari", "sari@example.com", "pw")
        self.reader = User.objects.create_user("budi", "budi@example.com", "pw")
        self.admin = User.objects.create_user(
            "admin", "admin@example.com", "pw", role="admin"
        )
        self.category = ArticleCategory.objects.create(name="Uji review")

    def submit(self, status="PENDING", title="Kebun kecil"):
        self.client.force_login(self.writer)
        return self.client.post(
            reverse("articles:html-create"),
            {
                "title": title,
                "summary": "Ringkas",
                "content": "Isi artikel yang cukup panjang.",
                "category": self.category.pk,
                "status": status,
            },
        )

    def test_starter_categories_exist_so_the_editor_works(self):
        self.client.force_login(self.writer)
        response = self.client.get(reverse("articles:html-create"))
        self.assertContains(response, "Lingkungan")
        self.assertNotContains(response, "Belum ada kategori.")

    def test_user_submission_goes_to_review_and_notifies_admins(self):
        self.submit()
        article = Article.objects.get(title="Kebun kecil")
        self.assertEqual(article.status, Article.Status.PENDING)
        self.assertIsNotNone(article.submitted_at)
        self.assertIsNone(article.published_at)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.admin, kind=Notification.Kind.ARTICLE_SUBMITTED
            ).exists()
        )
        # Pending work is visible to its writer only
        self.assertEqual(
            self.client.get(
                reverse("articles:html-detail", args=[article.slug])
            ).status_code,
            200,
        )
        self.client.force_login(self.reader)
        self.assertEqual(
            self.client.get(
                reverse("articles:html-detail", args=[article.slug])
            ).status_code,
            404,
        )

    def test_users_cannot_publish_directly(self):
        self.submit(status="PUBLISHED")
        self.assertEqual(
            Article.objects.get(title="Kebun kecil").status, Article.Status.PENDING
        )

    def test_admin_approves_or_returns_with_a_note(self):
        self.submit()
        article = Article.objects.get(title="Kebun kecil")
        self.client.force_login(self.admin)
        review_url = reverse("articles:review", args=[article.slug])

        # A rejection needs a note
        self.client.post(review_url, {"decision": "reject"})
        article.refresh_from_db()
        self.assertEqual(article.status, Article.Status.PENDING)

        self.client.post(
            review_url, {"decision": "reject", "review_note": "Tambah foto"}
        )
        article.refresh_from_db()
        self.assertEqual(article.status, Article.Status.REJECTED)
        self.assertEqual(article.reviewed_by, self.admin)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.writer, kind=Notification.Kind.ARTICLE_REJECTED
            ).exists()
        )

        # The writer fixes it and sends it again
        self.client.force_login(self.writer)
        editor = self.client.get(reverse("articles:html-update", args=[article.slug]))
        self.assertContains(editor, "Tambah foto")
        self.client.post(
            reverse("articles:html-update", args=[article.slug]),
            {
                "title": article.title,
                "summary": "Ringkas",
                "content": "Isi yang sudah diperbaiki.",
                "category": self.category.pk,
                "status": "PENDING",
            },
        )
        article.refresh_from_db()
        self.assertEqual(article.status, Article.Status.PENDING)

        self.client.force_login(self.admin)
        self.client.post(review_url, {"decision": "approve"})
        article.refresh_from_db()
        self.assertEqual(article.status, Article.Status.PUBLISHED)
        self.assertIsNotNone(article.published_at)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.writer, kind=Notification.Kind.ARTICLE_APPROVED
            ).exists()
        )

        # Published articles are locked for their (non-admin) writer
        self.client.force_login(self.writer)
        self.assertEqual(
            self.client.get(
                reverse("articles:html-update", args=[article.slug])
            ).status_code,
            403,
        )

    def test_admin_sees_pending_queue_and_review_is_admin_only(self):
        self.submit()
        article = Article.objects.get(title="Kebun kecil")
        self.client.force_login(self.writer)
        forbidden = self.client.post(
            reverse("articles:review", args=[article.slug]), {"decision": "approve"}
        )
        self.assertEqual(forbidden.status_code, 403)

        self.client.force_login(self.admin)
        queue = self.client.get(reverse("articles:html-list") + "?status=PENDING")
        self.assertContains(queue, "Kebun kecil")
        self.assertContains(queue, "Menunggu review · 1")

    def test_my_articles_page(self):
        self.submit(status="DRAFT", title="Draf saya")
        self.submit(title="Kiriman saya")
        response = self.client.get(reverse("articles:mine"))
        self.assertContains(response, "Draf saya")
        self.assertContains(response, "Kiriman saya")
        self.assertContains(response, "Semua · 2")
        filtered = self.client.get(reverse("articles:mine") + "?status=DRAFT")
        self.assertNotContains(filtered, "Kiriman saya")


class ArticleReadTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.reader = User.objects.create_user("budi", "budi@example.com", "pw")
        admin = User.objects.create_user(
            "admin", "admin@example.com", "pw", role="admin"
        )
        category = ArticleCategory.objects.create(name="Baca")
        self.article = Article.objects.create(
            title="Hemat air",
            content="Isi",
            category=category,
            author=admin,
            status=Article.Status.PUBLISHED,
        )

    def test_a_read_counts_once_and_shows_on_cards(self):
        url = reverse("articles:mark-read", args=[self.article.slug])
        self.assertEqual(self.client.post(url).status_code, 302)  # login first

        self.client.force_login(self.reader)
        first = self.client.post(url)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.json()["total_read"], 1)
        again = self.client.post(url)
        self.assertEqual(again.status_code, 200)
        self.assertEqual(ArticleRead.objects.count(), 1)

        listing = self.client.get(reverse("articles:html-list"))
        self.assertContains(listing, "Sudah dibaca")
        detail = self.client.get(
            reverse("articles:html-detail", args=[self.article.slug])
        )
        self.assertContains(detail, "Sudah tercatat sebagai bacaanmu")


class CategoryManagementTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            "admin", "admin@example.com", "pw", role="admin"
        )
        self.client.force_login(self.admin)
        self.url = reverse("articles:categories")

    def test_add_rename_and_protected_delete(self):
        self.client.post(self.url, {"action": "create", "name": "Laut"})
        category = ArticleCategory.objects.get(name="Laut")
        duplicate = self.client.post(self.url, {"action": "create", "name": "laut"})
        self.assertContains(duplicate, "sudah ada")

        self.client.post(
            self.url, {"action": "rename", "id": category.pk, "name": "Laut & Pesisir"}
        )
        category.refresh_from_db()
        self.assertEqual(category.name, "Laut & Pesisir")

        Article.objects.create(
            title="Pantai", content="x", category=category, author=self.admin
        )
        self.client.post(self.url, {"action": "delete", "id": category.pk})
        self.assertTrue(ArticleCategory.objects.filter(pk=category.pk).exists())

    def test_regular_users_cannot_manage_categories(self):
        user = get_user_model().objects.create_user("u", "u@example.com", "pw")
        self.client.force_login(user)
        self.assertEqual(self.client.get(self.url).status_code, 403)
