import json
from datetime import date
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.test.client import BOUNDARY, encode_multipart
from django.urls import reverse

from apps.challenges.models import Challenge, ChallengeParticipation
from apps.feeds.models import Comment, Like, Post


class FeedApiTests(TestCase):
    def setUp(self):
        media_directory = TemporaryDirectory()
        self.addCleanup(media_directory.cleanup)
        media_settings = override_settings(MEDIA_ROOT=media_directory.name)
        media_settings.enable()
        self.addCleanup(media_settings.disable)
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="feed-user",
            email="feed-user@example.com",
            password="test-password",
        )
        self.other_user = user_model.objects.create_user(
            username="other-user",
            email="other-user@example.com",
            password="test-password",
        )
        self.admin = user_model.objects.create_user(
            username="feed-admin",
            email="feed-admin@example.com",
            password="test-password",
            role="admin",
        )
        self.challenge = Challenge.objects.create(
            title="Zero Waste Week",
            description="Reduce waste.",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 31),
            is_published=True,
        )
        ChallengeParticipation.objects.create(challenge=self.challenge, user=self.user)
        self.post = Post.objects.create(
            author=self.other_user,
            challenge=self.challenge,
            content="Progress update",
        )
        self.client.force_login(self.user)

    def test_create_requires_participation_and_trims_content(self):
        path = "/api/v1/posts"
        data = {"content": "  My progress  ", "challenge_id": str(self.challenge.pk)}
        body = encode_multipart(BOUNDARY, data)
        response = self.client.post(
            path,
            body,
            content_type=f"multipart/form-data; boundary={BOUNDARY}",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["data"]["content"], "My progress")
        self.assertEqual(Post.objects.filter(author=self.user).count(), 1)

        self.client.force_login(self.other_user)
        response = self.client.post(
            path,
            body,
            content_type=f"multipart/form-data; boundary={BOUNDARY}",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "NOT_CHALLENGE_PARTICIPANT")

    def test_api_rejects_images_larger_than_10_mb(self):
        image = SimpleUploadedFile(
            "large.png",
            b"\x89PNG\r\n\x1a\n" + b"\x00" * (10 * 1024 * 1024),
            content_type="image/png",
        )
        response = self.client.post(
            "/api/v1/posts",
            {
                "content": "Large photo",
                "challenge_id": str(self.challenge.pk),
                "image": image,
            },
        )
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["error"]["code"], "PAYLOAD_TOO_LARGE")

    def test_feed_form_rejects_images_larger_than_10_mb(self):
        image = SimpleUploadedFile(
            "large.png",
            b"\x89PNG\r\n\x1a\n" + b"\x00" * (10 * 1024 * 1024),
            content_type="image/png",
        )
        response = self.client.post(
            reverse("feeds:create"),
            {
                "content": "Large photo",
                "image": image,
            },
        )
        self.assertEqual(response.status_code, 422)
        self.assertContains(response, "Ukuran foto maksimal 10 MB.", status_code=422)

    def test_create_without_challenge_is_allowed(self):
        body = encode_multipart(BOUNDARY, {"content": "Standalone post"})
        response = self.client.post(
            "/api/v1/posts",
            body,
            content_type=f"multipart/form-data; boundary={BOUNDARY}",
        )
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.json()["data"]["challenge"])
        self.assertIsNone(Post.objects.get(author=self.user).challenge)

    def test_feed_page_button_opens_post_form_and_accepts_upload(self):
        response = self.client.get(reverse("feeds:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "+ Buat postingan")
        self.assertContains(response, "feed-create-link")
        self.assertContains(response, reverse("feeds:create"))

        response = self.client.get(reverse("feeds:create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Challenge (opsional)")
        self.assertContains(response, 'type="file"')
        self.assertContains(response, "feed-image-input")
        self.assertContains(response, "::file-selector-button")
        self.assertContains(response, "maksimal 10 MB")
        self.assertContains(response, "Submit Postingan")
        self.assertContains(response, "feed-submit-button")

        image = SimpleUploadedFile(
            "progress.png",
            b"\x89PNG\r\n\x1a\n" + b"\x00" * 24,
            content_type="image/png",
        )
        response = self.client.post(
            reverse("feeds:create"),
            {
                "challenge": str(self.challenge.pk),
                "content": "  Progress from the page  ",
                "image": image,
            },
        )
        self.assertRedirects(response, reverse("feeds:list"))
        created = Post.objects.get(author=self.user)
        self.assertEqual(created.content, "Progress from the page")
        self.assertTrue(created.image.name.startswith("posts/"))

    def test_feed_form_allows_post_without_challenge(self):
        self.client.force_login(self.other_user)
        response = self.client.post(
            reverse("feeds:create"),
            {"content": "Standalone from the feed"},
        )
        self.assertRedirects(response, reverse("feeds:list"))
        created = Post.objects.get(
            author=self.other_user, content="Standalone from the feed"
        )
        self.assertIsNone(created.challenge)

    def test_admin_cannot_create_post_from_feed_page(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("feeds:list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Buat postingan")
        response = self.client.get(reverse("feeds:create"))
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            reverse("feeds:create"),
            {"challenge": str(self.challenge.pk), "content": "Admin post"},
        )
        self.assertEqual(response.status_code, 403)

    def test_comment_reply_depth_and_owner_rules(self):
        root_response = self.client.post(
            f"/api/v1/posts/{self.post.pk}/comments",
            data=json.dumps({"content": " Nice work! "}),
            content_type="application/json",
        )
        self.assertEqual(root_response.status_code, 201)
        root_id = root_response.json()["data"]["id"]

        reply_response = self.client.post(
            f"/api/v1/comments/{root_id}/replies",
            data=json.dumps({"content": "Thank you!"}),
            content_type="application/json",
        )
        self.assertEqual(reply_response.status_code, 201)
        reply_id = reply_response.json()["data"]["id"]

        nested_response = self.client.post(
            f"/api/v1/comments/{reply_id}/replies",
            data=json.dumps({"content": "Nested reply"}),
            content_type="application/json",
        )
        self.assertEqual(nested_response.status_code, 422)
        self.assertEqual(
            nested_response.json()["error"]["code"], "REPLY_DEPTH_EXCEEDED"
        )

        self.client.force_login(self.other_user)
        edit_response = self.client.patch(
            f"/api/v1/comments/{root_id}",
            data=json.dumps({"content": "Changed"}),
            content_type="application/json",
        )
        self.assertEqual(edit_response.status_code, 403)
        self.assertEqual(edit_response.json()["error"]["code"], "NOT_OWNER")

    def test_comment_list_returns_root_comments_with_one_reply_level(self):
        root = Comment.objects.create(
            post=self.post, author=self.user, content="Root comment"
        )
        Comment.objects.create(
            post=self.post,
            author=self.other_user,
            parent=root,
            content="Reply",
        )
        response = self.client.get(f"/api/v1/posts/{self.post.pk}/comments")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], root.pk)
        self.assertEqual(data[0]["replies"][0]["content"], "Reply")
        self.assertNotIn("replies", data[0]["replies"][0])

    def test_like_is_idempotent_and_count_is_returned(self):
        path = f"/api/v1/posts/{self.post.pk}/like"
        first = self.client.post(path)
        second = self.client.post(path)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["data"]["like_count"], 1)
        self.assertEqual(Like.objects.filter(post=self.post).count(), 1)

        unlike = self.client.delete(path)
        self.assertEqual(unlike.status_code, 200)
        self.assertFalse(unlike.json()["data"]["liked"])
        self.assertEqual(unlike.json()["data"]["like_count"], 0)

    def test_admin_can_moderate_but_cannot_like(self):
        self.client.force_login(self.admin)
        forbidden_like = self.client.post(f"/api/v1/posts/{self.post.pk}/like")
        self.assertEqual(forbidden_like.status_code, 403)
        self.assertEqual(forbidden_like.json()["error"]["code"], "FORBIDDEN_ROLE")

        deleted = self.client.delete(f"/api/v1/admin/posts/{self.post.pk}")
        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(Post.objects.filter(pk=self.post.pk).exists())

    def test_post_list_validation_and_owner_filter(self):
        response = self.client.get("/api/v1/posts?page=0")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["details"][0]["field"], "page")

        response = self.client.get("/api/v1/posts?mine=true")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"], [])

    def test_post_list_includes_aggregates_and_owner_edit_delete(self):
        Like.objects.create(post=self.post, user=self.user)
        Comment.objects.create(post=self.post, author=self.user, content="Progress!")
        response = self.client.get("/api/v1/posts")
        post_data = response.json()["data"][0]
        self.assertEqual(post_data["like_count"], 1)
        self.assertEqual(post_data["comment_count"], 1)
        self.assertTrue(post_data["liked_by_me"])
        self.assertFalse(post_data["is_owner"])

        owned_post = Post.objects.create(
            author=self.user, challenge=self.challenge, content="Before"
        )
        body = encode_multipart(BOUNDARY, {"content": "After"})
        update = self.client.generic(
            "PATCH",
            f"/api/v1/posts/{owned_post.pk}",
            body,
            content_type=f"multipart/form-data; boundary={BOUNDARY}",
        )
        self.assertEqual(update.status_code, 200)
        owned_post.refresh_from_db()
        self.assertEqual(owned_post.content, "After")
        unchanged_timestamp = owned_post.updated_at
        unchanged_body = encode_multipart(BOUNDARY, {"content": "After"})
        self.client.generic(
            "PATCH",
            f"/api/v1/posts/{owned_post.pk}",
            unchanged_body,
            content_type=f"multipart/form-data; boundary={BOUNDARY}",
        )
        owned_post.refresh_from_db()
        self.assertEqual(owned_post.updated_at, unchanged_timestamp)

        deleted = self.client.delete(f"/api/v1/posts/{owned_post.pk}")
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(deleted.content, b"")
        self.assertFalse(Post.objects.filter(pk=owned_post.pk).exists())

    def test_admin_search_hides_admin_like_and_exposes_all_posts(self):
        self.client.force_login(self.admin)
        response = self.client.get("/api/v1/admin/posts?q=Progress")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["data"]), 1)
        self.assertFalse(response.json()["data"][0]["liked_by_me"])
        self.assertFalse(response.json()["data"][0]["is_owner"])

    def test_unauthenticated_requests_use_api_error_shape(self):
        self.client.logout()
        response = self.client.get("/api/v1/posts")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "UNAUTHENTICATED")

    def test_htmx_receives_partial_html_and_empty_delete_response(self):
        response = self.client.get("/api/v1/posts", HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"<div"))
        self.assertIn(b"Progress update", response.content)

        self.client.force_login(self.other_user)
        deleted = self.client.delete(
            f"/api/v1/posts/{self.post.pk}",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.content, b"")
