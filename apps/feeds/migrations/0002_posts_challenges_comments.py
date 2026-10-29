import apps.feeds.models
from django.db import migrations, models
import django.db.models.deletion


def ensure_legacy_posts_are_empty_or_assigned(apps, schema_editor):
    Post = apps.get_model("feeds", "Post")
    if Post.objects.filter(challenge__isnull=True).exists():
        raise RuntimeError(
            "Feed migration needs existing posts to be assigned to a challenge "
            "before the challenge field can be required."
        )


class Migration(migrations.Migration):
    dependencies = [
        ("challenges", "0001_initial"),
        ("feeds", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="post",
            name="challenge",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="posts",
                to="challenges.challenge",
            ),
        ),
        migrations.AddField(
            model_name="post",
            name="image",
            field=models.FileField(
                blank=True,
                max_length=255,
                upload_to=apps.feeds.models.post_image_upload_to,
            ),
        ),
        migrations.AddField(
            model_name="comment",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="replies",
                to="feeds.comment",
            ),
        ),
        migrations.AlterField(
            model_name="comment",
            name="content",
            field=models.CharField(max_length=500),
        ),
        migrations.AddIndex(
            model_name="post",
            index=models.Index(
                fields=["-created_at", "-id"], name="feed_post_created_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="post",
            index=models.Index(
                fields=["author", "-created_at", "-id"], name="feed_post_author_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="post",
            index=models.Index(
                fields=["challenge", "-created_at", "-id"],
                name="feed_post_challenge_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="comment",
            index=models.Index(
                fields=["post", "created_at", "id"], name="feed_comment_post_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="comment",
            index=models.Index(
                fields=["parent", "created_at", "id"],
                name="feed_comment_parent_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="comment",
            index=models.Index(fields=["author"], name="feed_comment_author_idx"),
        ),
        migrations.AddIndex(
            model_name="like",
            index=models.Index(fields=["user"], name="feed_like_user_idx"),
        ),
        migrations.AddConstraint(
            model_name="post",
            constraint=models.CheckConstraint(
                condition=models.Q(("content__regex", r"(?s)^.{1,2000}$")),
                name="feed_post_content_length",
            ),
        ),
        migrations.AddConstraint(
            model_name="comment",
            constraint=models.CheckConstraint(
                condition=models.Q(("content__regex", r"(?s)^.{1,500}$")),
                name="feed_comment_content_length",
            ),
        ),
        migrations.AddConstraint(
            model_name="comment",
            constraint=models.CheckConstraint(
                condition=models.Q(("parent__isnull", True))
                | ~models.Q(("parent", models.F("pk"))),
                name="feed_comment_not_self_parent",
            ),
        ),
        migrations.RunPython(ensure_legacy_posts_are_empty_or_assigned, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="post",
            name="challenge",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="posts",
                to="challenges.challenge",
            ),
        ),
    ]
