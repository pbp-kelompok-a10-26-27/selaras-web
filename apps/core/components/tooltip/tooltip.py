import uuid

from django_components import component


@component.register("tooltip")
class Tooltip(component.Component):
    
    template_name = "tooltip.html"

    def get_template_data(self, args, kwargs: dict, slots, context):
        return {
            "id": kwargs.get("id") or f"tooltip-{uuid.uuid4().hex[:8]}",
            "text": kwargs.get("text", ""),
            "position": kwargs.get("position", "top"),  # top, bottom, left, right
            "class_": kwargs.get("class_", ""),
        }