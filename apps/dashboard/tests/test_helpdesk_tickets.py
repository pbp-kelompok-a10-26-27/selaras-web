from django.test import TestCase

from apps.accounts.models import User
from apps.helpdesk.models import Ticket, TicketMessage

LIST_API = "/dashboard/helpdesk/api/tickets/"
STATS_API = "/dashboard/helpdesk/api/tickets/stats/"


class AdminTicketManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.me = User.objects.create_user(username="dimas", email="dimas@example.com", password="x", role="admin", first_name="Dimas", last_name="Pratama")
        cls.other_admin = User.objects.create_user(username="rina", email="rina@example.com", password="x", role="admin", first_name="Rina")
        cls.alya = User.objects.create_user(username="alya", email="alya.safitri@example.com", password="x", first_name="Alya", last_name="Safitri")

        cls.mine_high = Ticket.objects.create(requester=cls.alya, assigned_to=cls.me, subject="Certificate mismatch", description="150 kg", priority="high")
        cls.mine_closed = Ticket.objects.create(requester=cls.alya, assigned_to=cls.me, subject="Old issue", description="done", status="closed")
        cls.theirs = Ticket.objects.create(requester=cls.alya, assigned_to=cls.other_admin, subject="Login loop", description="cannot log in", status="in_progress")
        cls.unassigned = Ticket.objects.create(requester=cls.alya, subject="Donation receipt missing", description="no email", priority="low")
        cls.resolved = Ticket.objects.create(requester=cls.alya, subject="Typo on page", description="fixed", status="resolved")
        TicketMessage.objects.create(ticket=cls.mine_high, author=cls.alya, message="hi")
        for i in range(25):
            Ticket.objects.create(requester=cls.alya, subject=f"Bulk {i:02}", description="filler")

    def setUp(self):
        self.client.force_login(self.me)

    def api(self, query=""):
        return self.client.get(LIST_API + query).json()

    # ---------------------------------------------------------------- lists

    def test_assigned_and_other_tickets_are_separate(self):
        data = self.api()
        self.assertEqual(sorted(t["title"] for t in data["assigned"]), ["Certificate mismatch", "Old issue"])
        self.assertTrue(all(not t["is_assigned_to_me"] for t in data["others"]))

    def test_other_tickets_are_paged(self):
        first = self.api()
        self.assertEqual((len(first["others"]), first["others_total"], first["has_more"]), (20, 28, True))

        second = self.api("?page=2")
        self.assertEqual(len(second["others"]), 8)
        self.assertIsNone(second["assigned"])  # only sent with page 1
        self.assertFalse(second["has_more"])

        ids = {t["id"] for t in first["others"]} | {t["id"] for t in second["others"]}
        self.assertEqual(len(ids), 28)  # no overlap, nothing skipped

    def test_row_fields(self):
        row = next(t for t in self.api()["assigned"] if t["title"] == "Certificate mismatch")
        self.assertEqual(row["messages_count"], 1)
        self.assertTrue(row["can_reply"])
        self.assertFalse(row["can_assign_to_me"])
        self.assertEqual(row["requester_email"], "alya.safitri@example.com")

        closed = next(t for t in self.api()["assigned"] if t["title"] == "Old issue")
        self.assertFalse(closed["can_reply"])

    # -------------------------------------------------------------- filters

    def test_assignment_filter(self):
        unassigned = self.api("?assignment=unassigned")
        self.assertEqual(unassigned["assigned"], [])
        # Every status counts here (27); the "Unassigned" stat only counts active ones (26)
        self.assertEqual(unassigned["others_total"], 27)
        self.assertTrue(all(t["assignee"] is None for t in unassigned["others"]))

        self.assertEqual([t["title"] for t in self.api("?assignment=others")["others"]], ["Login loop"])

        mine = self.api("?assignment=me")
        self.assertEqual((len(mine["assigned"]), mine["others"]), (2, []))

    def test_status_and_priority_filters(self):
        self.assertEqual([t["title"] for t in self.api("?status=in_progress")["others"]], ["Login loop"])
        self.assertEqual([t["title"] for t in self.api("?priority=high")["assigned"]], ["Certificate mismatch"])

    def test_search_covers_requester_and_ticket_id(self):
        self.assertEqual(self.api("?search=safitri")["others_total"], 28)
        self.assertEqual(self.api("?search=alya.safitri@")["others_total"], 28)
        short_id = str(self.theirs.id)[:8].upper()
        self.assertEqual([t["title"] for t in self.api(f"?search=%23{short_id}")["others"]], ["Login loop"])

    def test_invalid_query_values_are_ignored(self):
        self.assertEqual(self.api("?assignment=hack&status=nope&sort=password")["others_total"], 28)

    def test_priority_sort_puts_high_first(self):
        self.assertEqual(self.api("?sort=-priority")["assigned"][0]["title"], "Certificate mismatch")

    # ---------------------------------------------------------------- stats

    def test_stats(self):
        stats = self.client.get(STATS_API).json()
        self.assertEqual(stats["kpis"], {"total": 30, "active": 28, "assigned_to_me": 1, "unassigned": 26, "high_active": 1, "resolved_week": 1})
        self.assertEqual({s["key"]: s["value"] for s in stats["status"]}, {"open": 27, "in_progress": 1, "resolved": 1, "closed": 1})
        self.assertEqual([p["key"] for p in stats["priority"]], ["high", "normal", "low"])
        self.assertEqual(sum(p["value"] for p in stats["priority"]), 28)

    # -------------------------------------------------------------- actions

    def test_assign_unassigned_ticket_to_me(self):
        response = self.client.post(f"/dashboard/helpdesk/tickets/{self.unassigned.id}/assign/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ticket"]["is_assigned_to_me"])
        self.unassigned.refresh_from_db()
        self.assertEqual(self.unassigned.assigned_to, self.me)

    def test_cannot_take_another_admins_ticket(self):
        response = self.client.post(f"/dashboard/helpdesk/tickets/{self.theirs.id}/assign/")
        self.assertEqual(response.status_code, 409)
        self.assertIn("Rina", response.json()["error"])

    def test_delete_any_ticket_with_its_messages(self):
        response = self.client.post(f"/dashboard/helpdesk/tickets/{self.mine_high.id}/delete/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Ticket.objects.filter(id=self.mine_high.id).exists())
        self.assertFalse(TicketMessage.objects.filter(ticket_id=self.mine_high.id).exists())

        self.assertEqual(self.client.post(f"/dashboard/helpdesk/tickets/{self.theirs.id}/delete/").status_code, 200)
        self.assertEqual(self.client.post(f"/dashboard/helpdesk/tickets/{self.theirs.id}/delete/").status_code, 404)

    def test_actions_are_post_only(self):
        self.assertEqual(self.client.get(f"/dashboard/helpdesk/tickets/{self.unassigned.id}/assign/").status_code, 405)
        self.assertEqual(self.client.get(f"/dashboard/helpdesk/tickets/{self.resolved.id}/delete/").status_code, 405)

    # --------------------------------------------------------------- access

    def test_page_renders_with_filters_from_url(self):
        response = self.client.get("/dashboard/helpdesk/tickets/?status=open&assignment=unassigned")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="open"')
        self.assertContains(response, 'value="unassigned"')
        self.assertContains(response, 'aria-current="page"')

    def test_regular_users_are_blocked(self):
        self.client.force_login(self.alya)
        for url in ["/dashboard/helpdesk/tickets/", LIST_API, STATS_API]:
            self.assertEqual(self.client.get(url).status_code, 403, url)
        self.assertEqual(self.client.post(f"/dashboard/helpdesk/tickets/{self.resolved.id}/delete/").status_code, 403)
        self.assertTrue(Ticket.objects.filter(id=self.resolved.id).exists())
