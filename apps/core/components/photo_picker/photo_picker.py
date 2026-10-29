from django_components import component


@component.register("photo_picker")
class PhotoPicker(component.Component):
    """Pick several photos for one <input type="file" multiple>: thumbnails, remove,
    reorder, drag and drop, a count / total size meter and in-browser downscaling so
    phone photos fit the upload limit. The server validates everything again."""

    template_file = "photo_picker.html"

    def get_template_data(self, args, kwargs, slots, context):
        return {
            "id": kwargs.get("id", "photos"),
            "name": kwargs.get("name", "images"),
            "title": kwargs.get("title", "Tambah foto"),
            "hint": kwargs.get("hint", ""),
            "accept": kwargs.get("accept", "image/jpeg,image/png,image/webp"),
            "max_files": kwargs.get("max_files", 10),
            "max_mb": kwargs.get("max_mb", 10),
            "errors": kwargs.get("errors", []),
            "input_class": kwargs.get("input_class", ""),
            "class_": kwargs.get("class_", ""),
        }
