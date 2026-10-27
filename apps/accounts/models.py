import uuid

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStamp


class UserManager(DjangoUserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", self.model.Role.ADMIN)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser, TimeStamp):
    class Role(models.TextChoices):
        ADMIN = "admin", _("Admin")
        USER = "user", _("User")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(
        max_length=10, choices=Role.choices, default=Role.USER, db_index=True
    )
    email = models.EmailField(_("email"), unique=True)
    bio = models.CharField(_("bio"), max_length=200, blank=True, null=True)  # noqa: DJ001
    avatar = models.FileField(_("avatar"), upload_to="avatars/", blank=True)

    objects = UserManager()

    class Meta(AbstractUser.Meta):
        constraints = [
            models.UniqueConstraint(
                Lower("email"), name="accounts_user_email_ci_unique"
            ),
        ]

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    @property
    def avatar_url(self) -> str:
        return self.avatar.url if self.avatar else ""

    @property
    def is_admin(self) -> bool:
        return self.role == self.Role.ADMIN
