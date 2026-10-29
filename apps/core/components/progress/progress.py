from django_components import component


def _percent(raw):
    try:
        return min(max(float(raw), 0.0), 100.0)
    except (TypeError, ValueError):
        return 0.0


@component.register("progress")
class Progress(component.Component):
    template_file = "progress.html"

    def get_template_data(self, args, kwargs, slots, context):
        value = _percent(kwargs.get("value", 0))
        preview = min(_percent(kwargs.get("preview", 0)), 100.0 - value)

        return {
            "id": kwargs.get("id", ""),
            "label": kwargs.get("label", "Progres"),
            "size": kwargs.get("size", "md"),
            "with_preview": kwargs.get("with_preview", False),
            "value_int": round(value),
            # Formatted here so a localized comma never ends up in the style
            "width": f"{value:.2f}",
            "preview_width": f"{preview:.2f}",
            "class_": kwargs.get("class_", ""),
        }
