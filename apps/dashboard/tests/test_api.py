from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.articles.models import Article, ArticleCategory
from apps.challenges.models import (
    Badge,
    Challenge,
    ChallengeParticipation,
    CommunityGoal,
    UserBadge,
)
from apps.donations.models import Campaign, Donation
from apps.feeds.models import Comment, Post
from apps.helpdesk.models import Ticket, TicketAttachment, TicketMessage
from apps.notifications.models import Notification

PASSWORD = "Strong-password-123"
BASE = "/api/v1/dashboard"


class DashboardApiTestBase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            "boss", "boss@example.com", PASSWORD, role=User.Role.ADMIN
        )
        self.other_admin = User.objects.create_user(
            "boss2", "boss2@example.com", PASSWORD, role=User.Role.ADMIN
        )
        self.member = User.objects.create_user(
            "alya", "alya@example.com", PASSWORD, first_name="Alya"
        )
        self.login(self.admin)

    def login(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")


class AccessTests(DashboardApiTestBase):
    PATHS = [
        "/overview/",
        "/helpdesk/tickets/",
        "/helpdesk/tickets/stats/",
        "/challenges/",
        "/badges/",
        "/goals/",
        "/users/",
        "/articles/",
        "/donations/campaigns/",
        "/feeds/posts/",
        "/feeds/comments/",
    ]

    def test_admin_can_open_every_section(self):
        for path in self.PATHS:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(BASE + path).status_code, 200)

    def test_anonymous_gets_401(self):
        self.client.credentials()
        for path in self.PATHS:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(BASE + path).status_code, 401)

    def test_regular_users_get_403(self):
        self.login(self.member)
        for path in self.PATHS:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(BASE + path).status_code, 403)

    def test_writes_are_admin_only_too(self):
        self.login(self.member)
        self.assertEqual(
            self.client.post(f"{BASE}/badges/", {"name": "x"}).status_code, 403
        )
        self.assertEqual(
            self.client.patch(
                f"{BASE}/users/{self.admin.pk}/", {"role": "user"}
            ).status_code,
            403,
        )
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, User.Role.ADMIN)


class OverviewTests(DashboardApiTestBase):
    def test_overview_has_no_web_links(self):
        Ticket.objects.create(requester=self.member, subject="s", description="d")
        response = self.client.get(f"{BASE}/overview/")

        keys = {item["key"]: item for item in response.data["todo"]}
        self.assertEqual(keys["unassigned"]["value"], 1)
        self.assertTrue(all("href" not in item for item in response.data["todo"]))
        self.assertEqual(len(response.data["week"]), 4)


class HelpdeskTests(DashboardApiTestBase):
    def setUp(self):
        super().setUp()
        self.ticket = Ticket.objects.create(
            requester=self.member, subject="Broken", description="it broke"
        )

    def url(self, suffix=""):
        return f"{BASE}/helpdesk/tickets/{self.ticket.id}/{suffix}"

    def test_list_sees_all_tickets_and_filters_by_assignment(self):
        Ticket.objects.create(
            requester=self.member,
            subject="Mine",
            description="x",
            assigned_to=self.admin,
        )
        listing = self.client.get(f"{BASE}/helpdesk/tickets/")
        self.assertEqual(listing.data["count"], 2)

        mine = self.client.get(f"{BASE}/helpdesk/tickets/", {"assignment": "me"})
        self.assertEqual([t["subject"] for t in mine.data["results"]], ["Mine"])
        self.assertTrue(mine.data["results"][0]["is_assigned_to_me"])

        free = self.client.get(
            f"{BASE}/helpdesk/tickets/", {"assignment": "unassigned"}
        )
        self.assertEqual([t["subject"] for t in free.data["results"]], ["Broken"])
        self.assertTrue(free.data["results"][0]["can_assign_to_me"])

    def test_search_matches_requester_email(self):
        found = self.client.get(f"{BASE}/helpdesk/tickets/", {"search": "alya@example"})
        self.assertEqual(found.data["count"], 1)

    def test_stats(self):
        response = self.client.get(f"{BASE}/helpdesk/tickets/stats/")
        self.assertEqual(response.data["kpis"]["unassigned"], 1)

    def test_assign_then_conflict_for_another_admin(self):
        taken = self.client.post(self.url("assign/"))
        self.assertEqual(taken.status_code, 200)
        self.assertTrue(taken.data["is_assigned_to_me"])

        again = self.client.post(self.url("assign/"))
        self.assertEqual(again.status_code, 200)

        self.login(self.other_admin)
        blocked = self.client.post(self.url("assign/"))
        self.assertEqual(blocked.status_code, 409)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.assigned_to, self.admin)

    def test_only_the_coordinator_changes_status(self):
        denied = self.client.patch(self.url(), {"status": "resolved"}, format="json")
        self.assertEqual(denied.status_code, 403)

        self.client.post(self.url("assign/"))
        closed = self.client.patch(self.url(), {"status": "closed"}, format="json")
        self.assertEqual(closed.status_code, 200)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.Status.CLOSED)
        self.assertIsNotNone(self.ticket.closed_at)

        reopened = self.client.patch(
            self.url(), {"status": "in_progress"}, format="json"
        )
        self.assertEqual(reopened.status_code, 200)
        self.ticket.refresh_from_db()
        self.assertIsNone(self.ticket.closed_at)

    def test_status_must_be_settable(self):
        self.client.post(self.url("assign/"))
        response = self.client.patch(self.url(), {"status": "open"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_any_admin_can_delete(self):
        self.login(self.other_admin)
        self.assertEqual(self.client.delete(self.url()).status_code, 204)
        self.assertFalse(Ticket.objects.exists())

    def test_replying_follows_assignment_and_closing_rules(self):
        messages = self.url("messages/")
        self.assertEqual(
            self.client.post(messages, {"message": "hi"}, format="json").status_code,
            403,
        )

        self.client.post(self.url("assign/"))
        sent = self.client.post(messages, {"message": "  On it  "}, format="json")
        self.assertEqual(sent.status_code, 201)
        self.assertEqual(sent.data["message"], "On it")
        self.assertTrue(sent.data["is_admin_response"])

        quoted = self.client.post(
            messages, {"message": "again", "reply_to": sent.data["id"]}, format="json"
        )
        self.assertEqual(quoted.data["reply_to"]["excerpt"], "On it")
        self.assertEqual(len(self.client.get(messages).data), 2)

        Ticket.objects.filter(pk=self.ticket.pk).update(status=Ticket.Status.CLOSED)
        closed = self.client.post(messages, {"message": "late"}, format="json")
        self.assertEqual(closed.status_code, 409)

    def test_reply_to_other_tickets_message_is_rejected(self):
        other = Ticket.objects.create(
            requester=self.member, subject="o", description="o"
        )
        foreign = TicketMessage.objects.create(
            ticket=other, author=self.member, message="private"
        )
        self.client.post(self.url("assign/"))
        response = self.client.post(
            self.url("messages/"),
            {"message": "x", "reply_to": foreign.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_admin_downloads_attachments_with_token(self):
        link = TicketAttachment.objects.create(
            ticket=self.ticket, url="https://x.test/a.png"
        )
        detail = self.client.get(self.url())
        self.assertEqual(detail.data["attachments"][0]["url"], link.url)
        self.assertEqual(
            self.client.get(f"{BASE}/helpdesk/attachments/{link.pk}/").status_code, 404
        )


class ChallengeTests(DashboardApiTestBase):
    def payload(self, **overrides):
        data = {
            "title": "7 hari tanpa plastik",
            "description": "Kurangi plastik",
            "start_date": "2026-01-01",
            "end_date": "2026-01-07",
            "is_published": True,
        }
        data.update(overrides)
        return data

    def test_create_check_in_ignores_target_and_builds_slug(self):
        response = self.client.post(
            f"{BASE}/challenges/", self.payload(goal_target=99), format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["slug"], "7-hari-tanpa-plastik")
        self.assertEqual(response.data["goal_type"], "check_in")
        self.assertIsNone(response.data["goal_target"])
        self.assertEqual(response.data["participants_count"], 0)

    def test_tracked_goal_needs_a_target(self):
        response = self.client.post(
            f"{BASE}/challenges/",
            self.payload(goal_type="articles_read"),
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("goal_target", response.data)

    def test_end_date_cannot_precede_start(self):
        response = self.client.post(
            f"{BASE}/challenges/",
            self.payload(start_date="2026-02-01", end_date="2026-01-01"),
            format="json",
        )
        self.assertIn("end_date", response.data)

    def test_patch_revalidates_against_saved_values(self):
        challenge = Challenge.objects.create(
            title="C",
            description="d",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 7),
        )
        url = f"{BASE}/challenges/{challenge.slug}/"

        bad = self.client.patch(url, {"end_date": "2025-12-01"}, format="json")
        self.assertEqual(bad.status_code, 400)

        no_target = self.client.patch(
            url, {"goal_type": "posts_created"}, format="json"
        )
        self.assertEqual(no_target.status_code, 400)

        ok = self.client.patch(
            url, {"goal_type": "posts_created", "goal_target": 3}, format="json"
        )
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.data["goal_target"], 3)

    def test_list_filters_and_metrics(self):
        today = timezone.localdate()
        Challenge.objects.create(
            title="Running",
            description="d",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=1),
            is_published=True,
        )
        Challenge.objects.create(
            title="Draft",
            description="d",
            start_date=today,
            end_date=today,
            is_published=False,
        )

        active = self.client.get(f"{BASE}/challenges/", {"status": "active"})
        self.assertEqual([c["title"] for c in active.data["results"]], ["Running"])
        self.assertEqual(active.data["metrics"]["total"], 2)
        self.assertEqual(active.data["metrics"]["draft"], 1)

        found = self.client.get(f"{BASE}/challenges/", {"search": "draft"})
        self.assertEqual(found.data["count"], 1)

    def test_delete_blocked_when_it_has_participants(self):
        challenge = Challenge.objects.create(
            title="Busy",
            description="d",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 7),
        )
        ChallengeParticipation.objects.create(challenge=challenge, user=self.member)
        url = f"{BASE}/challenges/{challenge.slug}/"

        self.assertEqual(self.client.delete(url).status_code, 409)
        self.assertTrue(Challenge.objects.filter(pk=challenge.pk).exists())

        challenge.participations.all().delete()
        self.assertEqual(self.client.delete(url).status_code, 204)


class BadgeTests(DashboardApiTestBase):
    def test_create_rejects_case_insensitive_duplicates(self):
        created = self.client.post(
            f"{BASE}/badges/",
            {"name": "Pahlawan", "icon": "trophy", "tone": "gold"},
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data["slug"], "pahlawan")

        duplicate = self.client.post(
            f"{BASE}/badges/", {"name": " PAHLAWAN "}, format="json"
        )
        self.assertEqual(duplicate.status_code, 400)

    def test_update_keeps_own_name_and_rejects_bad_icon(self):
        badge = Badge.objects.create(name="Satu")
        url = f"{BASE}/badges/{badge.slug}/"
        self.assertEqual(
            self.client.patch(
                url, {"name": "Satu", "tone": "gold"}, format="json"
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.patch(url, {"icon": "nope"}, format="json").status_code, 400
        )

    def test_counts_and_delete_guard(self):
        badge = Badge.objects.create(name="Dipakai")
        Challenge.objects.create(
            title="C",
            description="d",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 2),
            badge=badge,
        )
        UserBadge.objects.create(user=self.member, badge=badge)

        detail = self.client.get(f"{BASE}/badges/{badge.slug}/")
        self.assertEqual(detail.data["challenge_count"], 1)
        self.assertEqual(detail.data["holder_count"], 1)
        self.assertEqual(
            self.client.delete(f"{BASE}/badges/{badge.slug}/").status_code, 409
        )

        free = Badge.objects.create(name="Bebas")
        self.assertEqual(
            self.client.delete(f"{BASE}/badges/{free.slug}/").status_code, 204
        )


class GoalTests(DashboardApiTestBase):
    def test_crud_with_progress(self):
        created = self.client.post(
            f"{BASE}/goals/",
            {
                "title": "Baca 10 artikel",
                "goal_type": "articles_read",
                "target": 10,
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data["progress"]["current"], 0)
        self.assertFalse(created.data["progress"]["reached"])

        url = f"{BASE}/goals/{created.data['id']}/"
        self.assertEqual(
            self.client.patch(url, {"target": 0}, format="json").status_code, 400
        )
        self.assertEqual(
            self.client.patch(
                url, {"end_date": "2025-01-01"}, format="json"
            ).status_code,
            400,
        )
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertFalse(CommunityGoal.objects.exists())


class UserTests(DashboardApiTestBase):
    def test_list_filters_and_metrics(self):
        self.member.is_active = False
        self.member.save()

        everyone = self.client.get(f"{BASE}/users/")
        self.assertEqual(everyone.data["metrics"]["total"], 3)
        self.assertEqual(everyone.data["metrics"]["inactive"], 1)

        admins = self.client.get(f"{BASE}/users/", {"role": "admin"})
        self.assertEqual(admins.data["count"], 2)

        inactive = self.client.get(f"{BASE}/users/", {"state": "inactive"})
        self.assertEqual([u["username"] for u in inactive.data["results"]], ["alya"])

        found = self.client.get(f"{BASE}/users/", {"search": "alya@"})
        self.assertEqual(found.data["count"], 1)

    def test_no_secrets_in_user_payload(self):
        payload = self.client.get(f"{BASE}/users/{self.member.pk}/").data
        self.assertNotIn("password", payload)
        self.assertIn("activity", payload)
        self.assertIn("impact", payload["activity"])

    def test_change_role_and_deactivate(self):
        url = f"{BASE}/users/{self.member.pk}/"

        promoted = self.client.patch(url, {"role": "admin"}, format="json")
        self.assertEqual(promoted.status_code, 200)
        self.member.refresh_from_db()
        self.assertEqual(self.member.role, User.Role.ADMIN)

        self.client.patch(url, {"is_active": False}, format="json")
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_active)

    def test_invalid_role_is_rejected(self):
        response = self.client.patch(
            f"{BASE}/users/{self.member.pk}/", {"role": "root"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_cannot_change_yourself_or_a_superuser(self):
        own = self.client.patch(
            f"{BASE}/users/{self.admin.pk}/", {"is_active": False}, format="json"
        )
        self.assertEqual(own.status_code, 403)

        root = User.objects.create_superuser("root", "root@example.com", PASSWORD)
        blocked = self.client.patch(
            f"{BASE}/users/{root.pk}/", {"role": "user"}, format="json"
        )
        self.assertEqual(blocked.status_code, 403)
        root.refresh_from_db()
        self.assertEqual(root.role, User.Role.ADMIN)

    def test_deactivated_account_token_stops_working(self):
        self.login(self.member)
        self.assertEqual(self.client.get("/api/v1/accounts/me/").status_code, 200)

        self.member.is_active = False
        self.member.save()
        self.assertEqual(self.client.get("/api/v1/accounts/me/").status_code, 401)

    def test_user_cannot_be_updated_with_unknown_fields(self):
        self.client.patch(
            f"{BASE}/users/{self.member.pk}/",
            {"is_staff": True, "is_superuser": True, "username": "x"},
            format="json",
        )
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_staff)
        self.assertFalse(self.member.is_superuser)
        self.assertEqual(self.member.username, "alya")


class ReadOnlySectionTests(DashboardApiTestBase):
    def setUp(self):
        super().setUp()
        self.category = ArticleCategory.objects.create(name="Gaya hidup")

    def test_articles_list_puts_pending_first_and_filters(self):
        Article.objects.create(
            title="Old",
            content="c",
            category=self.category,
            author=self.member,
            status=Article.Status.PUBLISHED,
        )
        Article.objects.create(
            title="Waiting",
            content="c",
            category=self.category,
            author=self.member,
            status=Article.Status.PENDING,
        )

        response = self.client.get(f"{BASE}/articles/")
        self.assertEqual(response.data["results"][0]["title"], "Waiting")
        self.assertEqual(response.data["metrics"]["pending"], 1)

        published = self.client.get(f"{BASE}/articles/", {"status": "PUBLISHED"})
        self.assertEqual([a["title"] for a in published.data["results"]], ["Old"])

        by_category = self.client.get(
            f"{BASE}/articles/", {"category": self.category.slug}
        )
        self.assertEqual(by_category.data["count"], 2)
        self.assertEqual(
            self.client.get(f"{BASE}/articles/", {"category": "no-such"}).data["count"],
            2,
        )

    def test_campaigns_progress_and_totals(self):
        campaign = Campaign.objects.create(
            title="Sumur",
            description="d",
            target_amount=Decimal("1000"),
            status=Campaign.Status.PUBLISHED,
        )
        Donation.objects.create(
            campaign=campaign,
            donor=self.member,
            amount=Decimal("250"),
            status=Donation.Status.APPROVED,
        )
        Donation.objects.create(
            campaign=campaign,
            donor=self.member,
            amount=Decimal("100"),
            status=Donation.Status.PENDING,
        )

        response = self.client.get(f"{BASE}/donations/campaigns/")
        row = response.data["results"][0]
        self.assertEqual(row["progress_percent"], 25.0)
        self.assertEqual(row["pending_count"], 1)
        self.assertEqual(row["donor_count"], 1)
        self.assertTrue(row["accepting_donations"])
        self.assertEqual(response.data["metrics"]["pending"], 1)
        self.assertEqual(response.data["metrics"]["open_campaigns"], 1)


class FeedModerationTests(DashboardApiTestBase):
    def setUp(self):
        super().setUp()
        self.post = Post.objects.create(author=self.member, content="Halo dunia")
        self.comment = Comment.objects.create(
            post=self.post, author=self.member, content="komentar"
        )

    def test_lists_with_counts_and_metrics(self):
        posts = self.client.get(f"{BASE}/feeds/posts/")
        self.assertEqual(posts.data["results"][0]["comment_count"], 1)
        self.assertEqual(posts.data["metrics"]["posts"], 1)

        comments = self.client.get(f"{BASE}/feeds/comments/")
        self.assertEqual(comments.data["results"][0]["post"]["excerpt"], "Halo dunia")

        none = self.client.get(f"{BASE}/feeds/posts/", {"search": "zzz"})
        self.assertEqual(none.data["count"], 0)

    def test_delete_post_notifies_author_with_reason(self):
        response = self.client.delete(
            f"{BASE}/feeds/posts/{self.post.pk}/", {"reason": "Spam"}, format="json"
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Post.objects.filter(pk=self.post.pk).exists())
        note = Notification.objects.get(recipient=self.member)
        self.assertEqual(note.kind, Notification.Kind.CONTENT_REMOVED)
        self.assertIn("Spam", note.message)

    def test_delete_comment_without_reason(self):
        response = self.client.delete(f"{BASE}/feeds/comments/{self.comment.pk}/")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Comment.objects.filter(pk=self.comment.pk).exists())
        self.assertNotIn(
            "Alasan", Notification.objects.get(recipient=self.member).message
        )
        self.assertTrue(Post.objects.filter(pk=self.post.pk).exists())

    def test_missing_content_is_404(self):
        response = self.client.delete(
            f"{BASE}/feeds/posts/00000000-0000-0000-0000-000000000000/"
        )
        self.assertEqual(response.status_code, 404)
