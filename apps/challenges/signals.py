"""Move tracked challenges forward when something happens in another module.

The receivers live here so feeds, donations and articles stay unaware of
challenges. Work runs after the surrounding transaction commits, so a rolled
back save never completes a challenge.
"""

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.articles.models import ArticleRead
from apps.donations.models import Donation
from apps.feeds.models import Comment, Like, Post

from .services import evaluate_user


def _later(user, event):
    transaction.on_commit(lambda: evaluate_user(user, event))


@receiver(post_save, sender=ArticleRead, dispatch_uid="challenge_article_read")
def _article_read(sender, instance, created, **kwargs):
    if created:
        _later(instance.user, "article_read")


@receiver(post_save, sender=Donation, dispatch_uid="challenge_donation")
def _donation_saved(sender, instance, **kwargs):
    if instance.status == Donation.Status.APPROVED:
        _later(instance.donor, "donation_approved")


@receiver(post_save, sender=Post, dispatch_uid="challenge_post_created")
def _post_created(sender, instance, created, **kwargs):
    if created:
        _later(instance.author, "post_created")


@receiver(post_save, sender=Like, dispatch_uid="challenge_like_received")
def _like_created(sender, instance, created, **kwargs):
    if created and instance.user_id != instance.post.author_id:
        _later(instance.post.author, "like_received")


@receiver(post_save, sender=Comment, dispatch_uid="challenge_comment_written")
def _comment_created(sender, instance, created, **kwargs):
    if created:
        _later(instance.author, "comment_written")
