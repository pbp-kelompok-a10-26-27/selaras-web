from django.conf import settings
from django.db import models
from django.db.models import UniqueConstraint

from apps.core.models import TimeStamp


class Post(TimeStamp):
	author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts")
	content = models.TextField()

	def __str__(self):
		return f"Post by {self.author}"


class Like(TimeStamp):
	post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="post_likes")

	class Meta:
		constraints = [UniqueConstraint(fields=("post", "user"), name="unique_post_like")]


class Comment(TimeStamp):
	post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
	author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments")
	content = models.TextField()
