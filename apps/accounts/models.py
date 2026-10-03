from django.contrib.auth.models import AbstractUser
from django.db import models
from apps.core.models import TimeStamp
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

class User(AbstractUser, TimeStamp):
	
    class Role(models.TextChoices):

        ADMIN = "Admin", _("Admin")
        USER = "User", _("User")

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.USER, db_index=True)
    email = models.EmailField(_("email"), unique=True)
    bio = models.TextField(_("bio"), max_length=200, blank=True, null=True)

    class Meta:
		
	    constraints = [
			models.UniqueConstraint(Lower("email"), name="accounts_user_email_ci_unique"),
		]



