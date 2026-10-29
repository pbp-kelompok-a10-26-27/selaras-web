from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.challenges import services
from apps.challenges.models import (
    Challenge,
    ChallengeParticipation,
    ChallengeProgress,
    CommunityGoal,
)
from apps.donations.models import Campaign, Donation
from apps.feeds.models import Comment, Like, Post


class GamificationTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.sari = User.objects.create_user(
            "sari", "sari@example.com", "pw", first_name="Sari"
        )
        self.budi = User.objects.create_user(
            "budi", "budi@example.com", "pw", first_name="Budi"
        )
        self.citra = User.objects.create_user(
            "citra", "citra@example.com", "pw", first_name="Citra"
        )
        self.outsider = User.objects.create_user("eka", "eka@example.com", "pw")
        self.admin = User.objects.create_user(
            "admin", "admin@example.com", "pw", role="admin"
        )
        self.today = timezone.localdate()

    def challenge(self, goal_type, target=None, **extra):
        return Challenge.objects.create(
            title=f"{goal_type} {target}",
            description="x",
            start_date=self.today - timedelta(days=2),
            end_date=self.today + timedelta(days=5),
            is_published=True,
            goal_type=goal_type,
            goal_target=target,
            **extra,
        )

    def join(self, challenge, user, minutes_ago=60):
        participation = ChallengeParticipation.objects.create(
            challenge=challenge, user=user
        )
        ChallengeParticipation.objects.filter(pk=participation.pk).update(
            created_at=timezone.now() - timedelta(minutes=minutes_ago)
        )
        participation.refresh_from_db()
        return participation


class LeaderboardTests(GamificationTestCase):
    def test_ranks_by_progress_with_shared_ranks_and_finishers_first(self):
        challenge = self.challenge(Challenge.GoalType.POSTS_CREATED, 3)
        for user in (self.sari, self.budi, self.citra):
            self.join(challenge, user)
        for _ in range(2):
            Post.objects.create(author=self.budi, content="b")
            Post.objects.create(author=self.citra, content="c")
        for _ in range(3):
            Post.objects.create(author=self.sari, content="s")
        services.evaluate(challenge.participations.get(user=self.sari))

        rows, me, total = services.leaderboard(challenge, viewer=self.citra)
        self.assertEqual(total, 3)
        self.assertEqual([r["user"] for r in rows][0], self.sari)
        self.assertTrue(rows[0]["completed"])
        self.assertEqual([r["rank"] for r in rows], [1, 2, 2])
        self.assertEqual(rows[1]["value"], 2)
        self.assertEqual(rows[1]["percent"], 66)
        self.assertTrue(next(r for r in rows if r["user"] == self.citra)["is_me"])
        self.assertIsNone(me)

    def test_counts_only_after_joining_and_ignores_self_likes(self):
        challenge = self.challenge(Challenge.GoalType.LIKES_RECEIVED, 5)
        post = Post.objects.create(author=self.sari, content="x")
        early = Like.objects.create(post=post, user=self.budi)
        Like.objects.filter(pk=early.pk).update(
            created_at=timezone.now() - timedelta(hours=5)
        )
        self.join(challenge, self.sari)
        Like.objects.create(post=post, user=self.citra)
        Like.objects.create(post=post, user=self.sari)
        rows, _, _ = services.leaderboard(challenge)
        self.assertEqual(rows[0]["value"], 1)

    def test_donation_and_check_in_values(self):
        donate = self.challenge(Challenge.GoalType.DONATION_AMOUNT, 100000)
        self.join(donate, self.sari)
        campaign = Campaign.objects.create(
            title="c", description="d", target_amount=Decimal("1000000")
        )
        Donation.objects.create(
            campaign=campaign,
            donor=self.sari,
            amount=Decimal("40000"),
            status=Donation.Status.APPROVED,
        )
        Donation.objects.create(
            campaign=campaign, donor=self.sari, amount=Decimal("90000")
        )
        rows, _, _ = services.leaderboard(donate)
        self.assertEqual(rows[0]["value"], 40000)

        check_in = self.challenge(Challenge.GoalType.CHECK_IN)
        participation = self.join(check_in, self.budi)
        ChallengeProgress.objects.create(
            participation=participation, progress_date=self.today, is_completed=True
        )
        rows, _, _ = services.leaderboard(check_in)
        self.assertEqual(rows[0]["value"], 1)

    def test_viewer_outside_the_top_gets_their_own_row(self):
        challenge = self.challenge(Challenge.GoalType.COMMENTS_WRITTEN, 5)
        User = get_user_model()
        post = Post.objects.create(author=self.admin, content="x")
        for index in range(11):
            user = User.objects.create_user(f"u{index}", f"u{index}@example.com", "pw")
            self.join(challenge, user)
            Comment.objects.create(post=post, author=user, content="semangat")
        self.join(challenge, self.sari)
        rows, me, total = services.leaderboard(challenge, viewer=self.sari)
        self.assertEqual(len(rows), 10)
        self.assertEqual(total, 12)
        self.assertEqual(me["rank"], 12)
        self.assertEqual(me["value"], 0)

    def test_only_participants_and_admins_see_the_ranking(self):
        challenge = self.challenge(Challenge.GoalType.POSTS_CREATED, 3)
        self.join(challenge, self.sari)
        url = reverse("challenges:detail", args=[challenge.slug])

        self.client.force_login(self.sari)
        response = self.client.get(url)
        self.assertContains(response, 'id="leaderboard"')
        self.assertContains(response, 'aria-current="true"')

        self.client.force_login(self.outsider)
        response = self.client.get(url)
        self.assertNotContains(response, 'id="leaderboard"')
        self.assertContains(response, "Gabung untuk lihat posisimu")

        self.client.force_login(self.admin)
        self.assertContains(self.client.get(url), 'id="leaderboard"')


class CommunityGoalTests(GamificationTestCase):
    def goal(self, goal_type, target, start=-3, end=4, **extra):
        return CommunityGoal.objects.create(
            title=f"Goal {goal_type}",
            goal_type=goal_type,
            target=target,
            start_date=self.today + timedelta(days=start),
            end_date=self.today + timedelta(days=end),
            **extra,
        )

    def test_progress_combines_everyone_and_shows_your_share(self):
        self.goal(Challenge.GoalType.POSTS_CREATED, 4)
        Post.objects.create(author=self.sari, content="a")
        Post.objects.create(author=self.sari, content="b")
        Post.objects.create(author=self.budi, content="c")

        (item,) = services.community_goals(self.sari)
        self.assertEqual(item["current"], 3)
        self.assertEqual(item["percent"], 75)
        self.assertEqual(item["mine"], 2)
        self.assertFalse(item["reached"])

        Post.objects.create(author=self.citra, content="d")
        self.assertTrue(services.community_goals(self.sari)[0]["reached"])

    def test_only_running_published_goals_are_listed(self):
        self.goal(Challenge.GoalType.POSTS_CREATED, 4)
        self.goal(Challenge.GoalType.POSTS_CREATED, 4, start=2, end=5)
        self.goal(Challenge.GoalType.POSTS_CREATED, 4, start=-9, end=-2)
        self.goal(Challenge.GoalType.POSTS_CREATED, 4, is_published=False)
        self.assertEqual(len(services.community_goals(None)), 1)

    def test_goals_appear_on_challenges_and_landing_pages(self):
        self.goal(Challenge.GoalType.ARTICLES_READ, 10)
        challenges = self.client.get(reverse("challenges:list"))
        self.assertContains(challenges, "Target komunitas")
        self.assertContains(challenges, "Masuk untuk ikut menghitung kontribusimu")
        self.client.force_login(self.sari)
        landing = self.client.get(reverse("home"))
        self.assertContains(landing, "Target komunitas")
        self.assertContains(landing, "Kontribusimu")

    def test_admin_manages_goals(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("dashboard:admin_goal_create"),
            {
                "title": "1.000 artikel",
                "goal_type": Challenge.GoalType.ARTICLES_READ,
                "target": 1000,
                "start_date": self.today,
                "end_date": self.today - timedelta(days=1),
                "is_published": "on",
            },
        )
        self.assertContains(response, "tidak boleh sebelum")
        response = self.client.post(
            reverse("dashboard:admin_goal_create"),
            {
                "title": "1.000 artikel",
                "goal_type": Challenge.GoalType.ARTICLES_READ,
                "target": 1000,
                "start_date": self.today,
                "end_date": self.today + timedelta(days=30),
                "is_published": "on",
            },
        )
        self.assertRedirects(response, reverse("dashboard:admin_goal_list"))
        goal = CommunityGoal.objects.get()
        self.assertContains(
            self.client.get(reverse("dashboard:admin_goal_list")), "1.000 artikel"
        )
        self.client.post(reverse("dashboard:admin_goal_delete", args=[goal.pk]))
        self.assertFalse(CommunityGoal.objects.exists())

        self.client.force_login(self.sari)
        self.assertEqual(
            self.client.get(reverse("dashboard:admin_goal_list")).status_code, 403
        )


class ImpactSummaryTests(GamificationTestCase):
    def test_profile_shows_personal_totals(self):
        check_in = self.challenge(Challenge.GoalType.CHECK_IN)
        participation = self.join(check_in, self.sari)
        for offset in (0, 1, 2, 5):
            ChallengeProgress.objects.create(
                participation=participation,
                progress_date=self.today - timedelta(days=offset),
                is_completed=True,
            )
        post = Post.objects.create(author=self.sari, content="x")
        Like.objects.create(post=post, user=self.budi)
        Like.objects.create(post=post, user=self.sari)
        other = Post.objects.create(author=self.budi, content="y")
        Comment.objects.create(post=other, author=self.sari, content="keren")
        Comment.objects.create(post=post, author=self.sari, content="sendiri")

        impact = services.impact_summary(self.sari)
        self.assertEqual(impact["longest_streak"], 3)
        self.assertEqual(impact["challenges_joined"], 1)
        self.assertEqual(impact["posts"], 1)
        self.assertEqual(impact["likes_received"], 1)
        self.assertEqual(impact["encouragements"], 1)

        self.client.force_login(self.sari)
        response = self.client.get(reverse("accounts:profile"))
        self.assertContains(response, 'id="impact"')
        self.assertContains(response, "Streak terpanjang")
