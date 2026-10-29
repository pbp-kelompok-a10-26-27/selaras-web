from django_components import component


@component.register("badge")
class Badge(component.Component):
    template_file = "badge.html"

    def get_template_data(self, args, kwargs, slots, context):
        return {
            "text": kwargs.get("text", ""),
            "variant": kwargs.get("variant", "primary"),
            "size": kwargs.get("size", "md"),
            "icon": kwargs.get("icon", ""),
            "class_": kwargs.get("class_", ""),
            "attrs": kwargs.get("attrs", ""),
        }
