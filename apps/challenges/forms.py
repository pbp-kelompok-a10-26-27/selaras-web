from django import forms

from .models import Challenge


class ChallengeForm(forms.ModelForm):
    """Form for creating and editing challenges by administrative staff."""

    class Meta:
        model = Challenge
        fields = ["title", "description", "start_date", "end_date", "is_published"]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "placeholder": "Contoh: 7 Hari Bebas Sampah Plastik Sekali Pakai",
                    "class": "w-full rounded-xl border border-neutral-400 bg-neutral-50 px-4 py-3 font-sans text-sm text-secondary-900 placeholder:text-neutral-500 focus:border-primary-500 focus:ring-2 focus:ring-primary-400/30 outline-none transition-all",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "Jelaskan tujuan, latar belakang, dan aksi nyata apa yang diharapkan dari peserta...",
                    "class": "w-full rounded-xl border border-neutral-400 bg-neutral-50 p-4 font-sans text-sm text-secondary-900 placeholder:text-neutral-500 focus:border-primary-500 focus:ring-2 focus:ring-primary-400/30 outline-none transition-all resize-none leading-relaxed",
                }
            ),
            "start_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "w-full rounded-xl border border-neutral-400 bg-neutral-50 px-4 py-3 font-sans text-sm text-secondary-900 focus:border-primary-500 focus:ring-2 focus:ring-primary-400/30 outline-none transition-all",
                }
            ),
            "end_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "w-full rounded-xl border border-neutral-400 bg-neutral-50 px-4 py-3 font-sans text-sm text-secondary-900 focus:border-primary-500 focus:ring-2 focus:ring-primary-400/30 outline-none transition-all",
                }
            ),
            "is_published": forms.CheckboxInput(
                attrs={
                    "class": "h-5 w-5 rounded-md border-neutral-400 text-primary-600 focus:ring-primary-500 cursor-pointer accent-primary-600",
                }
            ),
        }
        labels = {
            "title": "Judul Program Tantangan",
            "description": "Deskripsi & Panduan Tantangan",
            "start_date": "Tanggal Mulai",
            "end_date": "Tanggal Selesai",
            "is_published": "Publikasikan Tantangan Sekarang",
        }
        help_texts = {
            "is_published": "Centang agar tantangan dapat dilihat dan diikuti oleh seluruh pengguna di aplikasi.",
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if start_date and end_date:
            if end_date < start_date:
                self.add_error(
                    "end_date",
                    "Tanggal selesai tidak boleh lebih awal dari tanggal mulai.",
                )

        return cleaned_data
