import uuid
from pathlib import Path

from django.conf import settings
from django.db import models
from django.db.models import Q, UniqueConstraint

from apps.core.models import TimeStamp


def post_image_upload_to(instance, filename):
    extension = Path(filename).suffix.lower()
    return f"posts/{uuid.uuid4().hex}{extension}"


class Post(TimeStamp):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts"
    )
    challenge = models.ForeignKey(
        "challenges.Challenge",
        on_delete=models.CASCADE,
        related_name="posts",
        null=True,
        blank=True,
    )
    content = models.TextField()
    image = models.FileField(upload_to=post_image_upload_to, max_length=255, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=("-created_at", "-id"), name="feed_post_created_idx"),
            models.Index(
                fields=("author", "-created_at", "-id"),
                name="feed_post_author_idx",
            ),
            models.Index(
                fields=("challenge", "-created_at", "-id"),
                name="feed_post_challenge_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(content__regex=r"(?s)^.{1,2000}$"),
                name="feed_post_content_length",
            )
        ]

    def __str__(self):
        return f"Post by {self.author}"


class Comment(TimeStamp):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments"
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="replies",
        null=True,
        blank=True,
    )
    content = models.CharField(max_length=500)

    class Meta:
        indexes = [
            models.Index(
                fields=("post", "created_at", "id"), name="feed_comment_post_idx"
            ),
            models.Index(
                fields=("parent", "created_at", "id"),
                name="feed_comment_parent_idx",
            ),
            models.Index(fields=("author",), name="feed_comment_author_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(parent__isnull=True) | ~Q(parent=models.F("pk")),
                name="feed_comment_not_self_parent",
            ),
            models.CheckConstraint(
                condition=Q(content__regex=r"(?s)^.{1,500}$"),
                name="feed_comment_content_length",
            ),
        ]


class Like(TimeStamp):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="post_likes"
    )

    class Meta:
        constraints = [
            UniqueConstraint(fields=("post", "user"), name="unique_post_like")
        ]
        indexes = [models.Index(fields=("user",), name="feed_like_user_idx")]
