from django.test import TestCase

from apps.accounts.models import User
from apps.helpdesk.models import Ticket, TicketMessage


class AdminTicketDetailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.me = User.objects.create_user(
            username="dimas",
            email="dimas@example.com",
            password="x",
            role="admin",
            first_name="Dimas",
        )
        cls.rina = User.objects.create_user(
            username="rina",
            email="rina@example.com",
            password="x",
            role="admin",
            first_name="Rina",
        )
        cls.alya = User.objects.create_user(
            username="alya",
            email="alya@example.com",
            password="x",
            first_name="Alya",
            last_name="Safitri",
        )

        cls.mine = Ticket.objects.create(
            requester=cls.alya,
            assigned_to=cls.me,
            subject="Certificate shows 150 kg",
            description="should be 300",
        )
        cls.theirs = Ticket.objects.create(
            requester=cls.alya,
            assigned_to=cls.rina,
            subject="Login loop",
            description="",
        )
        cls.unassigned = Ticket.objects.create(
            requester=cls.alya, subject="Receipt missing", description=""
        )
        cls.first_message = TicketMessage.objects.create(
            ticket=cls.mine, author=cls.alya, message="Attaching my planting serial ID."
        )

    def setUp(self):
        self.client.force_login(self.me)

    def url(self, ticket, suffix=""):
        return f"/dashboard/helpdesk/tickets/{ticket.id}/{suffix}"

    def api(self, ticket):
        return self.client.get(f"/dashboard/helpdesk/api/tickets/{ticket.id}/").json()

    def reply(self, ticket, message, reply_to=None, client=None):
        data = {"message": message}
        if reply_to is not None:
            data["reply_to"] = reply_to
        return (client or self.client).post(
            self.url(ticket, "messages/create/"), data, HTTP_ACCEPT="application/json"
        )

    # ---------------------------------------------------------------- page + API

    def test_any_admin_can_view_any_ticket(self):
        for ticket in [self.mine, self.theirs, self.unassigned]:
            self.assertEqual(self.client.get(self.url(ticket)).status_code, 200)

    def test_detail_api_permissions(self):
        mine = self.api(self.mine)["ticket"]
        self.assertTrue(mine["can_reply"] and mine["can_update_status"])

        theirs = self.api(self.theirs)["ticket"]
        self.assertFalse(
            theirs["can_reply"]
            or theirs["can_update_status"]
            or theirs["can_assign_to_me"]
        )

        unassigned = self.api(self.unassigned)["ticket"]
        self.assertFalse(unassigned["can_reply"])
        self.assertTrue(unassigned["can_assign_to_me"])

    def test_list_rows_link_to_admin_detail(self):
        rows = self.client.get("/dashboard/helpdesk/api/tickets/").json()["assigned"]
        self.assertEqual(rows[0]["detail_url"], self.url(self.mine))

    # ------------------------------------------------------------------- status

    def test_owner_changes_status_and_closed_at(self):
        response = self.client.post(
            self.url(self.mine, "update/"), {"status": "closed"}
        )
        self.assertEqual(response.status_code, 200)
        ticket = response.json()["ticket"]
        self.assertEqual(ticket["status"], "closed")
        self.assertIsNotNone(ticket["closed_at"])
        self.assertFalse(ticket["can_reply"])

        reopened = self.client.post(
            self.url(self.mine, "update/"), {"status": "in_progress"}
        ).json()["ticket"]
        self.assertIsNone(reopened["closed_at"])
        self.assertTrue(reopened["can_reply"])

    def test_only_owner_changes_status(self):
        self.assertEqual(
            self.client.post(
                self.url(self.theirs, "update/"), {"status": "resolved"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                self.url(self.unassigned, "update/"), {"status": "resolved"}
            ).status_code,
            403,
        )
        self.theirs.refresh_from_db()
        self.assertEqual(self.theirs.status, "open")

    def test_invalid_status_rejected(self):
        for status in ["open", "deleted", ""]:
            self.assertEqual(
                self.client.post(
                    self.url(self.mine, "update/"), {"status": status}
                ).status_code,
                400,
                status,
            )
        self.assertEqual(
            self.client.get(self.url(self.mine, "update/")).status_code, 405
        )

    # ------------------------------------------------------------------ replies

    def test_owner_replies_with_quote(self):
        response = self.reply(
            self.mine, "Thanks, checking the ledger.", reply_to=self.first_message.id
        )
        self.assertEqual(response.status_code, 201)
        message = response.json()["message"]
        self.assertTrue(message["is_admin_response"])
        self.assertEqual(message["reply_to"]["id"], self.first_message.id)
        self.assertEqual(message["reply_to"]["author_name"], "Alya Safitri")

        # The quote comes back with the conversation too
        replies = [m for m in self.api(self.mine)["messages"] if m["reply_to"]]
        self.assertEqual(
            replies[0]["reply_to"]["excerpt"], "Attaching my planting serial ID."
        )

    def test_cannot_quote_a_message_from_another_ticket(self):
        other = TicketMessage.objects.create(
            ticket=self.theirs, author=self.alya, message="secret"
        )
        self.assertEqual(
            self.reply(self.mine, "hi", reply_to=other.id).status_code, 400
        )
        self.assertEqual(self.reply(self.mine, "hi", reply_to="abc").status_code, 400)

    def test_non_owner_admins_cannot_reply(self):
        self.assertEqual(self.reply(self.theirs, "hello").status_code, 403)
        self.assertEqual(self.reply(self.unassigned, "hello").status_code, 403)

    def test_no_replies_on_closed_tickets(self):
        self.client.post(self.url(self.mine, "update/"), {"status": "closed"})
        self.assertEqual(self.reply(self.mine, "hello").status_code, 409)

    def test_reply_without_js_redirects_back(self):
        response = self.client.post(
            self.url(self.mine, "messages/create/"), {"message": "plain form"}
        )
        self.assertRedirects(
            response, self.url(self.mine), fetch_redirect_response=False
        )

    # --------------------------------------------- user side (shared reply rules)

    def test_requester_replies_with_quote_on_user_api(self):
        self.client.force_login(self.alya)
        response = self.client.post(
            f"/helpdesk/api/tickets/{self.mine.id}/messages/",
            {"message": "Here it is", "reply_to": self.first_message.id},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.json()["message"]["reply_to"]["id"], self.first_message.id
        )

    def test_user_api_no_longer_lets_any_admin_reply(self):
        # Before TODO 3 any admin could post here; now only the assigned one can
        self.assertEqual(
            self.client.post(
                f"/helpdesk/api/tickets/{self.theirs.id}/messages/", {"message": "x"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                f"/helpdesk/api/tickets/{self.mine.id}/messages/", {"message": "ok"}
            ).status_code,
            201,
        )

    def test_user_detail_api_can_reply_flag(self):
        self.client.force_login(self.alya)
        self.assertTrue(
            self.client.get(f"/helpdesk/api/tickets/{self.mine.id}/").json()["ticket"][
                "can_reply"
            ]
        )
        self.client.force_login(self.rina)
        self.assertFalse(
            self.client.get(f"/helpdesk/api/tickets/{self.mine.id}/").json()["ticket"][
                "can_reply"
            ]
        )

    def test_deleted_original_keeps_the_reply(self):
        reply = TicketMessage.objects.create(
            ticket=self.mine,
            author=self.me,
            message="answer",
            reply_to=self.first_message,
            is_admin_response=True,
        )
        self.first_message.delete()
        reply.refresh_from_db()
        self.assertIsNone(reply.reply_to)

    def test_regular_users_blocked_from_admin_detail(self):
        self.client.force_login(self.alya)
        self.assertEqual(self.client.get(self.url(self.mine)).status_code, 403)
        self.assertEqual(
            self.client.post(
                self.url(self.mine, "update/"), {"status": "closed"}
            ).status_code,
            403,
        )
