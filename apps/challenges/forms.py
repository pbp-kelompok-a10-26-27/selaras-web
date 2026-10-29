from django import forms

from .models import Challenge

INPUT_CLASSES = (
    "w-full rounded-xl border border-neutral-400 bg-neutral-50 px-4 py-3 "
    "font-sans text-sm text-secondary-900 placeholder:text-neutral-500 "
    "focus:border-primary-500 focus:ring-2 focus:ring-primary-400/30 "
    "outline-none transition-all"
)

TEXTAREA_CLASSES = (
    "w-full rounded-xl border border-neutral-400 bg-neutral-50 p-4 "
    "font-sans text-sm text-secondary-900 placeholder:text-neutral-500 "
    "focus:border-primary-500 focus:ring-2 focus:ring-primary-400/30 "
    "outline-none transition-all resize-none leading-relaxed"
)

DATE_CLASSES = (
    "w-full rounded-xl border border-neutral-400 bg-neutral-50 px-4 py-3 "
    "font-sans text-sm text-secondary-900 focus:border-primary-500 "
    "focus:ring-2 focus:ring-primary-400/30 outline-none transition-all"
)

CHECKBOX_CLASSES = (
    "h-5 w-5 rounded-md border-neutral-400 text-primary-600 "
    "focus:ring-primary-500 cursor-pointer accent-primary-600"
)


class ChallengeForm(forms.ModelForm):
    """Form for creating and editing challenges by administrative staff."""

    class Meta:
        model = Challenge
        fields = ["title", "description", "start_date", "end_date", "is_published"]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "placeholder": "e.g. 7 days without single-use plastic",
                    "class": INPUT_CLASSES,
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": (
                        "Explain the goal, the background and which actions "
                        "participants are expected to take."
                    ),
                    "class": TEXTAREA_CLASSES,
                }
            ),
            "start_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": DATE_CLASSES,
                }
            ),
            "end_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": DATE_CLASSES,
                }
            ),
            "is_published": forms.CheckboxInput(
                attrs={
                    "class": CHECKBOX_CLASSES,
                }
            ),
        }
        labels = {
            "title": "Title",
            "description": "Description",
            "start_date": "Start date",
            "end_date": "End date",
            "is_published": "Publish this challenge",
        }
        help_texts = {
            "is_published": (
                "Published challenges are visible to everyone and can be "
                "joined. Leave unchecked to keep it as a draft."
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if start_date and end_date:
            if end_date < start_date:
                self.add_error(
                    "end_date",
                    "The end date cannot be before the start date.",
                )

        return cleaned_data
