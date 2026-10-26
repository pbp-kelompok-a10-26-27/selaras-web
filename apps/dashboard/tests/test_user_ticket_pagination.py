from django.test import TestCase

from apps.accounts.models import User
from apps.helpdesk.models import Ticket

LIST_API = "/helpdesk/api/tickets/"


class UserTicketPaginationTests(TestCase):
    """The user helpdesk list (/helpdesk/tickets/) pages its tickets 10 at a time."""

    @classmethod
    def setUpTestData(cls):
        cls.alya = User.objects.create_user(
            username="alya", email="alya@example.com", password="x"
        )
        cls.other = User.objects.create_user(
            username="budi", email="budi@example.com", password="x"
        )
        for i in range(23):
            Ticket.objects.create(
                requester=cls.alya,
                subject=f"Ticket {i:02}",
                description="",
                priority="high" if i < 4 else "normal",
            )
        Ticket.objects.create(
            requester=cls.other, subject="Someone else's", description=""
        )

    def setUp(self):
        self.client.force_login(self.alya)

    def api(self, query=""):
        return self.client.get(LIST_API + query).json()

    def test_ten_per_page(self):
        data = self.api()
        self.assertEqual(len(data["tickets"]), 10)
        self.assertEqual(
            data["pagination"],
            {
                "page": 1,
                "total_pages": 3,
                "count": 23,
                "per_page": 10,
                "start": 1,
                "end": 10,
            },
        )
        self.assertEqual(data["total_count"], 23)  # only this user's tickets

        last = self.api("?page=3")
        self.assertEqual(len(last["tickets"]), 3)
        self.assertEqual(
            (last["pagination"]["start"], last["pagination"]["end"]), (21, 23)
        )

    def test_pages_cover_every_ticket_once(self):
        ids = set()
        for page in (1, 2, 3):
            ids |= {t["id"] for t in self.api(f"?page={page}")["tickets"]}
        self.assertEqual(len(ids), 23)

    def test_out_of_range_or_bad_pages_snap(self):
        self.assertEqual(self.api("?page=50")["pagination"]["page"], 3)
        self.assertEqual(self.api("?page=zero")["pagination"]["page"], 1)
        self.assertEqual(self.api("?page=-2")["pagination"]["page"], 1)

    def test_filters_and_sort_apply_before_paging(self):
        high = self.api("?priority=high")
        self.assertEqual(
            (high["pagination"]["count"], high["pagination"]["total_pages"]), (4, 1)
        )
        self.assertTrue(all(t["priority"] == "high" for t in high["tickets"]))

        # Sorting is across all pages: the 4 high-priority tickets lead page 1
        by_priority = self.api("?sort=-priority")
        self.assertEqual(
            [t["priority"] for t in by_priority["tickets"][:4]], ["high"] * 4
        )

        searched = self.api("?search=Ticket 2&page=1")
        self.assertEqual(searched["pagination"]["count"], 3)  # Ticket 20, 21, 22

    def test_empty_list(self):
        self.client.force_login(
            User.objects.create_user(
                username="new", email="new@example.com", password="x"
            )
        )
        data = self.api()
        self.assertEqual(data["tickets"], [])
        self.assertEqual(
            (
                data["pagination"]["page"],
                data["pagination"]["total_pages"],
                data["pagination"]["count"],
            ),
            (1, 1, 0),
        )
