from django_components import component


@component.register("user_name")
class UserName(component.Component):
    """A person's display name followed by the badge they chose to feature."""

    template_file = "user_name.html"

    def get_template_data(self, args, kwargs, slots, context):
        user = kwargs.get("user")
        return {
            "person": user,
            "name": getattr(user, "display_name", "") if user else "",
            "badge": getattr(user, "featured_badge", None) if user else None,
            "size": kwargs.get("size", "md"),  # sm or md
            "badge_name": kwargs.get("badge_name", True),
            "class_": kwargs.get("class_", ""),
            "name_class": kwargs.get("name_class", "font-semibold text-secondary-900"),
        }
