from django_components import component

@component.register("skeleton")
class Skeleton(component.Component):
    template_name = "skeleton.html"

    def get_template_data(self, args, kwargs: dict, slots, context):
        return {
            "variant": kwargs.get("variant", "text"),  # text, avatar, card, form, rect, circle
            "width": kwargs.get("width", "w-full"),
            "height": kwargs.get("height", "h-4"),
            "rounded": kwargs.get("rounded", "rounded-xl"),
            "lines": int(kwargs.get("lines", 3)),  # Number of lines for text variant
            "class_": kwargs.get("class_", ""),
        }