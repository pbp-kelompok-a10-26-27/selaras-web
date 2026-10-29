import shutil
import tempfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.helpdesk.models import Ticket, TicketAttachment

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 32

TEMP_MEDIA = tempfile.mkdtemp(prefix="selaras-media-")
TEMP_PRIVATE = tempfile.mkdtemp(prefix="selaras-private-")


def upload(name="a.png", content=PNG, content_type="image/png"):
    return SimpleUploadedFile(name, content, content_type=content_type)


@override_settings(MEDIA_ROOT=TEMP_MEDIA, PRIVATE_MEDIA_ROOT=TEMP_PRIVATE)
class UploadTestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)
        shutil.rmtree(TEMP_PRIVATE, ignore_errors=True)


class AvatarTests(UploadTestCase):
    def setUp(self):
        self.user = User.objects.create_user("sari", "sari@example.com", "x")
        self.client.force_login(self.user)
        self.url = reverse("accounts:avatar_upload")

    def test_upload_stores_a_randomly_named_file(self):
        response = self.client.post(self.url, {"avatar": upload("../evil.html")})
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertRegex(self.user.avatar.name, r"^avatars/[0-9a-f]{32}\.png$")
        self.assertEqual(response.json()["avatar_url"], self.user.avatar_url)

    def test_each_supported_type_is_accepted(self):
        for content, extension in ((JPEG, "jpg"), (WEBP, "webp")):
            response = self.client.post(self.url, {"avatar": upload("x", content)})
            self.assertEqual(response.status_code, 200)
            self.user.refresh_from_db()
            self.assertTrue(self.user.avatar.name.endswith(f".{extension}"))

    def test_extension_and_content_type_are_not_trusted(self):
        fake = upload("photo.png", b"<script>alert(1)</script>", "image/png")
        response = self.client.post(self.url, {"avatar": fake})
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)

    def test_svg_is_rejected(self):
        svg = upload(
            "a.svg", b'<svg xmlns="http://www.w3.org/2000/svg"/>', "image/svg+xml"
        )
        self.assertEqual(self.client.post(self.url, {"avatar": svg}).status_code, 400)

    def test_too_large_is_rejected(self):
        big = upload("big.png", PNG + b"\x00" * (2 * 1024 * 1024))
        response = self.client.post(self.url, {"avatar": big})
        self.assertEqual(response.status_code, 400)
        self.assertIn("terlalu besar", response.json()["error"])

    def test_missing_file_is_rejected(self):
        self.assertEqual(self.client.post(self.url).status_code, 400)

    def test_replacing_deletes_the_old_file(self):
        self.client.post(self.url, {"avatar": upload()})
        self.user.refresh_from_db()
        old = Path(self.user.avatar.path)
        self.assertTrue(old.exists())

        self.client.post(self.url, {"avatar": upload("b.png", JPEG)})
        self.assertFalse(old.exists())

    def test_remove_clears_the_avatar_and_file(self):
        self.client.post(self.url, {"avatar": upload()})
        self.user.refresh_from_db()
        path = Path(self.user.avatar.path)

        response = self.client.post(reverse("accounts:avatar_remove"))
        self.assertEqual(response.json(), {"avatar_url": ""})
        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)
        self.assertFalse(path.exists())

    def test_get_is_not_allowed_and_anonymous_is_redirected(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.client.logout()
        response = self.client.post(self.url, {"avatar": upload()})
        self.assertEqual(response.status_code, 302)

    def test_profile_page_shows_the_picture(self):
        self.client.post(self.url, {"avatar": upload()})
        self.user.refresh_from_db()
        response = self.client.get(reverse("accounts:profile"))
        self.assertContains(response, self.user.avatar_url)
        self.assertContains(response, 'id="avatarModal"')

    def test_navbar_shows_the_picture_instead_of_the_icon(self):
        page = reverse("helpdesk:ticket_list")
        response = self.client.get(page)
        self.assertContains(response, 'data-nav-avatar class="mr-1.5 h-5 w-5')
        self.assertRegex(
            response.content.decode(), r'data-nav-avatar class="[^"]*hidden'
        )

        self.client.post(self.url, {"avatar": upload()})
        self.user.refresh_from_db()
        response = self.client.get(page)
        self.assertContains(
            response, f'src="{self.user.avatar_url}" alt="" data-nav-avatar'
        )
        self.assertNotRegex(
            response.content.decode(), r'data-nav-avatar class="[^"]*hidden'
        )


class TicketAttachmentTests(UploadTestCase):
    def setUp(self):
        self.user = User.objects.create_user("alya", "alya@example.com", "x")
        self.admin = User.objects.create_user(
            "dimas", "dimas@example.com", "x", role="admin"
        )
        self.other = User.objects.create_user("budi", "budi@example.com", "x")
        self.client.force_login(self.user)
        self.url = reverse("helpdesk:ticket_create_api")

    def create(self, **extra):
        data = {
            "subject": "Broken page",
            "description": "See screenshot",
            "priority": "normal",
        }
        data.update(extra)
        return self.client.post(self.url, data)

    def download_url(self):
        attachment = TicketAttachment.objects.get()
        return reverse("helpdesk:attachment_file", args=[attachment.id])

    def test_ticket_without_attachments_still_works(self):
        # The link field posts an empty value when nothing was typed in it
        self.assertEqual(self.create(image_links=[""]).status_code, 201)
        self.assertEqual(TicketAttachment.objects.count(), 0)

    def test_form_without_javascript_keeps_attachments(self):
        response = self.client.post(
            reverse("helpdesk:ticket_create"),
            {
                "subject": "No JS",
                "description": "Plain form post",
                "priority": "normal",
                "attachments": [upload()],
                "image_links": ["https://example.com/a.png"],
            },
        )
        self.assertRedirects(response, reverse("helpdesk:ticket_list"))
        self.assertEqual(Ticket.objects.get().attachments.count(), 2)

    def test_form_without_javascript_rejects_bad_files(self):
        response = self.client.post(
            reverse("helpdesk:ticket_create"),
            {
                "subject": "No JS",
                "description": "Plain form post",
                "priority": "normal",
                "attachments": [upload("x.png", b"nope")],
            },
        )
        self.assertRedirects(response, reverse("helpdesk:ticket_list"))
        self.assertEqual(Ticket.objects.count(), 0)

    def test_files_and_links_are_saved(self):
        response = self.create(
            attachments=[upload("one.png"), upload("two.jpg", JPEG, "image/jpeg")],
            image_links=["https://example.com/shot.png"],
        )
        self.assertEqual(response.status_code, 201)
        ticket = Ticket.objects.get()
        self.assertEqual(ticket.attachments.count(), 3)
        self.assertEqual(ticket.attachments.filter(file="").count(), 1)
        for attachment in ticket.attachments.exclude(file=""):
            self.assertRegex(attachment.file.name, r"^ticket_attachments/[0-9a-f]{32}")

    def test_attachments_are_stored_outside_public_media(self):
        self.create(attachments=[upload()])
        attachment = TicketAttachment.objects.get()
        self.assertTrue(attachment.file.path.startswith(TEMP_PRIVATE))
        self.assertFalse(Path(TEMP_MEDIA, attachment.file.name).exists())

    def test_invalid_files_reject_the_whole_ticket(self):
        response = self.create(attachments=[upload("x.png", b"not an image")])
        self.assertEqual(response.status_code, 400)
        self.assertIn("attachments", response.json()["errors"])
        self.assertEqual(Ticket.objects.count(), 0)

    def test_unsafe_links_are_rejected(self):
        unsafe = (
            "javascript:alert(1)",
            "data:image/png;base64,AAAA",
            "ftp://example.com/y.png",
            "not a url",
        )
        for link in unsafe:
            response = self.create(image_links=[link])
            self.assertEqual(response.status_code, 400, link)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_at_most_five_attachments(self):
        links = [f"https://example.com/{i}.png" for i in range(6)]
        self.assertEqual(self.create(image_links=links).status_code, 400)
        self.assertEqual(self.create(image_links=links[:5]).status_code, 201)

    def test_duplicate_links_are_saved_once(self):
        link = "https://example.com/a.png"
        self.create(image_links=[link, link])
        self.assertEqual(TicketAttachment.objects.count(), 1)

    def test_detail_apis_list_attachments(self):
        self.create(attachments=[upload()], image_links=["https://example.com/a.png"])
        ticket = Ticket.objects.get()

        data = self.client.get(
            reverse("helpdesk:ticket_detail_api", args=[ticket.id])
        ).json()
        urls = {item["kind"]: item["url"] for item in data["ticket"]["attachments"]}
        self.assertEqual(urls["link"], "https://example.com/a.png")
        self.assertRegex(urls["file"], r"^/helpdesk/attachments/\d+/$")

        self.client.force_login(self.admin)
        admin_data = self.client.get(
            f"/dashboard/helpdesk/api/tickets/{ticket.id}/"
        ).json()
        self.assertEqual(len(admin_data["ticket"]["attachments"]), 2)

    def test_only_requester_and_admins_can_download(self):
        self.create(attachments=[upload()])
        url = self.download_url()

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), PNG)
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(url).status_code, 200)

        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)

        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_link_attachment_has_no_download(self):
        self.create(image_links=["https://example.com/a.png"])
        self.assertEqual(self.client.get(self.download_url()).status_code, 404)
