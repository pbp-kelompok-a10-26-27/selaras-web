from pathlib import Path

from django import forms
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from PIL import Image, UnidentifiedImageError

from .models import Article, ArticleCategory, Tag


class ArticleForm(forms.ModelForm):
    image = forms.ImageField(
        required=False,
        error_messages={
            "invalid_image": "Unggah gambar JPEG, PNG, WEBP, atau GIF yang valid."
        },
    )
    new_tags = forms.CharField(
        required=False,
        label="Tambah tag baru",
        help_text="Pisahkan beberapa nama tag dengan koma.",
        widget=forms.TextInput(
            attrs={"placeholder": "contoh: kompos, berkebun", "autocomplete": "off"}
        ),
    )

    class Meta:
        model = Article
        fields = (
            "title",
            "summary",
            "content",
            "category",
            "tags",
            "status",
            "image",
        )
        widgets = {
            "title": forms.TextInput(
                attrs={"placeholder": "Judul yang mengundang pembaca"}
            ),
            "summary": forms.TextInput(
                attrs={"placeholder": "Ringkasan singkat untuk kartu artikel"}
            ),
            "content": forms.Textarea(
                attrs={"rows": 12, "placeholder": "Tulis isi artikel..."}
            ),
            "category": forms.Select(),
            "tags": forms.CheckboxSelectMultiple(),
            "status": forms.Select(),
            "image": forms.ClearableFileInput(
                attrs={"accept": ".jpg,.jpeg,.png,.webp,.gif"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = ArticleCategory.objects.order_by("name")
        self.fields["tags"].queryset = Tag.objects.order_by("name")
        self.fields["tags"].required = False
        self.fields["image"].required = False

    def clean_new_tags(self):
        raw_names = self.cleaned_data.get("new_tags", "")
        names = [name.strip() for name in raw_names.split(",") if name.strip()]
        if any(len(name) > 100 for name in names):
            raise ValidationError("Setiap nama tag maksimal 100 karakter.")
        if len({name.casefold() for name in names}) != len(names):
            raise ValidationError("Nama tag baru tidak boleh berulang.")
        return names

    def clean_image(self):
        upload = self.cleaned_data.get("image")
        if not isinstance(upload, UploadedFile):
            return upload

        if upload.size > 5 * 1024 * 1024:
            raise ValidationError("Ukuran gambar maksimal 5 MB.")

        allowed_extensions = {
            "JPEG": {".jpg", ".jpeg"},
            "PNG": {".png"},
            "WEBP": {".webp"},
            "GIF": {".gif"},
        }
        try:
            upload.seek(0)
            with Image.open(upload) as image:
                image_format = image.format
                width, height = image.size
                image.verify()
        except (
            UnidentifiedImageError,
            OSError,
            ValueError,
            Image.DecompressionBombError,
        ) as error:
            raise ValidationError(
                "Unggah gambar JPEG, PNG, WEBP, atau GIF yang valid."
            ) from error
        finally:
            upload.seek(0)

        extension = Path(upload.name).suffix.lower()
        if (
            image_format not in allowed_extensions
            or extension not in allowed_extensions[image_format]
            or width * height > 20_000_000
        ):
            raise ValidationError(
                "Gunakan JPEG, PNG, WEBP, atau GIF maksimal 20 megapiksel."
            )
        return upload
