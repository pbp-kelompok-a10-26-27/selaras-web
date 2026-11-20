import io

from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.accounts.models import User

from ..models import Ticket, TicketAttachment, TicketMessage

PASSWORD = "Strong-password-123"
BASE = "/api/v1/helpdesk"

# 1x1 transparent PNG
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe"
    b"\x02\xfe\xa7\x9a\xa0\xa0\x00\x00\x00\x00IEND\xaeB`\x82"
)


def png(name="shot.png"):
    file = io.BytesIO(PNG)
    file.name = name
    return file


class HelpdeskApiTestBase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("sari", "sari@example.com", PASSWORD)
        self.other = User.objects.create_user("budi", "budi@example.com", PASSWORD)
        self.admin = User.objects.create_user(
            "admin", "admin@example.com", PASSWORD, role=User.Role.ADMIN
        )
        self.mine = Ticket.objects.create(
            requester=self.user, subject="Mine", description="my problem"
        )
        self.theirs = Ticket.objects.create(
            requester=self.other, subject="Theirs", description="their problem"
        )

    def login(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def url(self, ticket, suffix=""):
        return f"{BASE}/tickets/{ticket.id}/{suffix}"


class TicketListTests(HelpdeskApiTestBase):
    def test_requires_authentication(self):
        for path in (f"{BASE}/tickets/", f"{BASE}/", f"{BASE}/tickets/stats/"):
            self.assertEqual(self.client.get(path).status_code, 401)

    def test_user_only_sees_own_tickets(self):
        self.login(self.user)
        response = self.client.get(f"{BASE}/tickets/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([t["subject"] for t in response.data["results"]], ["Mine"])
        self.assertEqual(response.data["count"], 1)

    def test_admin_sees_all_tickets(self):
        self.login(self.admin)
        response = self.client.get(f"{BASE}/tickets/")
        self.assertEqual(response.data["count"], 2)

    def test_filters_search_and_message_count(self):
        TicketMessage.objects.create(ticket=self.mine, author=self.user, message="hi")
        Ticket.objects.create(
            requester=self.user,
            subject="Urgent",
            description="x",
            priority=Ticket.Priority.HIGH,
            status=Ticket.Status.CLOSED,
        )
        self.login(self.user)

        high = self.client.get(f"{BASE}/tickets/", {"priority": "high"})
        self.assertEqual([t["subject"] for t in high.data["results"]], ["Urgent"])

        closed = self.client.get(f"{BASE}/tickets/", {"status": "closed"})
        self.assertEqual(closed.data["count"], 1)

        found = self.client.get(f"{BASE}/tickets/", {"search": "my problem"})
        self.assertEqual(found.data["results"][0]["messages_count"], 1)

    def test_pagination(self):
        for i in range(12):
            Ticket.objects.create(requester=self.user, subject=f"T{i}", description="x")
        self.login(self.user)

        response = self.client.get(f"{BASE}/tickets/", {"page_size": 5})
        self.assertEqual(len(response.data["results"]), 5)
        self.assertEqual(response.data["count"], 13)
        self.assertIsNotNone(response.data["next"])

    def test_stats_are_scoped_to_the_user(self):
        self.login(self.user)
        response = self.client.get(f"{BASE}/tickets/stats/")
        stats = {s["key"]: s["value"] for s in response.data["stats"]}
        self.assertEqual(stats["open"], 1)


class TicketCreateTests(HelpdeskApiTestBase):
    url = f"{BASE}/tickets/"

    def test_create_with_json(self):
        self.login(self.user)
        response = self.client.post(
            self.url,
            {"subject": "Help", "description": "It broke", "priority": "high"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        ticket = Ticket.objects.get(subject="Help")
        self.assertEqual(ticket.requester, self.user)
        self.assertEqual(response.data["messages_count"], 0)
        self.assertEqual(ticket.status, Ticket.Status.OPEN)

    def test_cannot_set_status_or_assignee(self):
        self.login(self.user)
        self.client.post(
            self.url,
            {
                "subject": "Help",
                "description": "x",
                "status": "closed",
                "assigned_to": self.admin.pk,
                "requester": self.other.pk,
            },
            format="json",
        )
        ticket = Ticket.objects.get(subject="Help")
        self.assertEqual(ticket.status, Ticket.Status.OPEN)
        self.assertIsNone(ticket.assigned_to)
        self.assertEqual(ticket.requester, self.user)

    def test_validation_errors(self):
        self.login(self.user)
        response = self.client.post(
            self.url, {"subject": "", "description": "x" * 5001}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("subject", response.data)
        self.assertIn("description", response.data)

    def test_create_with_screenshot_and_link(self):
        self.login(self.user)
        response = self.client.post(
            self.url,
            {
                "subject": "Shots",
                "description": "see attached",
                "attachments": [png()],
                "image_links": ["https://example.com/a.png"],
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        ticket = Ticket.objects.get(subject="Shots")
        self.assertEqual(ticket.attachments.filter(url="").count(), 1)
        self.assertEqual(ticket.attachments.exclude(url="").count(), 1)

    def test_rejects_non_image_bad_link_and_too_many(self):
        self.login(self.user)
        fake = io.BytesIO(b"<script>alert(1)</script>")
        fake.name = "x.png"
        response = self.client.post(
            self.url,
            {
                "subject": "Bad",
                "description": "x",
                "attachments": [fake],
                "image_links": ["javascript:alert(1)"],
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("attachments", response.data)

        many = self.client.post(
            self.url,
            {
                "subject": "Many",
                "description": "x",
                "image_links": [f"https://example.com/{i}.png" for i in range(6)],
            },
            format="json",
        )
        self.assertEqual(many.status_code, 400)
        self.assertFalse(Ticket.objects.filter(subject__in=["Bad", "Many"]).exists())


class TicketDetailTests(HelpdeskApiTestBase):
    def test_owner_sees_detail_with_attachments(self):
        TicketAttachment.objects.create(
            ticket=self.mine, url="https://example.com/a.png"
        )
        self.login(self.user)
        response = self.client.get(self.url(self.mine))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["attachments"][0]["kind"], "link")
        self.assertTrue(response.data["can_reply"])
        self.assertEqual(response.data["requester"]["name"], "sari")

    def test_other_users_are_forbidden(self):
        self.login(self.other)
        self.assertEqual(self.client.get(self.url(self.mine)).status_code, 403)
        self.assertEqual(self.client.delete(self.url(self.mine)).status_code, 403)
        self.assertTrue(Ticket.objects.filter(pk=self.mine.pk).exists())

    def test_admin_can_view_but_reply_only_when_assigned(self):
        self.login(self.admin)
        detail = self.client.get(self.url(self.mine))
        self.assertEqual(detail.status_code, 200)
        self.assertFalse(detail.data["can_reply"])

        self.mine.assigned_to = self.admin
        self.mine.save()
        self.assertTrue(self.client.get(self.url(self.mine)).data["can_reply"])

    def test_owner_can_delete(self):
        self.login(self.user)
        self.assertEqual(self.client.delete(self.url(self.mine)).status_code, 204)
        self.assertFalse(Ticket.objects.filter(pk=self.mine.pk).exists())

    def test_cannot_edit_through_detail(self):
        self.login(self.user)
        response = self.client.patch(
            self.url(self.mine), {"status": "closed"}, format="json"
        )
        self.assertEqual(response.status_code, 405)


class TicketMessageTests(HelpdeskApiTestBase):
    def post(self, ticket, data):
        return self.client.post(self.url(ticket, "messages/"), data, format="json")

    def test_owner_replies_and_lists(self):
        self.login(self.user)
        created = self.post(self.mine, {"message": "  Hello  "})

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data["message"], "Hello")
        self.assertTrue(created.data["is_own"])
        self.assertFalse(created.data["is_admin_response"])

        listing = self.client.get(self.url(self.mine, "messages/"))
        self.assertEqual(len(listing.data), 1)

    def test_assigned_admin_can_reply_and_is_marked(self):
        self.mine.assigned_to = self.admin
        self.mine.save()
        self.login(self.admin)

        response = self.post(self.mine, {"message": "On it"})
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["is_admin_response"])

    def test_unassigned_admin_and_strangers_cannot_reply(self):
        self.login(self.admin)
        self.assertEqual(self.post(self.mine, {"message": "x"}).status_code, 403)
        self.login(self.other)
        self.assertEqual(self.post(self.mine, {"message": "x"}).status_code, 403)
        listing = self.client.get(self.url(self.mine, "messages/"))
        self.assertEqual(listing.status_code, 403)
        self.assertFalse(TicketMessage.objects.exists())

    def test_closed_ticket_rejects_replies(self):
        self.mine.status = Ticket.Status.CLOSED
        self.mine.save()
        self.login(self.user)
        self.assertEqual(self.post(self.mine, {"message": "x"}).status_code, 409)

    def test_resolved_ticket_still_accepts_replies(self):
        self.mine.status = Ticket.Status.RESOLVED
        self.mine.save()
        self.login(self.user)
        self.assertEqual(self.post(self.mine, {"message": "x"}).status_code, 201)

    def test_empty_and_overlong_messages(self):
        self.login(self.user)
        self.assertEqual(self.post(self.mine, {"message": "   "}).status_code, 400)
        self.assertEqual(self.post(self.mine, {"message": "x" * 5001}).status_code, 400)

    def test_reply_to_must_belong_to_same_ticket(self):
        elsewhere = TicketMessage.objects.create(
            ticket=self.theirs, author=self.other, message="private"
        )
        original = TicketMessage.objects.create(
            ticket=self.mine, author=self.user, message="first"
        )
        self.login(self.user)

        bad = self.post(self.mine, {"message": "re", "reply_to": elsewhere.pk})
        self.assertEqual(bad.status_code, 400)
        self.assertIn("reply_to", bad.data)

        good = self.post(self.mine, {"message": "re", "reply_to": original.pk})
        self.assertEqual(good.status_code, 201)
        self.assertEqual(good.data["reply_to"]["excerpt"], "first")


class AttachmentDownloadTests(HelpdeskApiTestBase):
    def setUp(self):
        super().setUp()
        self.login(self.user)
        response = self.client.post(
            f"{BASE}/tickets/",
            {"subject": "Shot", "description": "x", "attachments": [png()]},
            format="multipart",
        )
        self.ticket = Ticket.objects.get(pk=response.data["id"])
        self.attachment = self.ticket.attachments.get()

    def test_owner_downloads_upload_via_detail_url(self):
        detail = self.client.get(self.url(self.ticket))
        url = detail.data["attachments"][0]["url"]
        self.assertTrue(url.startswith("http"))

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), PNG)
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_strangers_and_anonymous_are_refused(self):
        path = f"{BASE}/attachments/{self.attachment.pk}/"
        self.login(self.other)
        self.assertEqual(self.client.get(path).status_code, 404)
        self.client.credentials()
        self.assertEqual(self.client.get(path).status_code, 401)
