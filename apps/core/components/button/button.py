from django_components import component


@component.register("button")
class Button(component.Component):
    template_file = "button.html"

    def get_template_data(self, args, kwargs, slots, context):

        return {
            "id": kwargs.get("id", ""),
            "text": kwargs.get("text", "Button"),
            "variant": kwargs.get("variant", "primary"),
            "size": kwargs.get("size", "md"),

            "href": kwargs.get("href", ""),
            "type": kwargs.get("type", "button"),

            "disabled": kwargs.get("disabled", False),
            "selected": kwargs.get("selected", False),
            "loading": kwargs.get("loading", False),
            "full_width": kwargs.get("full_width", False),

            "icon_left": kwargs.get("icon_left", ""),
            "icon_right": kwargs.get("icon_right", ""),

            "aria_label": kwargs.get("aria_label", ""),
            "class_": kwargs.get("class_", ""),

            "attrs": kwargs.get("attrs", ""),
        }