from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.challenges.models import Challenge

from . import media
from .models import Comment, Post


class FeedCommentForm(forms.ModelForm):
    content = forms.CharField(
        max_length=500,
        strip=True,
        error_messages={"required": "Komentar tidak boleh kosong."},
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "maxlength": 500,
                "placeholder": "Tulis komentar...",
                "class": "feed-comment-textarea",
            }
        ),
    )

    class Meta:
        model = Comment
        fields = ("content",)

    def clean_content(self):
        content = self.cleaned_data["content"].strip()
        if not content:
            raise forms.ValidationError("Komentar tidak boleh kosong.")
        return content


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.FileField):
    """Several photos from one <input type="file" multiple>."""

    widget = MultipleImageInput

    def clean(self, data, initial=None):
        if not data:
            return []
        files = data if isinstance(data, (list, tuple)) else [data]
        single = super().clean
        return [single(file, initial) for file in files if file]


class FeedPostForm(forms.Form):
    content = forms.CharField(
        max_length=2000,
        strip=True,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "maxlength": 2000,
                "placeholder": "Ceritakan progres atau kegiatanmu...",
            }
        ),
    )
    challenge = forms.ModelChoiceField(
        queryset=Challenge.objects.none(),
        required=False,
        empty_label="Posting tanpa challenge",
    )
    images = MultipleImageField(required=False)

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.max_images = media.max_images_for(user)
        self.max_mb = media.MAX_MB
        self.fields["challenge"].queryset = Challenge.objects.filter(
            participations__user=user
        ).order_by("title")
        self.fields["images"].widget.attrs.update(
            {"accept": "image/jpeg,image/png,image/webp", "class": "feed-image-input"}
        )

    @property
    def photo_hint(self):
        return (
            f"Hingga {self.max_images} foto JPEG, PNG, atau WebP · "
            f"total maksimal {self.max_mb} MB"
        )

    def challenge_options(self):
        """Label -> value pairs for the dropdown component (the value is a string)."""
        options = {self.fields["challenge"].empty_label: ""}
        for challenge in self.fields["challenge"].queryset:
            options[challenge.title] = str(challenge.pk)
        return options

    @property
    def selected_challenge_label(self):
        chosen = str(self.data.get("challenge") or "") if self.is_bound else ""
        for label, value in self.challenge_options().items():
            if value == chosen:
                return label
        return ""

    def clean_content(self):
        content = self.cleaned_data["content"].strip()
        if not content:
            raise forms.ValidationError("Isi postingan wajib diisi.")
        return content

    def clean_images(self):
        images = self.cleaned_data.get("images") or []
        try:
            return media.validate_images(images, self.user)
        except ValidationError as error:
            raise forms.ValidationError(error.messages[0]) from error

    def save(self, user):
        post = Post(
            author=user,
            challenge=self.cleaned_data.get("challenge"),
            content=self.cleaned_data["content"],
        )
        with transaction.atomic():
            post.save()
            media.save_images(post, self.cleaned_data.get("images") or [])
        return post
