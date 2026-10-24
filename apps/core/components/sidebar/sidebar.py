from django.middleware.csrf import get_token
from django_components import component


@component.register("sidebar")
class Sidebar(component.Component):
    template_file = "sidebar.html"

    def get_template_data(self, args, kwargs, slots, context):
        request = context.get("request")
        path = request.path if request else ""
        user = getattr(request, "user", None)

        # sections: [{"label": "Management", "items": [{key, label, icon, href, badge, badge_label, exact}]}]
        # An item without an href renders as disabled "Soon".
        sections = []
        for section in kwargs.get("sections", []):
            items = []
            for item in section.get("items", []):
                href = item.get("href")
                if "active" in item:
                    active = item["active"]
                elif not href:
                    active = False
                elif item.get("exact"):
                    active = path == href
                else:
                    active = path.startswith(href)
                items.append({**item, "active": active})
            sections.append({**section, "items": items})

        name = ""
        if user and user.is_authenticated:
            name = user.get_full_name() or user.username
        initials = "".join(part[0] for part in name.split()[:2]).upper()

        return {
            "id": kwargs.get("id", "dashboard-sidebar"),
            "brand": kwargs.get("brand", "SELARAS"),
            "brand_caption": kwargs.get("brand_caption", "Admin"),
            "home_url": kwargs.get("home_url", "/dashboard/"),
            "site_url": kwargs.get("site_url", "/"),
            "logout_url": kwargs.get("logout_url", "/accounts/logout/"),
            "sections": sections,

            "user_name": name,
            "user_initials": initials,
            "user_role": user.get_role_display() if user and hasattr(user, "get_role_display") else "",

            # Logout is a POST form (Django 5's LogoutView rejects GET)
            "logout_csrf_token": get_token(request) if request else "",
            "class_": kwargs.get("class_", ""),
        }
