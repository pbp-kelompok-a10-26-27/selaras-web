from django_components import component


@component.register("navbar")
class Navbar(component.Component):
    template_file = "navbar.html"

    def get_template_data(self, args, kwargs, slots, context):
        return {
            "logo_url": kwargs.get("logo_url", "/"),
            "logo_text": kwargs.get("logo_text", "SELARAS"),
            "links": kwargs.get(
                "links",
                [
                    {"label": "Articles", "href": "/articles/"},
                    {"label": "Challenges", "href": "/challenges/"},
                    {"label": "Feed", "href": "/feed/"},
                    {"label": "Donations", "href": "/donations/"},
                    {"label": "Help Desk", "href": "/helpdesk/"},
                ],
            ),
            "login_url": kwargs.get("login_url", "/login/"),
            "register_url": kwargs.get("register_url", "/register/"),
            "preview": kwargs.get("preview", False),
            "class_": kwargs.get("class_", ""),
        }
