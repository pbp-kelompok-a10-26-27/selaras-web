import uuid
from pathlib import Path

from django.conf import settings
from django.db import models
from django.db.models import Q, UniqueConstraint
from django.db.models.functions import Length
from django.db.models.lookups import GreaterThanOrEqual, LessThanOrEqual

from apps.core.models import TimeStamp


def length_between(field, low, high):
    """Panjang teks low..high. Bukan regex: PostgreSQL menolak .{1,2000} (maks 255)."""
    return Q(
        GreaterThanOrEqual(Length(field), low), LessThanOrEqual(Length(field), high)
    )


def post_image_upload_to(instance, filename):
    extension = Path(filename).suffix.lower()
    return f"posts/{uuid.uuid4().hex}{extension}"


# Photo limits per post (the whole set must fit in MAX_POST_UPLOAD_BYTES)
MAX_POST_IMAGES = 10
MAX_POST_IMAGES_ADMIN = 20
MAX_POST_UPLOAD_BYTES = 10 * 1024 * 1024


class Post(TimeStamp):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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
                condition=length_between("content", 1, 2000),
                name="feed_post_content_length",
            )
        ]

    def __str__(self):
        return f"Post by {self.author}"

    @property
    def is_edited(self):
        return bool(
            self.created_at
            and self.updated_at
            and (self.updated_at - self.created_at).total_seconds() > 60
        )


class PostImage(TimeStamp):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="images")
    image = models.FileField(upload_to=post_image_upload_to, max_length=255)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return f"Image {self.position + 1} of post {self.post_id}"


class Comment(TimeStamp):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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
                condition=length_between("content", 1, 500),
                name="feed_comment_content_length",
            ),
        ]

    @property
    def is_edited(self):
        return bool(
            self.created_at
            and self.updated_at
            and (self.updated_at - self.created_at).total_seconds() > 60
        )


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


class CommentLike(TimeStamp):
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comment_likes",
    )

    class Meta:
        constraints = [
            UniqueConstraint(fields=("comment", "user"), name="unique_comment_like")
        ]
