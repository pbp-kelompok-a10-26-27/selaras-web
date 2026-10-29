from django_components import component


@component.register("chips")
class Chips(component.Component):
    template_file = "chips.html"

    def get_template_data(self, args, kwargs, slots, context):

        return {
            "text": kwargs.get("text", "Chips"),
            "variant": kwargs.get("variant", "primary"),
            "size": kwargs.get("size", "md"),
            "type": kwargs.get("type", "button"),
            "disabled": kwargs.get("disabled", False),
            "icon_left": kwargs.get("icon_left", ""),
            "icon_right": kwargs.get("icon_right", ""),
            "aria-label": kwargs.get("aria_label", ""),
            "selected": kwargs.get("selected", False),
            "class_": kwargs.get("class_", ""),
            "full_width": kwargs.get("full_width", False),
        }
