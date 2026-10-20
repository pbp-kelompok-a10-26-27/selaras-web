def is_authenticated_user(user) -> bool:
    return bool(user and user.is_authenticated)


def is_admin(user) -> bool:
    """Return True if user is authenticated and has Admin role or superuser status."""
    if not is_authenticated_user(user):
        return False
    return getattr(user, "role", None) == "ADMIN" or user.is_superuser


def is_user(user) -> bool:
    """Return True if user is standard platform user."""
    if not is_authenticated_user(user):
        return False
    return getattr(user, "role", None) == "USER"