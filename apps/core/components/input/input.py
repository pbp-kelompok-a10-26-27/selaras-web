from django_components import component

@component.register("input")
class Input(component.Component):

    template_name = "input.html"

    def get_template_data(self, args, kwargs: dict, slots, context):
        return {
            "id": kwargs.get("id", ""),
            "name": kwargs.get("name", ""),
            "label": kwargs.get("label", ""),
            "placeholder": kwargs.get("placeholder", ""),
            "value": kwargs.get("value", ""),
            "type": kwargs.get("type", "text"),  # text, password, email, number, etc.
            "class_": kwargs.get("class_", ""),
            "autocomplete": kwargs.get("autocomplete", "off"),
            "required": kwargs.get("required", False),
            "icon": kwargs.get("icon", None),  # Optional icon class
            "errors": kwargs.get("errors", []),  # List of error messages
            "attrs": kwargs.get("attrs", ""),  # Additional HTML attributes
            "disabled": kwargs.get("disabled", False),  # Disabled state
        }