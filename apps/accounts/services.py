from django.contrib.auth.models import Group
from django.db import transaction
from .models import User


@transaction.atomic
def assign_default_role(user: User) -> User:
    
    user.Role = User.Role.USER
    user.save(update_fields=["role"])

    group, _ = Group.objects.get_or_create(name="User")
    user.groups.add(group)
    return user
