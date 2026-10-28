from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.accounts.models import User
from apps.articles.models import Article, ArticleCategory, Tag


class ArticleHTMLViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="html-admin",
            email="html-admin@example.com",
            password="test-password",
            role=User.Role.ADMIN,
        )
        cls.user = User.objects.create_user(
            username="html-user",
            email="html-user@example.com",
            password="test-password",
            role=User.Role.USER,
        )
        cls.category = ArticleCategory.objects.create(name="Lingkungan")
        cls.tag = Tag.objects.create(name="Konsumsi Sadar")
        cls.published = Article.objects.create(
            title="Repair a bicycle",
            slug="repair-a-bicycle",
            summary="A practical repair guide",
            content="Repairable things deserve another life.",
            category=cls.category,
            author=cls.admin,
            status=Article.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        cls.published.tags.add(cls.tag)
        cls.draft = Article.objects.create(
            title="Draft bicycle guide",
            slug="draft-bicycle-guide",
            content="Draft content stays private.",
            category=cls.category,
            author=cls.admin,
            status=Article.Status.DRAFT,
        )
        cls.draft.tags.add(Tag.objects.create(name="Draft Only Tag"))

    def test_public_list_searches_filters_paginates_and_only_uses_visible_options(self):
        second = Article.objects.create(
            title="Repair a lamp",
            slug="repair-a-lamp",
            content="A second searchable repair guide.",
            category=self.category,
            author=self.admin,
            status=Article.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        second.tags.add(self.tag)
        hidden_tag = Tag.objects.get(name="Draft Only Tag")

        response = self.client.get(
            reverse("articles:html-list"),
            {
                "search": "bicycle",
                "category": self.category.slug,
                "tag": self.tag.slug,
                "page": 1,
                "page_size": 1,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.published.title)
        self.assertNotContains(response, self.draft.title)
        self.assertNotContains(response, hidden_tag.name)
        self.assertEqual(response.context["page_obj"].paginator.count, 1)
        self.assertEqual(response.context["page_obj"].object_list[0], self.published)
        self.assertContains(response, "Lingkungan")
        self.assertContains(response, "Konsumsi Sadar")

        paginated = self.client.get(
            reverse("articles:html-list"), {"page": 2, "page_size": 1}
        )
        self.assertEqual(paginated.context["page_obj"].number, 2)
        self.assertContains(paginated, 'aria-current="page"')
        self.assertNotEqual(second.pk, self.published.pk)

    def test_public_empty_and_invalid_tag_states_are_rendered(self):
        empty = self.client.get(reverse("articles:html-list"), {"search": "no-match"})
        self.assertEqual(empty.status_code, 200)
        self.assertContains(empty, "Belum ada cerita di sini.")

        invalid = self.client.get(reverse("articles:html-list"), {"tag": "missing-tag"})
        self.assertEqual(invalid.status_code, 400)
        self.assertContains(invalid, "Filter belum dapat diterapkan.", status_code=400)

    def test_draft_detail_is_hidden_from_public_and_available_to_admin(self):
        public_response = self.client.get(
            reverse("articles:html-detail", args=[self.draft.slug])
        )
        self.assertEqual(public_response.status_code, 404)

        self.client.force_login(self.user)
        user_response = self.client.get(
            reverse("articles:html-detail", args=[self.draft.slug])
        )
        self.assertEqual(user_response.status_code, 404)

        self.client.force_login(self.admin)
        admin_response = self.client.get(
            reverse("articles:html-detail", args=[self.draft.slug])
        )
        self.assertEqual(admin_response.status_code, 200)
        self.assertContains(admin_response, "Draf · hanya terlihat oleh admin")

    def test_admin_can_create_and_publish_through_csrf_protected_form(self):
        self.client.force_login(self.admin)
        form_url = reverse("articles:html-create")
        self.assertEqual(self.client.get(form_url).status_code, 200)

        image_data = BytesIO()
        Image.new("RGB", (3, 3), color="green").save(image_data, format="PNG")
        response = self.client.post(
            form_url,
            {
                "title": "A new garden",
                "summary": "Growing close to home",
                "content": "A small garden can make a difference.",
                "category": str(self.category.pk),
                "tags": [str(self.tag.pk)],
                "new_tags": "Urban Nature",
                "status": ["DRAFT", "PUBLISHED"],
                "image": SimpleUploadedFile(
                    "garden.png", image_data.getvalue(), content_type="image/png"
                ),
            },
        )
        self.assertEqual(response.status_code, 302)
        article = Article.objects.get(title="A new garden")
        self.assertEqual(article.status, Article.Status.PUBLISHED)
        self.assertIsNotNone(article.published_at)
        self.assertEqual(
            set(article.tags.values_list("name", flat=True)),
            {"Konsumsi Sadar", "Urban Nature"},
        )
        self.assertTrue(article.image.name.startswith("articles/"))

    def test_admin_update_manages_publication_time_and_delete_uses_post(self):
        self.client.force_login(self.admin)
        first_published_at = self.published.published_at
        update_url = reverse("articles:html-update", args=[self.published.slug])
        response = self.client.post(
            update_url,
            {
                "title": "Updated bicycle guide",
                "summary": "Updated summary",
                "content": "Updated text.",
                "category": str(self.category.pk),
                "tags": [],
                "new_tags": "",
                "status": "DRAFT",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.published.refresh_from_db()
        self.assertEqual(self.published.status, Article.Status.DRAFT)
        self.assertIsNone(self.published.published_at)
        self.assertEqual(self.published.slug, "updated-bicycle-guide")

        republish = self.client.post(
            reverse("articles:html-update", args=[self.published.slug]),
            {
                "title": self.published.title,
                "summary": self.published.summary,
                "content": self.published.content,
                "category": str(self.category.pk),
                "tags": [],
                "new_tags": "",
                "status": "PUBLISHED",
            },
        )
        self.assertEqual(republish.status_code, 302)
        self.published.refresh_from_db()
        self.assertIsNotNone(self.published.published_at)
        self.assertGreaterEqual(self.published.published_at, first_published_at)

        delete_url = reverse("articles:html-delete", args=[self.published.slug])
        self.assertEqual(self.client.get(delete_url).status_code, 405)
        deleted = self.client.post(delete_url)
        self.assertEqual(deleted.status_code, 302)
        self.assertFalse(Article.objects.filter(pk=self.published.pk).exists())

    def test_image_upload_validation_uses_existing_backend_limits(self):
        self.client.force_login(self.admin)
        image_data = BytesIO()
        Image.new("RGB", (2, 2), color="blue").save(image_data, format="JPEG")

        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                valid = self.client.post(
                    reverse("articles:html-create"),
                    {
                        "title": "Image upload article",
                        "content": "Valid image.",
                        "category": str(self.category.pk),
                        "status": "DRAFT",
                        "image": SimpleUploadedFile(
                            "cover.jpg",
                            image_data.getvalue(),
                            content_type="image/jpeg",
                        ),
                    },
                )
                self.assertEqual(valid.status_code, 302)
                article = Article.objects.get(title="Image upload article")
                old_image_path = article.image.path
                replacement_bytes = BytesIO()
                Image.new("RGB", (3, 3), color="orange").save(
                    replacement_bytes, format="JPEG"
                )
                replacement = self.client.post(
                    reverse("articles:html-update", args=[article.slug]),
                    {
                        "title": article.title,
                        "summary": article.summary,
                        "content": article.content,
                        "category": str(self.category.pk),
                        "status": "DRAFT",
                        "image": SimpleUploadedFile(
                            "replacement.jpg",
                            replacement_bytes.getvalue(),
                            content_type="image/jpeg",
                        ),
                    },
                )
                self.assertEqual(replacement.status_code, 302)
                article.refresh_from_db()
                new_image_path = article.image.path
                self.assertFalse(Path(old_image_path).exists())

                deleted = self.client.post(
                    reverse("articles:html-delete", args=[article.slug])
                )
                self.assertEqual(deleted.status_code, 302)
                self.assertFalse(Path(new_image_path).exists())

                invalid = self.client.post(
                    reverse("articles:html-create"),
                    {
                        "title": "Invalid image upload article",
                        "content": "Invalid image.",
                        "category": str(self.category.pk),
                        "status": "DRAFT",
                        "image": SimpleUploadedFile(
                            "fake.png", b"not an image", content_type="image/png"
                        ),
                    },
                )
                self.assertEqual(invalid.status_code, 200)
                self.assertContains(invalid, "gambar JPEG")

    def test_non_admin_cannot_manage_articles_and_api_routes_remain_json(self):
        create_url = reverse("articles:html-create")
        anonymous = self.client.get(create_url)
        self.assertEqual(anonymous.status_code, 302)
        self.assertIn("/accounts/login/", anonymous.url)

        self.client.force_login(self.user)
        forbidden = self.client.get(create_url)
        self.assertEqual(forbidden.status_code, 403)
        denied_delete = self.client.post(
            reverse("articles:html-delete", args=[self.published.slug])
        )
        self.assertEqual(denied_delete.status_code, 403)
        self.assertTrue(Article.objects.filter(pk=self.published.pk).exists())

        self.client.logout()
        api_list = self.client.get("/api/articles/")
        legacy_list = self.client.get("/articles/")
        self.assertEqual(api_list.status_code, 200)
        self.assertEqual(legacy_list.status_code, 200)
        self.assertEqual(api_list["Content-Type"], "application/json")
        self.assertEqual(legacy_list["Content-Type"], "application/json")
        self.assertEqual(
            self.client.get(
                reverse("articles:html-detail", args=[self.published.slug])
            ).status_code,
            200,
        )

    def test_csrf_is_required_for_html_mutation(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)
        response = csrf_client.post(
            reverse("articles:html-create"),
            {
                "title": "CSRF article",
                "content": "This request must be rejected without CSRF.",
                "category": str(self.category.pk),
                "status": "DRAFT",
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Article.objects.filter(title="CSRF article").exists())
