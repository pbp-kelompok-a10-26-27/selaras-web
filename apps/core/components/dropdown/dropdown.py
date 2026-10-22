from django_components import component

@component.register("dropdown")
class Dropdown(component.Component):

    template_file = "dropdown.html"

    def get_template_data(self, args, kwargs: dict, slots, context):

        return {

            "id": kwargs.get("id", ""),
            "name": kwargs.get("name", ""),
            "label": kwargs.get("label", ""),
            "placeholder": kwargs.get("placeholder", "Select an option"),
            "default_value": kwargs.get("default_value", "All"),
            "options": kwargs.get("options", {}), # key: [value, icon]
            "options_group": kwargs.get("options_group", {}), # label: [key: [value, icon], key: [value, icon]], label: [key: [value, icon], key: [value, icon]]
            "dropdown_class": kwargs.get("dropdown_class", ""),
            "option_class": kwargs.get("option_class", ""),
            "option_group_class": kwargs.get("option_group_class", ""),
        }