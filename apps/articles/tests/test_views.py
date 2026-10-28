import json

from django.test import TestCase

from apps.accounts.models import User
from apps.articles.models import Article, ArticleCategory


class ArticleAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="article-admin",
            email="article-admin@example.com",
            password="test-password",
            role=User.Role.ADMIN,
        )
        cls.user = User.objects.create_user(
            username="article-user",
            email="article-user@example.com",
            password="test-password",
            role=User.Role.USER,
        )
        cls.category = ArticleCategory.objects.create(name="Lingkungan")
        cls.published = Article.objects.create(
            title="Published article",
            slug="published-article",
            content="Published content",
            category=cls.category,
            author=cls.admin,
            status=Article.Status.PUBLISHED,
        )
        cls.draft = Article.objects.create(
            title="Draft article",
            slug="draft-article",
            content="Draft content",
            category=cls.category,
            author=cls.admin,
            status=Article.Status.DRAFT,
        )

    def api_detail(self, slug):
        return f"/api/articles/{slug}/"

    def category_detail(self, slug):
        return f"/api/categories/{slug}/"

    def create_article(self, **overrides):
        data = {
            "title": "Reduce household waste",
            "content": "Practical ways to reduce household waste.",
            "category_id": self.category.pk,
            "status": Article.Status.DRAFT,
        }
        data.update(overrides)
        return self.client.post(
            "/api/articles/",
            data=json.dumps(data),
            content_type="application/json",
        )

    def test_public_list_and_detail_only_expose_published_articles(self):
        listing = self.client.get("/api/articles/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(
            [item["slug"] for item in listing.json()["results"]],
            [self.published.slug],
        )
        published_response = self.client.get(self.api_detail(self.published.slug))
        self.assertEqual(published_response.status_code, 200)
        draft_response = self.client.get(self.api_detail(self.draft.slug))
        self.assertEqual(draft_response.status_code, 404)
        self.assertEqual(draft_response.json()["error"]["code"], "ARTICLE_NOT_FOUND")

    def test_admin_can_read_drafts_and_filter_status(self):
        self.client.force_login(self.admin)
        detail = self.client.get(self.api_detail(self.draft.slug))
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["status"], Article.Status.DRAFT)

        listing = self.client.get("/api/articles/?status=DRAFT")
        self.assertEqual(
            [item["slug"] for item in listing.json()["results"]], [self.draft.slug]
        )

    def test_anonymous_and_regular_user_cannot_mutate_articles(self):
        anonymous_responses = [
            self.create_article(),
            self.client.patch(
                self.api_detail(self.published.slug),
                data=json.dumps({"title": "Changed"}),
                content_type="application/json",
            ),
            self.client.delete(self.api_detail(self.published.slug)),
        ]
        for response in anonymous_responses:
            self.assertEqual(response.status_code, 401)
            self.assertEqual(
                response.json()["error"]["code"], "AUTHENTICATION_REQUIRED"
            )

        self.client.force_login(self.user)
        user_responses = [
            self.create_article(),
            self.client.patch(
                self.api_detail(self.published.slug),
                data=json.dumps({"title": "Changed"}),
                content_type="application/json",
            ),
            self.client.delete(self.api_detail(self.published.slug)),
        ]
        for response in user_responses:
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()["error"]["code"], "PERMISSION_DENIED")

    def test_admin_can_create_article_and_publication_timestamp_is_managed(self):
        self.client.force_login(self.admin)
        response = self.create_article(status=Article.Status.PUBLISHED)
        self.assertEqual(response.status_code, 201)
        article = Article.objects.get(pk=response.json()["article"]["id"])
        self.assertEqual(article.slug, "reduce-household-waste")
        first_published_at = article.published_at
        self.assertIsNotNone(first_published_at)

        draft_response = self.client.patch(
            self.api_detail(article.slug),
            data=json.dumps({"status": Article.Status.DRAFT}),
            content_type="application/json",
        )
        self.assertEqual(draft_response.status_code, 200)
        article.refresh_from_db()
        self.assertIsNone(article.published_at)

        republish_response = self.client.patch(
            self.api_detail(article.slug),
            data=json.dumps({"status": Article.Status.PUBLISHED}),
            content_type="application/json",
        )
        self.assertEqual(republish_response.status_code, 200)
        article.refresh_from_db()
        self.assertGreaterEqual(article.published_at, first_published_at)

    def test_validation_errors_and_full_put_requirements(self):
        self.client.force_login(self.admin)
        invalid_create = self.create_article(title=" ")
        self.assertEqual(invalid_create.status_code, 400)
        self.assertEqual(invalid_create.json()["error"]["code"], "VALIDATION_ERROR")

        invalid_put = self.client.put(
            self.api_detail(self.published.slug),
            data=json.dumps({"title": "Incomplete replacement"}),
            content_type="application/json",
        )
        self.assertEqual(invalid_put.status_code, 400)
        self.assertEqual(invalid_put.json()["error"]["code"], "VALIDATION_ERROR")

        full_put = self.client.put(
            self.api_detail(self.published.slug),
            data=json.dumps(
                {
                    "title": self.published.title,
                    "content": self.published.content,
                    "category_id": self.category.pk,
                    "status": Article.Status.PUBLISHED,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(full_put.status_code, 200)
        self.published.refresh_from_db()
        self.assertEqual(self.published.summary, "")

    def test_title_update_changes_slug_and_category_search_pagination_work(self):
        self.client.force_login(self.admin)
        update = self.client.patch(
            self.api_detail(self.published.slug),
            data=json.dumps({"title": "A new article title"}),
            content_type="application/json",
        )
        self.assertEqual(update.status_code, 200)
        self.assertEqual(update.json()["article"]["slug"], "a-new-article-title")

        self.client.logout()
        Article.objects.create(
            title="Second published article",
            slug="second-published-article",
            summary="Searchable summary phrase",
            content="Additional ideas for living sustainably",
            category=self.category,
            author=self.admin,
            status=Article.Status.PUBLISHED,
        )
        for search_term, expected_slug in (
            ("second published", "second-published-article"),
            ("searchable summary", "second-published-article"),
            ("published content", "a-new-article-title"),
        ):
            search_response = self.client.get("/api/articles/", {"search": search_term})
            self.assertEqual(search_response.status_code, 200)
            self.assertEqual(
                [item["slug"] for item in search_response.json()["results"]],
                [expected_slug],
            )

        response = self.client.get(
            "/api/articles/?category=lingkungan&page=1&page_size=1"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["pagination"]["page_size"], 1)
        self.assertEqual(response.json()["pagination"]["total_items"], 2)
        self.assertEqual(response.json()["pagination"]["total_pages"], 2)

    def test_missing_article_and_wrong_method_return_json_errors(self):
        self.client.force_login(self.admin)
        missing = self.client.delete(self.api_detail("missing-article"))
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json()["error"]["code"], "ARTICLE_NOT_FOUND")

        wrong_method = self.client.generic(
            "POST", self.api_detail(self.published.slug), data="{}"
        )
        self.assertEqual(wrong_method.status_code, 405)
        self.assertEqual(wrong_method["Allow"], "GET, PATCH, PUT, DELETE")

    def test_admin_can_delete_article_but_delete_requires_delete_method(self):
        self.client.force_login(self.admin)
        wrong_method = self.client.get(f"/articles/{self.draft.slug}/delete/")
        self.assertEqual(wrong_method.status_code, 405)
        self.assertEqual(wrong_method["Allow"], "DELETE")

        response = self.client.delete(self.api_detail(self.draft.slug))
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertFalse(Article.objects.filter(pk=self.draft.pk).exists())

    def test_category_list_access_and_admin_category_crud(self):
        anonymous = self.client.get("/api/categories/")
        self.assertEqual(anonymous.status_code, 401)

        self.client.force_login(self.user)
        listing = self.client.get("/api/categories/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["results"][0]["slug"], "lingkungan")
        denied = self.client.post(
            "/api/categories/",
            data=json.dumps({"name": "Konsumsi"}),
            content_type="application/json",
        )
        self.assertEqual(denied.status_code, 403)

        self.client.force_login(self.admin)
        created = self.client.post(
            "/api/categories/",
            data=json.dumps({"name": "Konsumsi"}),
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["slug"], "konsumsi")

        duplicate = self.client.post(
            "/api/categories/",
            data=json.dumps({"name": "konsumsi"}),
            content_type="application/json",
        )
        self.assertEqual(duplicate.status_code, 400)

        renamed = self.client.patch(
            self.category_detail("konsumsi"),
            data=json.dumps({"name": "Konsumsi Berkelanjutan"}),
            content_type="application/json",
        )
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(renamed.json()["slug"], "konsumsi-berkelanjutan")

    def test_category_delete_protects_used_categories_and_deletes_unused(self):
        self.client.force_login(self.admin)
        used = self.client.delete(self.category_detail(self.category.slug))
        self.assertEqual(used.status_code, 409)
        self.assertEqual(used.json()["error"]["code"], "CATEGORY_IN_USE")

        unused = ArticleCategory.objects.create(name="Unused")
        deleted = self.client.delete(self.category_detail(unused.slug))
        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(ArticleCategory.objects.filter(pk=unused.pk).exists())
