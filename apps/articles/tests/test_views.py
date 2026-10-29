import json
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.test.client import BOUNDARY, MULTIPART_CONTENT, encode_multipart
from PIL import Image

from apps.accounts.models import User
from apps.articles.models import Article, ArticleCategory, Tag


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
        # Start without the starter categories seeded by migration 0004
        ArticleCategory.objects.all().delete()
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
            "tags": [],
            "new_tags": [],
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

    def test_admin_can_assign_existing_and_new_tags_on_create_and_update(self):
        self.client.force_login(self.admin)
        existing = Tag.objects.create(name="Climate Action")
        response = self.create_article(tags=[existing.slug], new_tags=["Zero Waste"])
        self.assertEqual(response.status_code, 201)
        article = Article.objects.get(pk=response.json()["article"]["id"])
        self.assertEqual(
            {tag.slug for tag in article.tags.all()},
            {"climate-action", "zero-waste"},
        )
        self.assertEqual(
            {tag["slug"] for tag in response.json()["article"]["tags"]},
            {"climate-action", "zero-waste"},
        )

        replacement = Tag.objects.create(name="Circular Economy")
        update = self.client.patch(
            self.api_detail(article.slug),
            data=json.dumps({"tags": [replacement.slug], "new_tags": ["Regeneration"]}),
            content_type="application/json",
        )
        self.assertEqual(update.status_code, 200)
        article.refresh_from_db()
        self.assertEqual(
            set(article.tags.values_list("slug", flat=True)),
            {replacement.slug, "regeneration"},
        )
        detail = self.client.get(self.api_detail(article.slug))
        self.assertEqual(
            {tag["slug"] for tag in detail.json()["tags"]},
            {replacement.slug, "regeneration"},
        )

    def test_new_tag_names_are_case_insensitively_reused_and_slugs_are_unique(self):
        self.client.force_login(self.admin)
        first = self.create_article(new_tags=["Low Waste"])
        second = self.create_article(
            title="Another waste guide", new_tags=["LOW WASTE"]
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(Tag.objects.filter(name__iexact="low waste").count(), 1)

        collision = self.create_article(
            title="Low waste naming collision",
            new_tags=["Circular Economy", "Circular-Economy"],
        )
        self.assertEqual(collision.status_code, 201)
        self.assertTrue(Tag.objects.filter(slug="circular-economy").exists())
        self.assertTrue(Tag.objects.filter(slug="circular-economy-2").exists())

        duplicate_names = self.create_article(new_tags=["Reuse", "reuse"])
        self.assertEqual(duplicate_names.status_code, 400)
        self.assertEqual(Tag.objects.filter(name__iexact="reuse").count(), 0)

    def test_tag_filter_combines_with_search_category_admin_status_and_pagination(self):
        self.client.force_login(self.admin)
        tag = Tag.objects.create(name="Repair")
        published = Article.objects.create(
            title="Repair old furniture",
            slug="repair-old-furniture",
            summary="repair guide",
            content="Searchable furniture repair",
            category=self.category,
            author=self.admin,
            status=Article.Status.PUBLISHED,
        )
        published.tags.add(tag)
        other = Article.objects.create(
            title="Repair bicycles",
            slug="repair-bicycles",
            content="Repair guide",
            category=self.category,
            author=self.admin,
            status=Article.Status.PUBLISHED,
        )
        other.tags.add(tag)
        draft = Article.objects.create(
            title="Repair draft",
            slug="repair-draft",
            content="Searchable draft repair",
            category=self.category,
            author=self.admin,
            status=Article.Status.DRAFT,
        )
        draft.tags.add(tag)

        response = self.client.get(
            "/api/articles/",
            {
                "tag": tag.slug,
                "search": "repair",
                "category": self.category.slug,
                "status": Article.Status.PUBLISHED,
                "page": 1,
                "page_size": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["pagination"]["total_items"], 2)
        self.assertEqual(response.json()["pagination"]["total_pages"], 2)
        self.assertEqual(len(response.json()["results"]), 1)

        self.client.logout()
        public_results = self.client.get(
            "/api/articles/", {"tag": tag.slug, "search": "repair"}
        ).json()["results"]
        self.assertEqual(
            {item["slug"] for item in public_results}, {published.slug, other.slug}
        )
        self.assertNotIn(draft.slug, {item["slug"] for item in public_results})

        self.client.force_login(self.admin)
        draft_results = self.client.get(
            "/api/articles/", {"tag": tag.slug, "status": Article.Status.DRAFT}
        ).json()["results"]
        self.assertEqual([item["slug"] for item in draft_results], [draft.slug])

    def test_unknown_and_invalid_tag_references_return_validation_errors(self):
        self.client.force_login(self.admin)
        unknown_assignment = self.create_article(tags=["no-such-tag"])
        self.assertEqual(unknown_assignment.status_code, 400)
        self.assertEqual(
            unknown_assignment.json()["error"]["details"]["tags"],
            ["Slug tag tidak dikenal: no-such-tag."],
        )
        invalid_array = self.create_article(tags="not-an-array")
        self.assertEqual(invalid_array.status_code, 400)
        unknown_filter = self.client.get("/api/articles/?tag=no-such-tag")
        self.assertEqual(unknown_filter.status_code, 400)
        self.assertEqual(
            unknown_filter.json()["error"]["code"], "INVALID_QUERY_PARAMETER"
        )

    def test_non_admin_cannot_create_tags_or_change_article_tag_associations(self):
        before = Tag.objects.count()
        anonymous = self.create_article(new_tags=["Must Not Be Created"])
        self.assertEqual(anonymous.status_code, 401)

        self.client.force_login(self.user)
        denied_create = self.create_article(new_tags=["Must Not Be Created"])
        denied_update = self.client.patch(
            self.api_detail(self.published.slug),
            data=json.dumps({"new_tags": ["Must Not Be Created"]}),
            content_type="application/json",
        )
        self.assertEqual(denied_create.status_code, 403)
        self.assertEqual(denied_update.status_code, 403)
        self.assertEqual(Tag.objects.count(), before)

    def test_legacy_mutation_routes_return_json_auth_errors_and_method_errors(self):
        anonymous = self.client.post(
            "/articles/create/",
            data="{",
            content_type="application/json",
        )
        self.assertEqual(anonymous.status_code, 401)
        self.assertEqual(anonymous.json()["error"]["code"], "AUTHENTICATION_REQUIRED")

        self.client.force_login(self.user)
        forbidden = self.client.patch(
            f"/articles/{self.published.slug}/edit/",
            data=json.dumps({"title": "Denied"}),
            content_type="application/json",
        )
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(forbidden.json()["error"]["code"], "PERMISSION_DENIED")

        self.client.force_login(self.admin)
        legacy_method = self.client.post("/articles/api/articles/", data={})
        self.assertEqual(legacy_method.status_code, 405)
        self.assertEqual(legacy_method.json()["error"]["code"], "METHOD_NOT_ALLOWED")

    def test_unexpected_api_errors_are_logged_and_return_generic_json(self):
        self.client.force_login(self.admin)
        with patch(
            "apps.articles.views.Article.objects.create",
            side_effect=RuntimeError("private database detail"),
        ):
            response = self.create_article(title="Trigger failure")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error"]["code"], "INTERNAL_ERROR")
        self.assertNotIn("private database detail", response.content.decode())

    def test_csrf_rejection_for_mutations_uses_json_api_error(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)
        response = csrf_client.post(
            "/api/articles/",
            data=json.dumps(
                {
                    "title": "CSRF protected article",
                    "content": "Body",
                    "category_id": self.category.pk,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "PERMISSION_DENIED")

    def test_model_slug_generation_handles_collisions_and_renames(self):
        self.client.force_login(self.admin)
        first_category = ArticleCategory.objects.create(name="Clean Energy")
        second_category = ArticleCategory.objects.create(name="Clean-Energy")
        self.assertEqual(first_category.slug, "clean-energy")
        self.assertEqual(second_category.slug, "clean-energy-2")

        second_category.name = "Circular Energy"
        second_category.save(update_fields={"name"})
        self.assertEqual(second_category.slug, "circular-energy")

        first_tag = Tag.objects.create(name="Low Waste")
        second_tag = Tag.objects.create(name="Low-Waste")
        self.assertEqual(first_tag.slug, "low-waste")
        self.assertEqual(second_tag.slug, "low-waste-2")
        second_tag.name = "Reuse More"
        second_tag.save(update_fields={"name"})
        self.assertEqual(second_tag.slug, "reuse-more")

        first_article = Article.objects.create(
            title="Reuse Guide",
            content="First article.",
            category=self.category,
            author=self.admin,
        )
        second_article = Article.objects.create(
            title="Reuse-Guide",
            content="Second article.",
            category=self.category,
            author=self.admin,
        )
        self.assertEqual(first_article.slug, "reuse-guide")
        self.assertEqual(second_article.slug, "reuse-guide-2")
        second_article.title = "Repair Guide"
        second_article.save(update_fields={"title"})
        self.assertEqual(second_article.slug, "repair-guide")

    def test_image_file_upload_is_validated_and_returned_as_a_media_url(self):
        self.client.force_login(self.admin)
        image_bytes = BytesIO()
        Image.new("RGB", (2, 2), color="green").save(image_bytes, format="PNG")
        valid_image = image_bytes.getvalue()

        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                response = self.client.post(
                    "/api/articles/",
                    {
                        "title": "Image article",
                        "content": "Article with an uploaded image.",
                        "category_id": str(self.category.pk),
                        "status": Article.Status.DRAFT,
                        "tags": "[]",
                        "new_tags": "[]",
                        "image": SimpleUploadedFile(
                            "cover.png", valid_image, content_type="image/png"
                        ),
                    },
                )
                self.assertEqual(response.status_code, 201)
                article = Article.objects.get(pk=response.json()["article"]["id"])
                self.assertTrue(article.image.name.startswith("articles/"))
                self.assertTrue(article.image.storage.exists(article.image.name))
                self.assertTrue(
                    response.json()["article"]["image"].endswith(article.image.name)
                )

                previous_image_path = article.image.path
                replacement_bytes = BytesIO()
                Image.new("RGB", (3, 3), color="blue").save(
                    replacement_bytes, format="JPEG"
                )
                replacement_body = encode_multipart(
                    BOUNDARY,
                    {
                        "image": SimpleUploadedFile(
                            "replacement.jpg",
                            replacement_bytes.getvalue(),
                            content_type="image/jpeg",
                        )
                    },
                )
                replacement = self.client.generic(
                    "PATCH",
                    self.api_detail(article.slug),
                    data=replacement_body,
                    content_type=MULTIPART_CONTENT,
                )
                self.assertEqual(replacement.status_code, 200)
                article.refresh_from_db()
                self.assertTrue(article.image.name.endswith(".jpg"), article.image.name)
                self.assertFalse(Path(previous_image_path).exists())

                invalid = self.client.post(
                    "/api/articles/",
                    {
                        "title": "Invalid image article",
                        "content": "Invalid image.",
                        "category_id": str(self.category.pk),
                        "image": SimpleUploadedFile(
                            "fake.png", b"not an image", content_type="image/png"
                        ),
                    },
                )
                self.assertEqual(invalid.status_code, 400)

                current_image_path = article.image.path
                deleted = self.client.delete(self.api_detail(article.slug))
                self.assertEqual(deleted.status_code, 204)
                self.assertFalse(Path(current_image_path).exists())

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
