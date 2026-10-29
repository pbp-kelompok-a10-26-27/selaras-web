from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.articles.models import Article, ArticleCategory, ArticleRead
from apps.challenges import services
from apps.challenges.forms import ChallengeForm
from apps.challenges.models import (
    Badge,
    Challenge,
    ChallengeParticipation,
    ChallengeProgress,
    UserBadge,
)
from apps.donations.models import Campaign, Donation
from apps.donations.services import verify_pending_donation
from apps.feeds.models import Comment, Like, Post
from apps.notifications.models import Notification


class TrackingTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("sari", "sari@example.com", "pw")
        self.other = User.objects.create_user("budi", "budi@example.com", "pw")
        self.admin = User.objects.create_user(
            "admin", "admin@example.com", "pw", role="admin"
        )
        self.badge = Badge.objects.create(name="Bookworm", icon="book-open")
        today = timezone.localdate()
        self.start, self.end = today - timedelta(days=1), today + timedelta(days=6)

    def challenge(self, goal_type, target=None, **extra):
        return Challenge.objects.create(
            title=f"{goal_type} challenge",
            description="Do it.",
            start_date=self.start,
            end_date=self.end,
            is_published=True,
            goal_type=goal_type,
            goal_target=target,
            badge=extra.pop("badge", self.badge),
            **extra,
        )

    def join(self, challenge, user=None):
        return ChallengeParticipation.objects.create(
            challenge=challenge, user=user or self.user
        )


class MetricTests(TrackingTestCase):
    def test_articles_read_completes_and_awards_badge_with_notification(self):
        challenge = self.challenge(Challenge.GoalType.ARTICLES_READ, target=2)
        participation = self.join(challenge)
        category = ArticleCategory.objects.create(name="Uji coba")
        articles = [
            Article.objects.create(
                title=f"A{i}",
                content="isi",
                category=category,
                author=self.admin,
                status=Article.Status.PUBLISHED,
            )
            for i in range(2)
        ]
        with self.captureOnCommitCallbacks(execute=True):
            ArticleRead.objects.create(user=self.user, article=articles[0])
        participation.refresh_from_db()
        self.assertIsNone(participation.completed_at)
        self.assertEqual(services.get_progress(participation)["current"], 1)

        with self.captureOnCommitCallbacks(execute=True):
            ArticleRead.objects.create(user=self.user, article=articles[1])
        participation.refresh_from_db()
        self.assertIsNotNone(participation.completed_at)
        earned = UserBadge.objects.get(user=self.user, badge=self.badge)
        self.assertEqual(earned.challenge, challenge)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.user, kind=Notification.Kind.BADGE_EARNED
            ).exists()
        )

    def test_only_approved_donations_count(self):
        challenge = self.challenge(Challenge.GoalType.DONATION_AMOUNT, target=100000)
        participation = self.join(challenge)
        campaign = Campaign.objects.create(
            title="Pohon",
            description="x",
            target_amount=Decimal("1000000"),
            status=Campaign.Status.PUBLISHED,
        )
        donation = Donation.objects.create(
            campaign=campaign, donor=self.user, amount=Decimal("150000")
        )
        self.assertEqual(services.get_progress(participation)["current"], 0)

        with self.captureOnCommitCallbacks(execute=True):
            self.assertTrue(
                verify_pending_donation(
                    donation.pk, Donation.Status.APPROVED, admin=self.admin
                )
            )
        participation.refresh_from_db()
        self.assertEqual(services.get_progress(participation)["current"], 150000)
        self.assertIsNotNone(participation.completed_at)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.user, kind=Notification.Kind.DONATION_APPROVED
            ).exists()
        )

    def test_likes_on_own_posts_and_comments_on_own_posts_dont_count(self):
        likes = self.join(self.challenge(Challenge.GoalType.LIKES_RECEIVED, 5))
        comments = self.join(
            self.challenge(Challenge.GoalType.COMMENTS_WRITTEN, 5, badge=None)
        )
        own_post = Post.objects.create(author=self.user, content="mine")
        others_post = Post.objects.create(author=self.other, content="theirs")
        Like.objects.create(post=own_post, user=self.user)
        Like.objects.create(post=own_post, user=self.other)
        Comment.objects.create(post=own_post, author=self.user, content="self")
        Comment.objects.create(post=others_post, author=self.user, content="hi")

        self.assertEqual(services.get_progress(likes)["current"], 1)
        self.assertEqual(services.get_progress(comments)["current"], 1)

    def test_activity_before_joining_is_not_counted(self):
        before = Post.objects.create(author=self.user, content="before")
        Post.objects.filter(pk=before.pk).update(
            created_at=timezone.now() - timedelta(minutes=5)
        )
        participation = self.join(self.challenge(Challenge.GoalType.POSTS_CREATED, 2))
        self.assertEqual(services.get_progress(participation)["current"], 0)
        Post.objects.create(author=self.user, content="after")
        self.assertEqual(services.get_progress(participation)["current"], 1)

    def test_challenge_without_badge_still_completes_and_notifies(self):
        challenge = self.challenge(Challenge.GoalType.POSTS_CREATED, 1, badge=None)
        participation = self.join(challenge)
        with self.captureOnCommitCallbacks(execute=True):
            Post.objects.create(author=self.user, content="done")
        participation.refresh_from_db()
        self.assertIsNotNone(participation.completed_at)
        self.assertFalse(UserBadge.objects.filter(user=self.user).exists())
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.user, kind=Notification.Kind.CHALLENGE_COMPLETED
            ).exists()
        )


class CheckInTests(TrackingTestCase):
    def test_check_in_completion_awards_the_challenge_badge(self):
        challenge = Challenge.objects.create(
            title="Two days",
            description="x",
            start_date=timezone.localdate() - timedelta(days=1),
            end_date=timezone.localdate(),
            is_published=True,
            badge=self.badge,
        )
        participation = self.join(challenge)
        ChallengeProgress.objects.create(
            participation=participation,
            progress_date=timezone.localdate() - timedelta(days=1),
            is_completed=True,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("challenges:progress", args=[challenge.slug]),
            {"notes": "done"},
            follow=True,
        )
        self.assertContains(response, "Kamu dapat lencana “Bookworm”")
        self.assertTrue(UserBadge.objects.filter(user=self.user, badge=self.badge))

    def test_streaks(self):
        participation = self.join(self.challenge(Challenge.GoalType.CHECK_IN))
        today = timezone.localdate()
        for offset in (0, 1, 2, 5, 6):
            ChallengeProgress.objects.create(
                participation=participation,
                progress_date=today - timedelta(days=offset),
                is_completed=True,
            )
        self.assertEqual(services.check_in_streaks(participation), (3, 3))

    def test_tracked_challenge_rejects_check_ins(self):
        challenge = self.challenge(Challenge.GoalType.POSTS_CREATED, 3)
        self.join(challenge)
        self.client.force_login(self.user)
        self.client.post(reverse("challenges:progress", args=[challenge.slug]))
        self.assertFalse(ChallengeProgress.objects.exists())

    def test_detail_page_shows_goal_and_action(self):
        challenge = self.challenge(Challenge.GoalType.ARTICLES_READ, 3)
        self.join(challenge)
        self.client.force_login(self.user)
        response = self.client.get(reverse("challenges:detail", args=[challenge.slug]))
        self.assertContains(response, "Artikel dibaca")
        self.assertContains(response, "dari <strong>3</strong> artikel")
        self.assertContains(response, reverse("articles:html-list"))
        self.assertContains(response, "Bookworm")


class FormAndBadgeAdminTests(TrackingTestCase):
    def test_tracked_goal_needs_a_target_and_slugs_are_unique(self):
        data = {
            "title": "Same",
            "description": "x",
            "start_date": self.start,
            "end_date": self.end,
            "goal_type": Challenge.GoalType.POSTS_CREATED,
        }
        form = ChallengeForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn("goal_target", form.errors)

        first = ChallengeForm({**data, "goal_target": 3}).save()
        second = ChallengeForm({**data, "goal_target": 3}).save()
        self.assertNotEqual(first.slug, second.slug)

    def test_admin_badge_crud_and_owned_badges_are_protected(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("dashboard:admin_badge_create"),
            {"name": "Tree Hugger", "icon": "trees", "tone": "gold"},
        )
        self.assertRedirects(response, reverse("dashboard:admin_badge_list"))
        badge = Badge.objects.get(name="Tree Hugger")
        self.assertEqual(badge.slug, "tree-hugger")
        self.assertContains(
            self.client.get(reverse("dashboard:admin_badge_list")), "Tree Hugger"
        )

        UserBadge.objects.create(user=self.user, badge=badge)
        self.client.post(reverse("dashboard:admin_badge_delete", args=[badge.slug]))
        self.assertTrue(Badge.objects.filter(pk=badge.pk).exists())

        self.client.force_login(self.user)
        forbidden = self.client.get(reverse("dashboard:admin_badge_list"))
        self.assertEqual(forbidden.status_code, 403)


class FeaturedBadgeTests(TrackingTestCase):
    def test_one_featured_badge_shown_next_to_the_name(self):
        other_badge = Badge.objects.create(name="Gardener")
        first = UserBadge.objects.create(user=self.user, badge=self.badge)
        second = UserBadge.objects.create(user=self.user, badge=other_badge)
        not_mine = UserBadge.objects.create(user=self.other, badge=self.badge)
        self.client.force_login(self.user)
        url = reverse("accounts:featured_badge")

        self.client.post(url, {"user_badge": first.pk})
        self.client.post(url, {"user_badge": second.pk})
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.is_featured)
        self.assertTrue(second.is_featured)

        # Someone else's badge can't be featured
        self.client.post(url, {"user_badge": not_mine.pk})
        not_mine.refresh_from_db()
        self.assertFalse(not_mine.is_featured)

        self.client.post(url, {"user_badge": second.pk})
        Post.objects.create(author=self.user, content="hello")
        feed = self.client.get(reverse("feeds:list"))
        self.assertContains(feed, "data-badge-chip")
        self.assertContains(feed, "Gardener")

        profile = self.client.get(reverse("accounts:profile"))
        self.assertContains(profile, 'id="badges"')
        self.assertContains(profile, "Pasang di samping nama")
