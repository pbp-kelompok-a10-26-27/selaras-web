from django_components import component

@component.register("modal")
class Modal(component.Component):
    template_name = "modal.html"
    

    def get_template_data(self, args, kwargs: dict, slots, context):
        return {
            "id": kwargs.get("id", "modal-default"),
            "title": kwargs.get("title", ""),
            "size": kwargs.get("size", "md"),  # sm, md, lg, xl, full
            "class_": kwargs.get("class_", ""),
            "has_footer": "footer" in slots,
        }