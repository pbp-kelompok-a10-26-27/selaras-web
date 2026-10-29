from django.middleware.csrf import get_token
from django.urls import reverse
from django_components import component


@component.register("navbar")
class Navbar(component.Component):
    template_file = "navbar.html"

    def get_template_data(self, args, kwargs, slots, context):
        request = context.get("request")
        current_path = request.path if request else ""

        def is_active(href):
            # Prefix match so detail pages (e.g. /articles/42/) keep their section
            # highlighted.
            return bool(current_path) and href != "/" and current_path.startswith(href)

        links = [
            {**link, "active": is_active(link["href"])}
            for link in kwargs.get(
                "links",
                [
                    {"label": "Artikel", "href": "/articles/browse/"},
                    {"label": "Challenge", "href": "/challenges/"},
                    {"label": "Feed", "href": "/feed/"},
                    {"label": "Donasi", "href": "/donations/"},
                    {"label": "Bantuan", "href": "/helpdesk/tickets/"},
                ],
            )
        ]
        profile_url = kwargs.get("profile_url", "/accounts/profile/")
        user = getattr(request, "user", None)
        authenticated = kwargs.get("authenticated", False)
        unread = 0
        if authenticated and not kwargs.get("preview", False):
            from apps.notifications.services import unread_count

            unread = unread_count(user)

        return {
            # Logout is a POST form: Django's LogoutView rejects GET, so a link to
            # it fails. (Not named "csrf_token": that name is reserved by Django's
            # context processor.)
            "logout_csrf_token": get_token(request) if request else "",
            "logo_url": kwargs.get("logo_url", "/"),
            "logo_text": kwargs.get("logo_text", "SELARAS"),
            "links": links,
            "authenticated": authenticated,
            # Notification bell
            "unread_count": unread,
            "notifications_url": reverse("notifications:list"),
            "notifications_feed_url": reverse("notifications:feed"),
            "notifications_read_all_url": reverse("notifications:read_all"),
            "notifications_active": is_active(reverse("notifications:list")),
            "login_url": kwargs.get("login_url", "/accounts/login/"),
            "register_url": kwargs.get("register_url", "/accounts/register/"),
            "logout_url": kwargs.get("logout_url", "/accounts/logout/"),
            "profile_url": profile_url,
            "profile_active": is_active(profile_url),
            # Shown in place of the profile icon once the user has uploaded one
            "avatar_url": getattr(user, "avatar_url", ""),
            "preview": kwargs.get("preview", False),
            "class_": kwargs.get("class_", ""),
        }
