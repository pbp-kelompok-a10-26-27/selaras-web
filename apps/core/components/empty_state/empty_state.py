from django_components import component


@component.register("empty_state")
class EmptyState(component.Component):
    template_file = "empty_state.html"

    def get_template_data(self, args, kwargs, slots, context):
        return {
            "icon": kwargs.get("icon", "search-x"),
            "title": kwargs.get("title", ""),
            "description": kwargs.get("description", ""),
            "class_": kwargs.get("class_", ""),
            "has_actions": "actions" in slots,
        }
