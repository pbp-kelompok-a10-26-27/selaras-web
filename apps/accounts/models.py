import uuid

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.db import models
from django.db.models.functions import Lower
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStamp


class UserManager(DjangoUserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", self.model.Role.ADMIN)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser, TimeStamp):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        USER = "user", "Pengguna"

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

    @property
    def display_name(self) -> str:
        return self.get_full_name().strip() or self.get_username()

    @cached_property
    def featured_badge(self):
        """The badge this user chose to show beside their name, if any.

        Lists of users should prefetch it into ``featured_badges`` (see
        ``apps.challenges.queries.featured_badge_prefetch``) to avoid a query per row.
        """
        prefetched = getattr(self, "featured_badges", None)
        if prefetched is not None:
            return prefetched[0].badge if prefetched else None
        user_badge = (
            self.badges.filter(is_featured=True).select_related("badge").first()
        )
        return user_badge.badge if user_badge else None
