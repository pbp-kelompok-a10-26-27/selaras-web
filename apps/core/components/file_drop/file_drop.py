from django_components import component


@component.register("file_drop")
class FileDrop(component.Component):
    template_file = "file_drop.html"

    def get_template_data(self, args, kwargs, slots, context):
        errors = kwargs.get("errors") or []

        return {
            "id": kwargs.get("id", ""),
            "name": kwargs.get("name", ""),
            "title": kwargs.get("title", "Seret file ke sini atau klik untuk memilih"),
            "hint": kwargs.get("hint", ""),
            "icon": kwargs.get("icon", "image-up"),
            "accept": kwargs.get("accept", ""),
            "max_mb": kwargs.get("max_mb", ""),
            "required": kwargs.get("required", False),
            "errors": [str(error) for error in errors],
            "input_class": kwargs.get("input_class", ""),
            "class_": kwargs.get("class_", ""),
        }
