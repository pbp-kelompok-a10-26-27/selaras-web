from django import forms
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import User


class NormalizedEmailMixin:
    """Lowercases the email and rejects case-insensitive duplicates."""

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        qs = User.objects.filter(email__iexact=email)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(_("A user with this email already exists."))
        return email


class RegistrationForm(NormalizedEmailMixin, UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")


class ProfileForm(NormalizedEmailMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "bio")  # never role/is_staff


class AdminUserCreationForm(NormalizedEmailMixin, UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "role")


class AdminUserChangeForm(NormalizedEmailMixin, UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"