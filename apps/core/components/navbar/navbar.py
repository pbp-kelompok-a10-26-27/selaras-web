from django.middleware.csrf import get_token
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
                    {"label": "Articles", "href": "/articles/"},
                    {"label": "Challenges", "href": "/challenges/"},
                    {"label": "Feed", "href": "/feed/"},
                    {"label": "Donations", "href": "/donations/"},
                    {"label": "Help Desk", "href": "/helpdesk/tickets/"},
                ],
            )
        ]
        profile_url = kwargs.get("profile_url", "/accounts/profile/")
        user = getattr(request, "user", None)

        return {
            # Logout is a POST form: Django's LogoutView rejects GET, so a link to
            # it fails. (Not named "csrf_token": that name is reserved by Django's
            # context processor.)
            "logout_csrf_token": get_token(request) if request else "",
            "logo_url": kwargs.get("logo_url", "/"),
            "logo_text": kwargs.get("logo_text", "SELARAS"),
            "links": links,
            "authenticated": kwargs.get("authenticated", False),
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
