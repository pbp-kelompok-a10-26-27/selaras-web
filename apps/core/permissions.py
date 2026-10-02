from django.contrib.auth.models import Group


def is_admin(user):
    """
    Return True when the authenticated user belongs to the Admin group.
    """
    if not user.is_authenticated:
        return False

    return user.groups.filter(name="Admin").exists()


def is_user(user):
    """
    Return True when the authenticated user belongs to the User group.
    """
    if not user.is_authenticated:
        return False

    return user.groups.filter(name="User").exists()