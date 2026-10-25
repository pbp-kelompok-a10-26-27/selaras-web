from django_components import component


@component.register("toast")
class Toast(component.Component):
    template_name = "toast.html"

    def get_template_data(self, args, kwargs: dict, slots, context):
        return {
            "id": kwargs.get("id", "toast-default"),
            "type": kwargs.get("type", "success"),  # success, error, warning, info
            "title": kwargs.get("title", ""),
            "message": kwargs.get("message", ""),
            "duration": kwargs.get("duration", 4000),  # Auto-dismiss in ms
            "class_": kwargs.get("class_", ""),
        }
