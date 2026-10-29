from django import forms

from .models import Badge, Challenge, CommunityGoal

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
    """Form challenge untuk admin."""

    class Meta:
        model = Challenge
        fields = [
            "title",
            "description",
            "start_date",
            "end_date",
            "goal_type",
            "goal_target",
            "badge",
            "is_published",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "placeholder": "Contoh: 7 hari tanpa plastik sekali pakai",
                    "class": INPUT_CLASSES,
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": (
                        "Jelaskan tujuan, latar belakang, dan aksi apa yang "
                        "perlu dilakukan peserta."
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
            "goal_type": forms.Select(attrs={"class": INPUT_CLASSES}),
            "goal_target": forms.NumberInput(
                attrs={"class": INPUT_CLASSES, "min": "1", "placeholder": "e.g. 5"}
            ),
            "badge": forms.Select(attrs={"class": INPUT_CLASSES}),
        }
        labels = {
            "title": "Judul",
            "description": "Deskripsi",
            "start_date": "Tanggal mulai",
            "end_date": "Tanggal selesai",
            "is_published": "Terbitkan challenge ini",
            "goal_type": "Yang dihitung sebagai progres",
            "goal_target": "Target",
            "badge": "Hadiah lencana",
        }
        help_texts = {
            "is_published": (
                "Challenge yang terbit bisa dilihat dan diikuti semua orang. "
                "Biarkan kosong untuk menyimpannya sebagai draf."
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["badge"].queryset = Badge.objects.order_by("name")
        self.fields["badge"].empty_label = "Tanpa lencana"
        # Tanpa jenis target, challenge dianggap check-in
        self.fields["goal_type"].required = False

    def clean_goal_type(self):
        return self.cleaned_data.get("goal_type") or Challenge.GoalType.CHECK_IN

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        goal_type = cleaned_data.get("goal_type")
        if goal_type and goal_type != Challenge.GoalType.CHECK_IN:
            if not cleaned_data.get("goal_target"):
                self.add_error("goal_target", "Isi angka yang harus dicapai peserta.")
        elif goal_type == Challenge.GoalType.CHECK_IN:
            # Challenge check-in memakai jumlah harinya sebagai target
            cleaned_data["goal_target"] = None

        if start_date and end_date:
            if end_date < start_date:
                self.add_error(
                    "end_date",
                    "Tanggal selesai tidak boleh sebelum tanggal mulai.",
                )

        return cleaned_data


class BadgeForm(forms.ModelForm):
    """Form lencana (ikon dan warna dipilih dari daftar tetap)."""

    class Meta:
        model = Badge
        fields = ["name", "description", "icon", "tone"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "placeholder": "Contoh: Pahlawan Zero Waste",
                    "class": INPUT_CLASSES,
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Apa yang dilakukan untuk mendapatkannya?",
                    "class": TEXTAREA_CLASSES,
                }
            ),
            "icon": forms.RadioSelect(),
            "tone": forms.RadioSelect(),
        }
        labels = {
            "name": "Nama",
            "description": "Deskripsi",
            "icon": "Ikon",
            "tone": "Warna",
        }

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        duplicate = Badge.objects.filter(name__iexact=name)
        if self.instance.pk:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise forms.ValidationError("Lencana dengan nama ini sudah ada.")
        return name


class CommunityGoalForm(forms.ModelForm):
    """Form target komunitas."""

    class Meta:
        model = CommunityGoal
        fields = [
            "title",
            "description",
            "goal_type",
            "target",
            "start_date",
            "end_date",
            "is_published",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "placeholder": "Contoh: 2.000 artikel dibaca bulan ini",
                    "class": INPUT_CLASSES,
                }
            ),
            "description": forms.TextInput(
                attrs={
                    "placeholder": "Satu kalimat kenapa ini penting (opsional)",
                    "class": INPUT_CLASSES,
                }
            ),
            "goal_type": forms.Select(attrs={"class": INPUT_CLASSES}),
            "target": forms.NumberInput(attrs={"class": INPUT_CLASSES, "min": "1"}),
            "start_date": forms.DateInput(
                attrs={"type": "date", "class": DATE_CLASSES}
            ),
            "end_date": forms.DateInput(attrs={"type": "date", "class": DATE_CLASSES}),
            "is_published": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASSES}),
        }
        labels = {
            "title": "Judul",
            "description": "Deskripsi",
            "goal_type": "Yang dihitung",
            "target": "Target",
            "start_date": "Tanggal mulai",
            "end_date": "Tanggal selesai",
            "is_published": "Tampilkan di situs",
        }

    def clean(self):
        cleaned_data = super().clean()
        start, end = cleaned_data.get("start_date"), cleaned_data.get("end_date")
        if start and end and end < start:
            self.add_error(
                "end_date", "Tanggal selesai tidak boleh sebelum tanggal mulai."
            )
        target = cleaned_data.get("target")
        if target is not None and target < 1:
            self.add_error("target", "Target minimal 1.")
        return cleaned_data
