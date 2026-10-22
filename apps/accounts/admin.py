from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .forms import AdminUserChangeForm, AdminUserCreationForm
from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = AdminUserChangeForm
    add_form = AdminUserCreationForm
    list_display = ("username", "email", "role", "is_active", "is_staff")
    list_filter = DjangoUserAdmin.list_filter + ("role",)
    search_fields = ("username", "email")
    fieldsets = DjangoUserAdmin.fieldsets + (("Profile", {"fields": ("role", "bio")}),)
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        (None, {"fields": ("email", "role")}),
    )