from django_components import component


@component.register("textarea")
class Textarea(component.Component):
    template_file = "textarea.html"

    def get_template_data(self, args, kwargs, slots, context):
        value = kwargs.get("value") or ""
        errors = kwargs.get("errors") or []

        return {
            "id": kwargs.get("id", ""),
            "name": kwargs.get("name", ""),
            "label": kwargs.get("label", ""),
            "value": value,
            "rows": kwargs.get("rows", 4),
            "maxlength": kwargs.get("maxlength", ""),
            "length": len(value),
            "required": kwargs.get("required", False),
            "disabled": kwargs.get("disabled", False),
            "errors": [str(error) for error in errors],
            "attrs": kwargs.get("attrs", ""),
            "class_": kwargs.get("class_", ""),
        }
