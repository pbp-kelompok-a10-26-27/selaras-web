from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User


class RegistrationForm(UserCreationForm):

    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email")

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with that email already exists.")
        return email


class ProfileForm(forms.ModelForm):

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name","bio")
        widgets = {
            "username": forms.TextInput(attrs={"readonly": "readonly", "class": "bg-gray-100 cursor-not-allowed"}),
            "bio": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.exclude(pk=self.instance.pk).filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with that email already exists.")
        return email
