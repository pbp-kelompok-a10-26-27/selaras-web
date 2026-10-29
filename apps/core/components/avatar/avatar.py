from django_components import component

TONES = ("primary", "secondary", "tertiary")


@component.register("avatar")
class Avatar(component.Component):
    template_file = "avatar.html"

    def get_template_data(self, args, kwargs, slots, context):
        name = (kwargs.get("name") or "").strip()
        words = name.split()
        if len(words) > 1:
            initials = (words[0][0] + words[-1][0]).upper()
        else:
            initials = name[:2].upper()

        # The same person always gets the same colour
        tone = TONES[sum(ord(char) for char in name) % len(TONES)]

        return {
            "src": kwargs.get("src", ""),
            "name": name,
            "initials": initials or "?",
            "tone": kwargs.get("tone", tone),
            "size": kwargs.get("size", "md"),
            "class_": kwargs.get("class_", ""),
        }
