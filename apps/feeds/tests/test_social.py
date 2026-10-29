from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.feeds.models import Comment, CommentLike, Like, Post
from apps.notifications.models import Notification

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24


def png(name="photo.png", size=None):
    body = PNG if size is None else b"\x89PNG\r\n\x1a\n" + b"\x00" * size
    return SimpleUploadedFile(name, body, content_type="image/png")


class FeedSocialTests(TestCase):
    def setUp(self):
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        media_settings = override_settings(MEDIA_ROOT=media.name)
        media_settings.enable()
        self.addCleanup(media_settings.disable)
        User = get_user_model()
        self.author = User.objects.create_user(
            "sari", "sari@example.com", "pw", first_name="Sari"
        )
        self.reader = User.objects.create_user(
            "budi", "budi@example.com", "pw", first_name="Budi"
        )
        self.admin = User.objects.create_user(
            "admin", "admin@example.com", "pw", role="admin"
        )
        self.post = Post.objects.create(author=self.author, content="Kompos hari ini")

    # ---------------------------------------------------------------- photos

    def test_posts_take_several_photos_with_role_limits(self):
        self.client.force_login(self.reader)
        response = self.client.post(
            reverse("feeds:create"),
            {"content": "Tiga foto", "images": [png(f"{i}.png") for i in range(3)]},
        )
        self.assertRedirects(response, reverse("feeds:list"))
        post = Post.objects.get(content="Tiga foto")
        self.assertEqual(
            list(post.images.values_list("position", flat=True)), [0, 1, 2]
        )

        too_many = self.client.post(
            reverse("feeds:create"),
            {"content": "Banyak", "images": [png(f"{i}.png") for i in range(11)]},
        )
        self.assertEqual(too_many.status_code, 422)
        self.assertContains(too_many, "Maksimal 10 foto", status_code=422)

        self.client.force_login(self.admin)
        admin_post = self.client.post(
            reverse("feeds:create"),
            {"content": "Admin", "images": [png(f"{i}.png") for i in range(15)]},
        )
        self.assertRedirects(admin_post, reverse("feeds:list"))
        self.assertEqual(Post.objects.get(content="Admin").images.count(), 15)

    def test_photo_total_size_is_limited(self):
        self.client.force_login(self.reader)
        response = self.client.post(
            "/api/v1/posts",
            {
                "content": "Berat",
                "images": [
                    png("a.png", 6 * 1024 * 1024),
                    png("b.png", 5 * 1024 * 1024),
                ],
            },
        )
        self.assertEqual(response.status_code, 413)
        self.assertIn("Total ukuran", response.json()["error"]["message"])

    def test_api_returns_all_photo_urls(self):
        self.client.force_login(self.reader)
        response = self.client.post(
            "/api/v1/posts", {"content": "Dua", "images": [png("a.png"), png("b.png")]}
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()["data"]
        self.assertEqual(len(data["images"]), 2)
        self.assertEqual(data["image_url"], data["images"][0])

    def test_carousel_renders_for_several_photos(self):
        self.client.force_login(self.reader)
        self.client.post(
            reverse("feeds:create"),
            {"content": "Galeri", "images": [png("a.png"), png("b.png")]},
        )
        response = self.client.get(reverse("feeds:list"))
        self.assertContains(response, "data-carousel")
        self.assertContains(response, "Foto 2 dari 2")

    # ---------------------------------------------------------------- likes

    def test_likers_list_and_like_notification(self):
        self.client.force_login(self.reader)
        self.client.post(f"/api/v1/posts/{self.post.pk}/like")
        self.client.post(f"/api/v1/posts/{self.post.pk}/like")
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.author, kind=Notification.Kind.POST_LIKED
            ).count(),
            1,
        )

        page = self.client.get(reverse("feeds:likers", args=[self.post.pk]))
        self.assertContains(page, "Budi")
        api = self.client.get(f"/api/v1/posts/{self.post.pk}/likes")
        self.assertEqual(api.json()["data"][0]["name"], "Budi")

        feed = self.client.get(reverse("feeds:list"))
        self.assertContains(feed, "Disukai oleh")
        self.assertContains(feed, reverse("feeds:likers", args=[self.post.pk]))

    def test_liking_your_own_post_does_not_notify(self):
        self.client.force_login(self.author)
        self.client.post(f"/api/v1/posts/{self.post.pk}/like")
        self.assertFalse(Notification.objects.exists())

    def test_comment_likes(self):
        comment = Comment.objects.create(
            post=self.post, author=self.author, content="Semangat"
        )
        self.client.force_login(self.reader)
        liked = self.client.post(f"/api/v1/comments/{comment.pk}/like")
        self.assertEqual(liked.status_code, 201)
        self.assertEqual(liked.json()["data"]["like_count"], 1)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.author, kind=Notification.Kind.COMMENT_LIKED
            ).exists()
        )
        self.assertContains(
            self.client.get(reverse("feeds:comment_likers", args=[comment.pk])),
            "Budi",
        )

        # Without JavaScript the form posts to the page route
        self.client.post(
            reverse("feeds:comment_like", args=[comment.pk]), {"action": "unlike"}
        )
        self.assertFalse(CommentLike.objects.exists())

    # --------------------------------------------------------------- replies

    def test_replies_stay_one_level_and_notify(self):
        root = Comment.objects.create(post=self.post, author=self.reader, content="A")
        reply = Comment.objects.create(
            post=self.post, author=self.author, parent=root, content="B"
        )
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("feeds:reply_create", args=[reply.pk]),
            {"content": "@sari setuju"},
        )
        new_reply = Comment.objects.get(content="@sari setuju")
        self.assertEqual(new_reply.parent, root)
        self.assertRedirects(
            response,
            f"{reverse('feeds:detail', args=[self.post.pk])}#comment-{new_reply.pk}",
            fetch_redirect_response=False,
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.reader, kind=Notification.Kind.COMMENT_REPLIED
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.author, kind=Notification.Kind.POST_COMMENTED
            ).exists()
        )

        detail = self.client.get(reverse("feeds:detail", args=[self.post.pk]))
        self.assertContains(detail, f'id="reply-form-{root.pk}"')
        self.assertContains(detail, "data-reply-to")
        self.assertContains(
            detail, '<span class="font-semibold text-secondary-600">@sari</span>'
        )

    def test_long_threads_mark_extra_replies(self):
        root = Comment.objects.create(post=self.post, author=self.reader, content="A")
        for index in range(4):
            Comment.objects.create(
                post=self.post, author=self.author, parent=root, content=f"R{index}"
            )
        self.client.force_login(self.reader)
        detail = self.client.get(reverse("feeds:detail", args=[self.post.pk]))
        self.assertContains(detail, "data-reply-extra", count=2)
        self.assertContains(detail, "Lihat 2 balasan lainnya")

    # ------------------------------------------------------------------ sort

    def test_popular_sort_orders_by_likes(self):
        quiet = Post.objects.create(author=self.reader, content="Sepi")
        Like.objects.create(post=self.post, user=self.reader)
        Like.objects.create(post=self.post, user=self.admin)
        self.client.force_login(self.reader)
        response = self.client.get(reverse("feeds:list") + "?sort=popular")
        posts = list(response.context["posts"])
        self.assertEqual(posts[0], self.post)
        self.assertIn(quiet, posts)
        self.assertContains(response, "Paling disukai")


class GuestFeedTests(TestCase):
    def setUp(self):
        self.author = get_user_model().objects.create_user(
            "sari", "sari@example.com", "pw", first_name="Sari"
        )
        self.post = Post.objects.create(author=self.author, content="Kompos hari ini")
        self.comment = Comment.objects.create(
            post=self.post, author=self.author, content="Semangat"
        )
        Like.objects.create(post=self.post, user=self.author)
        self.login = reverse("accounts:login")

    def test_guests_can_browse_the_feed(self):
        for url in (reverse("feeds:list"), reverse("feeds:list") + "?sort=popular"):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Kompos hari ini")
            self.assertContains(response, "Mau ikut berbagi cerita?")
            self.assertContains(response, "Masuk untuk menyukai postingan ini")
            self.assertNotContains(response, "data-likers-url")

    def test_guests_are_sent_to_login_for_everything_else(self):
        detail = reverse("feeds:detail", args=[self.post.pk])
        gets = [
            detail,
            reverse("feeds:create"),
            reverse("feeds:likers", args=[self.post.pk]),
            reverse("feeds:comment_likers", args=[self.comment.pk]),
        ]
        for url in gets:
            response = self.client.get(url)
            self.assertRedirects(
                response, f"{self.login}?next={url}", fetch_redirect_response=False
            )

        posts = {
            reverse("feeds:like", args=[self.post.pk]): {"action": "like"},
            reverse("feeds:comment_create", args=[self.post.pk]): {"content": "hai"},
            reverse("feeds:reply_create", args=[self.comment.pk]): {"content": "hai"},
            reverse("feeds:comment_like", args=[self.comment.pk]): {"action": "like"},
        }
        for url, data in posts.items():
            response = self.client.post(url, data)
            self.assertEqual(response.status_code, 302, url)
            self.assertTrue(response["Location"].startswith(self.login), url)
        self.assertEqual(Like.objects.count(), 1)
        self.assertEqual(Comment.objects.count(), 1)

    def test_api_still_answers_guests_with_json(self):
        response = self.client.get("/api/v1/posts")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "UNAUTHENTICATED")
