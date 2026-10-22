def is_authenticated_user(user) -> bool:
    return bool(user and user.is_authenticated)


def is_admin(user) -> bool:
    return bool(user.is_authenticated and getattr(user, "is_admin", False))


def is_user(user) -> bool:
    """Return True if user is standard platform user."""
    if not is_authenticated_user(user):
        return False
    return getattr(user, "role", None) == "USER"