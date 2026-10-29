import uuid

from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction

from apps.challenges.models import Challenge

from .models import Comment, Post

MAX_IMAGE_SIZE = 10 * 1024 * 1024


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


class FeedPostForm(forms.Form):
    content = forms.CharField(
        max_length=2000,
        strip=True,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "maxlength": 2000,
                "placeholder": "Ceritakan progres atau kegiatanmu...",
                "class": "w-full rounded-xl border border-slate-300 p-3",
            }
        ),
    )
    challenge = forms.ModelChoiceField(
        queryset=Challenge.objects.none(),
        required=False,
        empty_label="Posting tanpa challenge",
        widget=forms.Select(
            attrs={"class": "w-full rounded-xl border border-slate-300 p-3"}
        ),
    )
    image = forms.FileField(
        required=False,
        widget=forms.FileInput(
            attrs={
                "accept": "image/jpeg,image/png,image/webp",
                "class": "feed-image-input",
            }
        ),
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["challenge"].queryset = Challenge.objects.filter(
            participations__user=user
        ).order_by("title")

    def clean_content(self):
        content = self.cleaned_data["content"].strip()
        if not content:
            raise forms.ValidationError("Isi postingan wajib diisi.")
        return content

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if image is None:
            return image
        if not isinstance(image, UploadedFile):
            raise forms.ValidationError("File foto tidak valid.")
        if image.size > MAX_IMAGE_SIZE:
            raise forms.ValidationError("Ukuran foto maksimal 10 MB.")
        image.seek(0)
        signature = image.read(12)
        image.seek(0)
        extensions = {
            b"\xff\xd8\xff": ".jpg",
            b"\x89PNG\r\n\x1a\n": ".png",
        }
        extension = next(
            (
                suffix
                for prefix, suffix in extensions.items()
                if signature.startswith(prefix)
            ),
            None,
        )
        if signature.startswith(b"RIFF") and signature[8:12] == b"WEBP":
            extension = ".webp"
        if extension is None:
            raise forms.ValidationError("Foto harus berformat JPEG, PNG, atau WebP.")
        image.name = f"{uuid.uuid4().hex}{extension}"
        return image

    def save(self, user):
        post = Post(
            author=user,
            challenge=self.cleaned_data.get("challenge"),
            content=self.cleaned_data["content"],
        )
        image = self.cleaned_data.get("image")
        storage = post.image.storage
        try:
            with transaction.atomic():
                if image:
                    post.image.save(image.name, image, save=False)
                post.save()
        except Exception:
            if post.image.name:
                storage.delete(post.image.name)
            raise
        return post
