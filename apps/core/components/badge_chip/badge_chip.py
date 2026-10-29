from django_components import component


@component.register("badge_chip")
class BadgeChip(component.Component):
    """A challenge badge as a small pill: its icon, tone and (optionally) name."""

    template_file = "badge_chip.html"

    def get_template_data(self, args, kwargs, slots, context):
        badge = kwargs.get("badge")
        return {
            "badge": badge,
            "size": kwargs.get("size", "sm"),  # xs (beside names), sm, md
            "show_name": kwargs.get("show_name", True),
            "class_": kwargs.get("class_", ""),
        }
